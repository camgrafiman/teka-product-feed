"""
Entry point for the Teka product scraper.

Usage:
    python -m scraper.main                    # scrape all categories
    python -m scraper.main --dry-run          # scrape but skip Sheets upload
    python -m scraper.main --categories 0,1   # scrape specific category indices
"""

import argparse
import json
import logging
import sys

from .config import CATEGORIES
from .scraper import scrape_all
from .sheets import write_products

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Teka product scraper")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Scrape and print results; do NOT write to Google Sheets",
    )
    p.add_argument(
        "--categories",
        default="",
        help="Comma-separated indices of categories to scrape (default: all)",
    )
    p.add_argument(
        "--output",
        default="",
        help="Optional path to save JSON output (e.g. products.json)",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()

    if args.categories:
        indices = [int(i.strip()) for i in args.categories.split(",")]
        categories = [CATEGORIES[i] for i in indices]
    else:
        categories = CATEGORIES

    log.info("Scraping %d categories", len(categories))
    products, run_log = scrape_all(categories)
    log.info("Total products scraped: %d", len(products))

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(products, f, ensure_ascii=False, indent=2)
        log.info("Saved JSON to %s", args.output)

    if args.dry_run:
        log.info("Dry-run mode – skipping Google Sheets upload")
        for p in products[:5]:
            log.info("  sample: %s | %s", p.get("category"), p.get("name"))
        return

    log.info("Uploading to Google Sheets…")
    write_products(products, run_log)
    log.info("Done.")


if __name__ == "__main__":
    main()
