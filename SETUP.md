# Teka Product Feed – Setup Guide

## What this does

Scrapes all Teka product listing pages (19 categories, ES‑ES), writes the
results to a Google Sheet, and runs automatically every Monday at 06:00 UTC
via GitHub Actions.

---

## 1. Google Cloud – Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com) and create
   (or open) a project.
2. Enable the **Google Sheets API** and **Google Drive API** for the project.
3. Create a **Service Account**:
   - IAM & Admin → Service Accounts → Create
   - Role: **Editor** (or a custom role with Sheets + Drive write access)
4. Create a JSON key for the service account:
   - Service Account → Keys → Add Key → Create new key → JSON
   - Download the file (keep it secret – do not commit it)
5. Note the `client_email` from the JSON file.

---

## 2. Google Sheet

1. Create a new Google Sheet (or open an existing one).
2. Share it with the service-account `client_email` as **Editor**.
3. Copy the Sheet ID from the URL:
   ```
   https://docs.google.com/spreadsheets/d/<SHEET_ID>/edit
   ```

---

## 3. GitHub Secrets

In your repository → Settings → Secrets and variables → Actions, add:

| Secret name          | Value                                        |
|----------------------|----------------------------------------------|
| `GOOGLE_CREDENTIALS` | Paste the **entire contents** of the JSON key file |
| `GOOGLE_SHEET_ID`    | The Sheet ID from step 2                     |

---

## 4. Run manually

GitHub Actions → Workflows → **Teka Product Feed Scraper** → Run workflow.

Optional inputs:
- **Dry run**: scrape but don't upload to Sheets (useful for debugging)
- **Category indices**: comma-separated list (e.g. `0,1,2`) to test a subset

---

## 5. Local development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium

cp .env.example .env
# Edit .env with your credentials

# Test one category (index 0 = Hornos), dry run
python -m scraper.main --categories 0 --dry-run --output out.json

# Full run
python -m scraper.main
```

---

## Output columns (Productos tab)

| Column        | Description                                    |
|---------------|------------------------------------------------|
| timestamp     | ISO-8601 UTC time the row was scraped          |
| category      | Category name (e.g. Hornos)                    |
| name          | Product name                                   |
| sku           | Model code (when available via API)            |
| ean           | EAN/GTIN (when available via API)              |
| price         | Price (when available)                         |
| description   | Short description from listing page            |
| badges        | NUEVO, WiFi, etc.                              |
| colors        | Available colours                              |
| product_url   | Link to product detail page                    |
| image_url     | Main product image                             |
| category_url  | Source category page                           |

---

## How the scraper works

1. **API interception first** – Playwright intercepts every JSON XHR/fetch
   response. If a response looks like a product list (has `name`/`sku`/`url`
   keys), it is parsed directly. This is faster and more reliable than DOM
   parsing.

2. **DOM fallback** – If no API is intercepted, the scraper scrolls the full
   page (to trigger lazy-loaded images), then tries a priority list of CSS
   selectors to find product cards and extracts name, image, description,
   badges, and colours from the rendered HTML.

3. **Results are written to Sheets** – The *Productos* tab is cleared and
   rewritten on every run. The *Log* tab keeps a cumulative history of each
   run (category, count, duration, status).
