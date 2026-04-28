# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

Automates the manual process of collecting questionnaire data from a web application. Logs in via SSO, navigates to Products > All Products, filters by sigla "ic5", iterates every product detail page, and exports fields from the "Risk Assessment" and "Access" questionnaire sections to CSV.

## Setup

```bash
# 1. Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows

# 2. Install dependencies (Selenium Manager auto-downloads ChromeDriver on first run)
pip install -r requirements.txt

# 3. Configure the target URL
copy .env.example .env
# Edit .env and set APP_URL=<url da aplicação>
```

Requires Google Chrome already installed. No manual ChromeDriver setup needed — Selenium 4.6+ handles it automatically.

## Running

```bash
# Gera um novo CSV com nome automático baseado em timestamp
python main.py

# Salva em um arquivo específico (cria se não existir)
python main.py --output relatorio.csv

# Adiciona ao final de um CSV existente sem duplicar o cabeçalho
python main.py --output relatorio.csv   # se relatorio.csv já existir → append
```

On first run a Chrome window opens for SSO login. After login, press Enter in the terminal. Auth cookies are persisted to `auth_state.json` and reused on subsequent runs (re-login triggers automatically when the session expires).

Set `SLOW_MO=1000` in `.env` to slow down browser actions for visual debugging.

### Output file behavior

| Situação | Comportamento |
|----------|---------------|
| Sem `--output` | Cria `relatorio-YYYYMMDD-HHMMSSmmm.csv` |
| `--output arquivo.csv` (não existe) | Cria o arquivo com cabeçalho |
| `--output arquivo.csv` (já existe) | Adiciona linhas ao final, sem repetir o cabeçalho |

## Architecture

| File | Responsibility |
|------|---------------|
| `main.py` | Entry point — validates config, calls scrape, calls exporter; `--output` controls write vs append |
| `scraper.py` | All browser automation: auth, navigation, filtering, extraction |
| `exporter.py` | Writes or appends results to CSV with `utf-8-sig` encoding (Excel-compatible) |
| `config.py` | Loads `.env` values; single source of truth for constants |

### Key flows in `scraper.py`

- `_restore_or_login` — loads `auth_state.json` cookies if present; if session expired or missing, opens Chrome and waits for manual SSO completion, then saves cookies.
- `_go_to_all_products` → `_apply_filter` → `_set_pagesize_all` — three-step navigation to get all results on one page.
- `_collect_product_links` — snapshots all `(name, href)` pairs before iteration to avoid stale element references.
- `_extract_questionnaire(driver, section_title)` — locates a Bootstrap panel/card by its heading text, then extracts Completion Date, Expiration Date, Responder, and Status using multiple XPath fallbacks (table, definition list, label).
- `_wait_page` — waits for `document.readyState == complete` plus jQuery AJAX idle, with optional `SLOW_MO` delay.

## Selector Customization

All selectors that depend on the real HTML are marked with `# AJUSTE` comments in `scraper.py`. Inspect the target page with browser DevTools (F12) and update:

- Sidebar menu XPath in `_go_to_all_products`
- Sigla input XPath in `_apply_filter`
- Pagesize combobox XPath in `_set_pagesize_all`
- Table row XPath in `_collect_product_links`
- Section panel XPath and field label strings in `_extract_questionnaire`

## Output

CSV gerado via `--output` ou com nome automático `relatorio-YYYYMMDD-HHMMSSmmm.csv`.

Colunas: `nome_aplicacao`, `sigla_app`, `repo`, `url`, `risk_overall_risk`, `risk_responder`, `risk_status`, `risk_completion_date`, `risk_expiration_date`, `access_responder`, `access_status`, `access_completion_date`.
