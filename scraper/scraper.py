"""
Teka product scraper using Playwright.

Strategy:
  1. Intercept JSON API responses – if the site fetches product data via XHR/fetch,
     we capture it directly (clean, structured, fast).
  2. Fall back to DOM parsing – scroll-based lazy loading, extract from rendered HTML.
"""

import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright, Page, Request, Response

from .config import (
    BASE_URL, BROWSER, SCROLL,
    PRODUCT_CARD_SELECTORS, PRODUCT_LINK_SELECTORS, PRODUCT_NAME_SELECTORS,
    PRODUCT_DESC_SELECTORS, PRODUCT_IMAGE_SELECTORS, PRODUCT_BADGE_SELECTORS,
    PRODUCT_COLOR_SELECTORS, CONSENT_SELECTORS,
)

log = logging.getLogger(__name__)


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
                log.debug("Dismissed consent banner via %s", sel)
                return
        except Exception:
            pass


def _scroll_full_page(page: Page) -> None:
    """Scroll incrementally to trigger lazy-loading; stop when height stabilises."""
    cfg = SCROLL
    prev_height = 0
    idle_count = 0
    position = 0
    round_n = 0

    while round_n < cfg["max_rounds"]:
        page.evaluate(f"window.scrollTo(0, {position})")
        page.wait_for_timeout(cfg["pause_ms"])

        new_height = page.evaluate("document.body.scrollHeight")
        position = min(position + cfg["step_px"], new_height)

        if new_height == prev_height:
            idle_count += 1
            if idle_count >= cfg["idle_rounds_to_stop"]:
                break
        else:
            idle_count = 0

        prev_height = new_height
        round_n += 1
        log.debug("Scroll round %d  pos=%d  height=%d", round_n, position, new_height)

    # Return to top so images near the header are resolved.
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(400)


# ---------------------------------------------------------------------------
# Data extraction – DOM path
# ---------------------------------------------------------------------------

def _first_text(el, selectors: list[str]) -> str:
    for sel in selectors:
        try:
            child = el.locator(sel).first
            if child.count() and child.is_visible(timeout=500):
                return child.inner_text().strip()
        except Exception:
            pass
    return ""


def _first_attr(el, selectors: list[str], attr: str) -> str:
    for sel in selectors:
        try:
            child = el.locator(sel).first
            if child.count():
                val = child.get_attribute(attr) or ""
                if val:
                    return val
        except Exception:
            pass
    return ""


def _extract_card(card, category_name: str, category_url: str) -> dict[str, Any] | None:
    try:
        # Link / URL
        href = _first_attr(card, PRODUCT_LINK_SELECTORS, "href")
        if not href:
            # Try the card itself as a link
            href = card.get_attribute("href") or ""
        product_url = urljoin(BASE_URL, href) if href else ""

        # Name
        name = _first_text(card, PRODUCT_NAME_SELECTORS)
        if not name and product_url:
            # Derive a rough name from URL slug
            slug = product_url.rstrip("/").split("/")[-1]
            name = slug.replace("-", " ").title()

        if not name:
            return None

        # Image – prefer data-src (lazy), then src
        image_url = ""
        for sel in PRODUCT_IMAGE_SELECTORS:
            try:
                img = card.locator(sel).first
                if img.count():
                    image_url = (
                        img.get_attribute("data-src")
                        or img.get_attribute("data-lazy-src")
                        or img.get_attribute("src")
                        or ""
                    )
                    if image_url and not image_url.startswith("data:"):
                        image_url = urljoin(BASE_URL, image_url)
                        break
            except Exception:
                pass

        # Description
        description = _first_text(card, PRODUCT_DESC_SELECTORS)

        # Badges (NUEVO, WiFi …)
        badges: list[str] = []
        for sel in PRODUCT_BADGE_SELECTORS:
            try:
                for b in card.locator(sel).all():
                    txt = b.inner_text().strip()
                    if txt:
                        badges.append(txt)
            except Exception:
                pass

        # Color swatches
        colors: list[str] = []
        for sel in PRODUCT_COLOR_SELECTORS:
            try:
                for c in card.locator(sel).all():
                    color_val = (
                        c.get_attribute("data-color")
                        or c.get_attribute("title")
                        or c.get_attribute("aria-label")
                        or c.inner_text().strip()
                    )
                    if color_val:
                        colors.append(color_val)
            except Exception:
                pass

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "category": category_name,
            "category_url": category_url,
            "name": name,
            "product_url": product_url,
            "image_url": image_url,
            "description": description,
            "badges": ", ".join(badges),
            "colors": ", ".join(colors),
        }
    except Exception as exc:
        log.warning("Card extraction error: %s", exc)
        return None


