# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

Automates the manual process of collecting questionnaire data from a web application. Logs in via SSO, navigates to Products > All Products, filters by sigla "ic5", iterates every product detail page, and exports fields from the "Risk Assessment" and "Access" questionnaire sections to CSV.

## Setup

```bash
# 1. Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows

# 2. Install dependencies
pip install -r requirements.txt
playwright install chromium

# 3. Configure the target URL
copy .env.example .env
# Edit .env and set APP_URL=<url da aplicação>
```

## Running

```bash
python main.py
```

On first run a headed Chromium window opens for SSO login. After login, press Enter in the terminal. Auth state is persisted to `auth_state.json` and reused on subsequent runs (re-login is triggered automatically when the session expires).

Set `SLOW_MO=500` in `.env` to slow down browser actions for visual debugging.

## Architecture

| File | Responsibility |
|------|---------------|
| `main.py` | Entry point — validates config, runs async scrape, calls exporter |
| `scraper.py` | All browser automation: auth, navigation, filtering, extraction |
| `exporter.py` | Writes results list to CSV with `utf-8-sig` encoding (Excel-compatible) |
| `config.py` | Loads `.env` values; single source of truth for constants |

### Key flows in `scraper.py`

- `_restore_or_login` — loads `auth_state.json` if present; if session expired or missing, opens headed browser and waits for manual SSO completion, then saves state.
- `_go_to_all_products` → `_apply_filter` → `_set_pagesize_all` — three-step navigation to get all results on one page.
- `_collect_product_links` — snapshots all `(name, href)` pairs before iteration to avoid stale element references.
- `_extract_questionnaire(page, section_title)` — locates a Bootstrap panel/card by its heading text, then extracts Completion Date, Expiration Date, Responder, and Status using multiple selector fallbacks (table, definition list, label).

## Selector Customization

All selectors that depend on the real HTML are marked with `# AJUSTE` comments in `scraper.py`. Inspect the target page with browser DevTools (F12) and update:

- Sidebar menu selector in `_go_to_all_products`
- Sigla input selector in `_apply_filter`
- Pagesize combobox selector in `_set_pagesize_all`
- Table row selector in `_collect_product_links`
- Section panel selector and field label strings in `_extract_questionnaire`

## Output

`levantamento_ic5.csv` — columns: `produto`, `risk_completion_date`, `risk_expiration_date`, `risk_responder`, `risk_status`, `access_completion_date`, `access_expiration_date`, `access_responder`, `access_status`.
