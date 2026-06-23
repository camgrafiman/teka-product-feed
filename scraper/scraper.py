"""
Teka product scraper – Playwright-based.

All key product data lives in data-* attributes and CSS classes on each
.et_pb_portfolio_item div. We extract everything with a single page.evaluate()
call after scrolling to trigger lozad lazy-image loading.
"""

import json
import logging
import time
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright, Page, Response

from .config import BROWSER, SCROLL, CONSENT_SELECTORS

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# JavaScript executed inside the browser page to collect all product data.
# Returns a plain list of dicts – no Playwright locators needed.
# ---------------------------------------------------------------------------
_EXTRACT_JS = r"""
() => {
    const cards = document.querySelectorAll(
        '.et_pb_portfolio_item[data-product-sku]'
    );

    return Array.from(cards).map(card => {
        const cls = card.className;

        /* ── data attributes ── */
        const sku       = card.getAttribute('data-product-sku')          || '';
        const shortName = card.getAttribute('data-short-product-name')   || '';
        const fullName  = card.getAttribute('data-product-name')         || '';
        const catId     = card.getAttribute('data-product-cat')          || '';
        const catTeka   = card.getAttribute('data-product-cat0')         || '';
        const review    = card.getAttribute('data-review-value')         || '';

        /* ── CSS-class attributes ── */
        const instM   = cls.match(/product_type_of_installation-([\w-]+)/);
        const energyM = cls.match(/product_energy_efficiency-([a-z])-/i);
        const colorM  = cls.match(/\bcolor-([\w-]+)/);
        const iconMs  = cls.match(/product_icons-[\w-]+/g) || [];

        const installationType = instM
            ? instM[1].replace(/-/g, ' ')
            : '';
        const energyClass = energyM ? energyM[1].toUpperCase() : '';
        const colorClass  = colorM
            ? colorM[1].replace(/-/g, ' ')
            : '';
        const features = iconMs
            .map(m => m.replace('product_icons-', '').replace(/-/g, ' '))
            .join(', ');

        /* ── product URL (first .product-link) ── */
        const linkEl     = card.querySelector('a.product-link');
        const productUrl = linkEl ? linkEl.href : '';

        /* ── main image (data-src preferred for lozad pages) ── */
        const imgOrg   = card.querySelector('img.product-cat-img-org');
        const imageUrl = imgOrg
            ? (imgOrg.getAttribute('data-src') || imgOrg.getAttribute('src') || '')
            : '';

        /* ── alternate / hover image ── */
        const imgAlt      = card.querySelector('img.product-cat-img-alt');
        const imageAltUrl = imgAlt
            ? (imgAlt.getAttribute('data-src') || imgAlt.getAttribute('src') || '')
            : '';

        /* ── color swatches in footer ── */
        const swatches = card.querySelectorAll(
            '.product-list-colors img.tooltip, .product-list-colors img.tooltipstered'
        );
        const colorNames  = Array.from(swatches)
            .map(i => i.getAttribute('alt') || '').filter(Boolean).join(', ');
        const colorImages = Array.from(swatches)
            .map(i => i.getAttribute('src') || '').filter(Boolean).join(', ');

        /* ── "NUEVO" / new badge ── */
        const badgeEl  = card.querySelector(
            '.badge, .new-badge, .badge-new, [class*="badge"], .product-new'
        );
        const badgeTxt = badgeEl ? badgeEl.innerText.trim() : '';
        // Also check any overlay inside the image container
        const imgContainerTxt =
            (card.querySelector('.product-cat-img-container') || {innerText: ''}).innerText || '';
        const isNew = /\bnuevo\b/i.test(badgeTxt) || /\bnuevo\b/i.test(imgContainerTxt)
            ? 'Sí' : '';

        return {
            sku,
            short_name:        shortName,
            name:              fullName,
            category_id:       catId,
            category_teka:     catTeka,
            review_score:      review,
            installation_type: installationType,
            energy_class:      energyClass,
            color_class:       colorClass,
            features,
            product_url:       productUrl,
            image_url:         imageUrl,
            image_alt_url:     imageAltUrl,
            colors:            colorNames,
            color_images:      colorImages,
            is_new:            isNew,
        };
    });
}
"""

# ---------------------------------------------------------------------------
# Browser helpers
# ---------------------------------------------------------------------------

def _dismiss_consent(page: Page) -> None:
    for sel in CONSENT_SELECTORS:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=2_000):
                btn.click()
                page.wait_for_timeout(800)
                log.debug("Dismissed consent via %s", sel)
                return
        except Exception:
            pass


def _scroll_full_page(page: Page) -> None:
    """Scroll incrementally so lozad loads all lazy images."""
    cfg = SCROLL
    prev_height = 0
    idle_count  = 0
    position    = 0
    round_n     = 0

    while round_n < cfg["max_rounds"]:
        page.evaluate(f"window.scrollTo(0, {position})")
        page.wait_for_timeout(cfg["pause_ms"])

        new_height = page.evaluate("document.body.scrollHeight")
        position   = min(position + cfg["step_px"], new_height)

        if new_height == prev_height:
            idle_count += 1
            if idle_count >= cfg["idle_rounds_to_stop"]:
                break
        else:
            idle_count = 0

        prev_height = new_height
        round_n    += 1
        log.debug("Scroll %d  pos=%d  height=%d", round_n, position, new_height)

    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(400)


# ---------------------------------------------------------------------------
# Public scraping functions
# ---------------------------------------------------------------------------

def scrape_category(page: Page, category_name: str, category_url: str) -> list[dict]:
    log.info("Loading %s", category_url)
    page.goto(category_url, wait_until="domcontentloaded", timeout=BROWSER["timeout"])
    _dismiss_consent(page)
    page.wait_for_timeout(1_500)
    _scroll_full_page(page)
    page.wait_for_timeout(1_000)

    raw: list[dict] = page.evaluate(_EXTRACT_JS)

    if not raw:
        log.warning("No products found in '%s' – check selector or page structure", category_name)
        return []

    ts = datetime.now(timezone.utc).isoformat()
    for p in raw:
        p["timestamp"]    = ts
        p["category"]     = category_name
        p["category_url"] = category_url

    log.info("Extracted %d products from '%s'", len(raw), category_name)
    return raw


def scrape_all(categories: list[dict]) -> tuple[list[dict], list[dict]]:
    """Scrape all categories. Returns (all_products, run_log)."""
    all_products: list[dict] = []
    run_log:      list[dict] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=BROWSER["headless"],
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = browser.new_context(
            viewport=BROWSER["viewport"],
            user_agent=BROWSER["user_agent"],
            locale=BROWSER["locale"],
            extra_http_headers={"Accept-Language": "es-ES,es;q=0.9,en;q=0.8"},
        )
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = context.new_page()

        for cat in categories:
            start  = time.time()
            status = "ok"
            count  = 0
            try:
                products = scrape_category(page, cat["name"], cat["url"])
                all_products.extend(products)
                count = len(products)
            except Exception as exc:
                log.error("Failed '%s': %s", cat["name"], exc)
                status = f"error: {exc}"

            elapsed = round(time.time() - start, 1)
            run_log.append({
                "timestamp":      datetime.now(timezone.utc).isoformat(),
                "category":       cat["name"],
                "url":            cat["url"],
                "products_found": count,
                "duration_s":     elapsed,
                "status":         status,
            })
            time.sleep(2)  # polite delay between categories

        browser.close()

    return all_products, run_log
