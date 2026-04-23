"""
Automação de navegação via Selenium.

AJUSTES NECESSÁRIOS:
  Seletores marcados com "# AJUSTE" devem ser conferidos com F12 no browser.
  Execute com SLOW_MO=1000 no .env para ver a automação em câmera lenta.
"""
import json
import logging
import re
import time
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from config import APP_URL, AUTH_STATE_FILE, BROWSER, CHROMEDRIVER_PATH, SLOW_MO

log = logging.getLogger(__name__)

TIMEOUT = 15


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def _make_driver() -> webdriver.Chrome | webdriver.Edge:
    if BROWSER == "edge":
        options = webdriver.EdgeOptions()
        options.add_argument("--start-maximized")
        return webdriver.Edge(service=EdgeService(), options=options)

    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    driver_path = Path(CHROMEDRIVER_PATH)
    if not driver_path.exists():
        raise FileNotFoundError(
            f"ChromeDriver não encontrado em '{driver_path}'.\n"
            "Defina CHROMEDRIVER_PATH no .env ou use BROWSER=edge no .env para usar o Edge."
        )
    return webdriver.Chrome(service=ChromeService(executable_path=str(driver_path)), options=options)


# ---------------------------------------------------------------------------
# Autenticação via cookies
# ---------------------------------------------------------------------------

def _is_login_page(url: str) -> bool:
    return any(k in url.lower() for k in ("login", "sso", "auth", "signin", "adfs"))


def _save_cookies(driver, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(driver.get_cookies(), f)


def _load_cookies(driver, path: str) -> None:
    driver.get(APP_URL)
    with open(path, encoding="utf-8") as f:
        for cookie in json.load(f):
            try:
                driver.add_cookie(cookie)
            except Exception:
                pass


def _restore_or_login(driver, target_url: str) -> None:
    if Path(AUTH_STATE_FILE).exists():
        _load_cookies(driver, AUTH_STATE_FILE)
        driver.get(target_url)
        _wait_page(driver)
        if not _is_login_page(driver.current_url):
            log.info("Sessão restaurada com sucesso.")
            return
        log.warning("Sessão expirada. Necessário novo login.")

    driver.get(target_url)
    _wait_page(driver)

    if _is_login_page(driver.current_url):
        log.info("Login SSO detectado. Complete o login no browser e pressione Enter aqui...")
        input()
        _wait_page(driver)

    _save_cookies(driver, AUTH_STATE_FILE)
    log.info("Cookies salvos em '%s'.", AUTH_STATE_FILE)


# ---------------------------------------------------------------------------
# Espera de carregamento
# ---------------------------------------------------------------------------

def _wait_page(driver, timeout: int = TIMEOUT) -> None:
    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )
    try:
        WebDriverWait(driver, 3).until(
            lambda d: d.execute_script("return typeof jQuery === 'undefined' || jQuery.active === 0")
        )
    except Exception:
        pass
    if SLOW_MO:
        time.sleep(SLOW_MO / 1000)


# ---------------------------------------------------------------------------
# Coleta de hrefs da tabela de produtos
# ---------------------------------------------------------------------------

def _collect_product_links(driver) -> list[tuple[str, str]]:
    try:
        WebDriverWait(driver, TIMEOUT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table#products tbody tr"))
        )
    except TimeoutException:
        raise RuntimeError("Tabela 'table#products' não encontrada. Verifique a URL informada.")

    # Padrão esperado: /product/<id> sem sub-caminhos após o id numérico
    # AJUSTE: altere o regex se o padrão de URL for diferente
    product_url_pattern = re.compile(r"/product/\d+/?$")

    rows = driver.find_elements(By.CSS_SELECTOR, "table#products tbody tr")
    items = []
    for row in rows:
        for link in row.find_elements(By.CSS_SELECTOR, "td a"):
            href = link.get_attribute("href") or ""
            if product_url_pattern.search(href):
                items.append((link.text.strip(), href))
                break  # pega apenas o primeiro link válido por linha
    return items