def _scrape_via_dom(page: Page, category_name: str, category_url: str) -> list[dict]:
    """Find product cards in the rendered DOM."""
    products: list[dict] = []

    for sel in PRODUCT_CARD_SELECTORS:
        cards = page.locator(sel).all()
        if cards:
            log.info("Using selector '%s' – found %d cards", sel, len(cards))
            for card in cards:
                product = _extract_card(card, category_name, category_url)
                if product:
                    products.append(product)
            break
        log.debug("No match for selector '%s'", sel)

    if not products:
        log.warning("DOM fallback: no product cards matched known selectors for %s", category_url)
        # Last resort: collect all <a> tags that look like product URLs
        links = page.locator("a[href*='/producto/'], a[href*='/product/']").all()
        seen: set[str] = set()
        for link in links:
            href = link.get_attribute("href") or ""
            product_url = urljoin(BASE_URL, href)
            if product_url in seen:
                continue
            seen.add(product_url)
            name = link.inner_text().strip() or product_url.rstrip("/").split("/")[-1].replace("-", " ").title()
            products.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "category": category_name,
                "category_url": category_url,
                "name": name,
                "product_url": product_url,
                "image_url": "",
                "description": "",
                "badges": "",
                "colors": "",
            })
        log.info("Last-resort link harvest: %d products", len(products))

    return products


# ---------------------------------------------------------------------------
# Data extraction – API interception path
# ---------------------------------------------------------------------------

_JSON_PRODUCT_KEYS = {"name", "title", "sku", "url", "image"}

def _looks_like_product_list(obj: Any) -> list[dict] | None:
    """Return a list of product dicts if obj looks like a product API response."""
    if isinstance(obj, list) and obj and isinstance(obj[0], dict):
        if _JSON_PRODUCT_KEYS & obj[0].keys():
            return obj
    if isinstance(obj, dict):
        for key in ("data", "products", "items", "results", "nodes"):
            val = obj.get(key)
            if isinstance(val, list) and val and isinstance(val[0], dict):
                if _JSON_PRODUCT_KEYS & val[0].keys():
                    return val
    return None


def _parse_api_products(raw: list[dict], category_name: str, category_url: str) -> list[dict]:
    products = []
    ts = datetime.now(timezone.utc).isoformat()
    for item in raw:
        name = item.get("name") or item.get("title") or ""
        if not name:
            continue
        href = item.get("url") or item.get("path") or item.get("link") or ""
        product_url = urljoin(BASE_URL, href) if href else ""
        image = item.get("image") or ""
        if isinstance(image, dict):
            image = image.get("url") or image.get("src") or ""
        products.append({
            "timestamp": ts,
            "category": category_name,
            "category_url": category_url,
            "name": name,
            "product_url": product_url,
            "image_url": image,
            "description": item.get("description") or item.get("short_description") or "",
            "badges": ", ".join(item.get("badges", []) or []),
            "colors": ", ".join(item.get("colors", []) or []),
            "sku": item.get("sku") or item.get("reference") or "",
            "ean": item.get("ean") or item.get("gtin") or "",
            "price": str(item.get("price") or item.get("final_price") or ""),
        })
    return products


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def scrape_category(
    page: Page,
    category_name: str,
    category_url: str,
) -> list[dict]:
    """
    Scrape one category page and return a list of product dicts.
    Tries API interception first; falls back to DOM scraping.
    """
    captured_products: list[dict] = []

    def handle_response(response: Response) -> None:
        if captured_products:
            return  # already got data
        ct = response.headers.get("content-type", "")
        if "json" not in ct:
            return
        url = response.url
        if any(skip in url for skip in ("google-analytics", "facebook", "hotjar", "sentry")):
            return
        try:
            text = response.text()
            obj = json.loads(text)
            items = _looks_like_product_list(obj)
            if items:
                log.info("API intercept hit: %s  (%d items)", url, len(items))
                captured_products.extend(
                    _parse_api_products(items, category_name, category_url)
                )
        except Exception:
            pass

    page.on("response", handle_response)

    try:
        log.info("Loading %s", category_url)
        page.goto(category_url, wait_until="domcontentloaded", timeout=BROWSER["timeout"])
        _dismiss_consent(page)
        page.wait_for_timeout(1_500)
        _scroll_full_page(page)
        page.wait_for_timeout(1_000)
    finally:
        page.remove_listener("response", handle_response)

    if captured_products:
        log.info("API path: %d products in '%s'", len(captured_products), category_name)
        return captured_products

    # DOM fallback
    products = _scrape_via_dom(page, category_name, category_url)
    log.info("DOM path: %d products in '%s'", len(products), category_name)
    return products


def scrape_all(categories: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Scrape all categories. Returns (all_products, run_log).
    """
    all_products: list[dict] = []
    run_log: list[dict] = []

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
        # Hide webdriver flag
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = context.new_page()

        for cat in categories:
            start = time.time()
            status = "ok"
            count = 0
            try:
                products = scrape_category(page, cat["name"], cat["url"])
                all_products.extend(products)
                count = len(products)
            except Exception as exc:
                log.error("Failed to scrape '%s': %s", cat["name"], exc)
                status = f"error: {exc}"
            elapsed = round(time.time() - start, 1)
            run_log.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "category": cat["name"],
                "url": cat["url"],
                "products_found": count,
                "duration_s": elapsed,
                "status": status,
            })
            # Be polite
            time.sleep(2)

        browser.close()

    return all_products, run_log
