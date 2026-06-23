"""
Google Sheets writer.

Auth:  Service-account JSON stored in env var GOOGLE_CREDENTIALS.
Sheet: The spreadsheet must be shared with the service account email.
"""

import json
import logging
import os
from typing import Any

import gspread
from google.oauth2.service_account import Credentials

from .config import SHEETS

log = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

PRODUCT_HEADERS = [
    "timestamp",
    "category",
    "category_teka",
    "category_id",
    "sku",
    "short_name",
    "name",
    "installation_type",
    "energy_class",
    "features",
    "review_score",
    "colors",
    "color_class",
    "is_new",
    "product_url",
    "image_url",
    "image_alt_url",
    "color_images",
    "category_url",
]

LOG_HEADERS = [
    "timestamp",
    "category",
    "url",
    "products_found",
    "duration_s",
    "status",
]


def _get_client() -> gspread.Client:
    raw = os.environ.get("GOOGLE_CREDENTIALS", "")
    if not raw:
        raise RuntimeError("GOOGLE_CREDENTIALS env var is not set")
    info = json.loads(raw)
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(creds)


def _ensure_tab(spreadsheet: gspread.Spreadsheet, title: str) -> gspread.Worksheet:
    try:
        return spreadsheet.worksheet(title)
    except gspread.WorksheetNotFound:
        log.info("Creating tab '%s'", title)
        return spreadsheet.add_worksheet(title=title, rows=5_000, cols=20)


def _rows_from_dicts(headers: list[str], records: list[dict]) -> list[list[Any]]:
    return [[r.get(h, "") for h in headers] for r in records]


def write_products(products: list[dict], run_log: list[dict]) -> None:
    """Clear and rewrite the Products and Log tabs."""
    client = _get_client()
    sheet_id = SHEETS["spreadsheet_id"]
    if not sheet_id:
        raise RuntimeError("GOOGLE_SHEET_ID env var is not set")

    spreadsheet = client.open_by_key(sheet_id)

    # --- Products tab ---
    ws = _ensure_tab(spreadsheet, SHEETS["products_tab"])
    ws.clear()
    product_rows = _rows_from_dicts(PRODUCT_HEADERS, products)
    data = [PRODUCT_HEADERS] + product_rows
    ws.update("A1", data, value_input_option="USER_ENTERED")
    ws.freeze(rows=1)
    log.info("Written %d products to '%s'", len(products), SHEETS["products_tab"])

    # --- Log tab ---
    log_ws = _ensure_tab(spreadsheet, SHEETS["log_tab"])
    # Prepend new log entries (keep history – don't clear)
    existing = log_ws.get_all_values()
    has_header = existing and existing[0] == LOG_HEADERS
    new_rows = _rows_from_dicts(LOG_HEADERS, run_log)
    if has_header:
        # Insert after header
        body = [LOG_HEADERS] + new_rows + existing[1:]
    else:
        body = [LOG_HEADERS] + new_rows + existing
    log_ws.clear()
    log_ws.update("A1", body, value_input_option="USER_ENTERED")
    log_ws.freeze(rows=1)
    log.info("Log tab updated (%d new entries)", len(run_log))