# ---------------------------------------------------------------------------
# Navegação de abas
# ---------------------------------------------------------------------------

def _click_overview_tab(driver) -> None:
    """Clica na aba Overview (li[role=presentation] > span: Overview)."""
    try:
        tab = WebDriverWait(driver, TIMEOUT).until(
            EC.element_to_be_clickable((By.XPATH,
                "//li[@role='presentation']//span[contains(normalize-space(),'Overview')]"
                " | //li[@role='tab']//span[contains(normalize-space(),'Overview')]"
            ))
        )
        tab.click()
        _wait_page(driver)
        log.debug("  Aba 'Overview' selecionada.")
    except TimeoutException:
        log.warning("  Aba 'Overview' não encontrada — tentando extrair da página atual.")


# ---------------------------------------------------------------------------
# Diagnóstico da página de detalhe
# ---------------------------------------------------------------------------

def _diagnose_page(driver) -> None:
    """Loga a estrutura encontrada na página para ajudar a identificar seletores errados."""
    log.warning("  ── DIAGNÓSTICO DA PÁGINA ──")

    # Verifica se #surveys existe
    surveys = driver.find_elements(By.ID, "surveys")
    if not surveys:
        log.warning("  #surveys NÃO encontrado na página.")
        all_tables = driver.find_elements(By.TAG_NAME, "table")
        log.warning("  Tabelas encontradas na página: %d", len(all_tables))
        for t in all_tables:
            tid = t.get_attribute("id") or "(sem id)"
            tcls = t.get_attribute("class") or "(sem class)"
            log.warning("    <table id='%s' class='%s'>", tid, tcls)
    else:
        log.warning("  #surveys encontrado.")

        # Lista todos os h3 dentro de #surveys
        headings = surveys[0].find_elements(By.XPATH, ".//h3")
        log.warning("  h3 encontrados em #surveys (%d):", len(headings))
        for h in headings:
            log.warning("    '%s'", h.text.strip())

        # Lista headers de cada tabela dentro de #surveys
        tables = surveys[0].find_elements(By.TAG_NAME, "table")
        log.warning("  Tabelas dentro de #surveys (%d):", len(tables))
        for idx, t in enumerate(tables):
            headers = [th.text.strip() for th in t.find_elements(By.XPATH, ".//thead//th")]
            log.warning("    Tabela %d — headers: %s", idx + 1, headers)

    # Verifica abas disponíveis
    tabs = driver.find_elements(By.XPATH, "//li[@role='presentation'] | //li[@role='tab']")
    log.warning("  Abas encontradas (%d):", len(tabs))
    for tab in tabs:
        log.warning("    '%s'", tab.text.strip())

    log.warning("  ── FIM DO DIAGNÓSTICO ──")


# ---------------------------------------------------------------------------
# Extração por seção (h3 + tabela dentro de #surveys)
# ---------------------------------------------------------------------------

def _extract_table_section(driver, h3_text: str, needed_columns: list[str]) -> dict:
    """
    Localiza o h3 com h3_text dentro de #surveys e extrai as colunas
    needed_columns da primeira linha da tabela que vem logo após ele.
    A correspondência é feita pelo nome do header — sem índices fixos.
    """
    empty = {col: "" for col in needed_columns}

    # Encontra a primeira tabela após o h3 dentro de #surveys
    xpath = (
        f"(//*[@id='surveys']"
        f"//*[contains(normalize-space(),'{h3_text}')]"
        f"/following::table)[1]"
    )
    try:
        table = driver.find_element(By.XPATH, xpath)
    except NoSuchElementException:
        log.warning("  Seção '%s' não encontrada em #surveys.", h3_text)
        return empty

    # Lê os headers para mapear nome -> índice de coluna
    headers = [
        th.text.strip().lower()
        for th in table.find_elements(By.XPATH, ".//thead//th")
    ]
    if not headers:
        log.warning("  Seção '%s': nenhum header encontrado na tabela.", h3_text)
        return empty

    log.debug("  Seção '%s' — headers encontrados: %s", h3_text, headers)

    # Lê a primeira linha de dados
    rows = table.find_elements(By.XPATH, ".//tbody/tr")
    if not rows:
        log.warning("  Seção '%s': nenhuma linha de dados encontrada.", h3_text)
        return empty

    cells = rows[0].find_elements(By.TAG_NAME, "td")

    result = {}
    for col in needed_columns:
        col_key = col.lower()
        if col_key in headers:
            idx = headers.index(col_key)
            result[col] = cells[idx].text.strip() if idx < len(cells) else ""
        else:
            log.warning("  Seção '%s': coluna '%s' não encontrada. Headers: %s", h3_text, col, headers)
            result[col] = ""

    return result


# ---------------------------------------------------------------------------
# Fluxo principal
# ---------------------------------------------------------------------------

def scrape(url: str) -> list[dict]:
    results = []
    driver = _make_driver()

    try:
        _restore_or_login(driver, url)

        if driver.current_url != url:
            driver.get(url)
            _wait_page(driver)

        products = _collect_product_links(driver)
        total = len(products)
        log.info("%d produto(s) encontrado(s). Iniciando extração...", total)

        for i, (name, href) in enumerate(products, 1):
            log.info("─" * 60)
            log.info("[%d/%d] %s", i, total, name)
            log.info("  URL: %s", href)

            driver.get(href)
            _wait_page(driver)
            _click_overview_tab(driver)

            # AJUSTE: textos exatos dos h3 conforme aparecem na tela
            risk = _extract_table_section(
                driver,
                h3_text="Questionnaire Risk Assessment",
                needed_columns=["Overall Risk", "Responder", "Status", "Completion Date", "Expiration Date"],
            )
            access = _extract_table_section(
                driver,
                h3_text="Questionnaire Access",
                needed_columns=["Responder", "Status", "Completion Date"],
            )

            log.info("  [Risk Assessment]")
            log.info("    Overall Risk    : %s", risk.get("Overall Risk")    or "(vazio)")
            log.info("    Responder       : %s", risk.get("Responder")       or "(vazio)")
            log.info("    Status          : %s", risk.get("Status")          or "(vazio)")
            log.info("    Completion Date : %s", risk.get("Completion Date") or "(vazio)")
            log.info("    Expiration Date : %s", risk.get("Expiration Date") or "(vazio)")

            log.info("  [Access]")
            log.info("    Responder       : %s", access.get("Responder")       or "(vazio)")
            log.info("    Status          : %s", access.get("Status")          or "(vazio)")
            log.info("    Completion Date : %s", access.get("Completion Date") or "(vazio)")

            all_empty = not any([
                risk.get("Overall Risk"), risk.get("Responder"), risk.get("Status"),
                access.get("Responder"), access.get("Status"),
            ])
            if all_empty:
                _diagnose_page(driver)

            results.append({
                "produto":                  name,
                "risk_overall_risk":        risk.get("Overall Risk", ""),
                "risk_responder":           risk.get("Responder", ""),
                "risk_status":              risk.get("Status", ""),
                "risk_completion_date":     risk.get("Completion Date", ""),
                "risk_expiration_date":     risk.get("Expiration Date", ""),
                "access_responder":         access.get("Responder", ""),
                "access_status":            access.get("Status", ""),
                "access_completion_date":   access.get("Completion Date", ""),
            })

            log.info("  Registro %d capturado com sucesso.", i)

            driver.back()
            _wait_page(driver)

        log.info("─" * 60)
        log.info("Extração concluída: %d/%d registro(s) capturado(s).", len(results), total)

    finally:
        _save_cookies(driver, AUTH_STATE_FILE)
        driver.quit()

    return results
