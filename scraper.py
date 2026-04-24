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
    """Clica no <a> da aba Overview e aguarda o conteúdo dos painéis carregar."""
    try:
        tab_link = WebDriverWait(driver, TIMEOUT).until(
            EC.element_to_be_clickable((By.XPATH,
                "//li[@role='presentation' and .//span[contains(normalize-space(),'Overview')]]//a"
                " | //li[@role='tab' and .//span[contains(normalize-space(),'Overview')]]//a"
                " | //a[contains(normalize-space(),'Overview') and ancestor::li[@role]]"
            ))
        )
        tab_link.click()
        log.debug("  Clique na aba 'Overview' realizado.")

        # Aguarda qualquer tabela dentro de um panel-body aparecer
        WebDriverWait(driver, TIMEOUT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".panel-body table"))
        )
        log.debug("  Conteúdo dos painéis carregado.")

    except TimeoutException:
        log.warning("  Aba 'Overview' não respondeu ou painéis não carregaram após o clique.")


# ---------------------------------------------------------------------------
# Diagnóstico da página de detalhe
# ---------------------------------------------------------------------------

def _diagnose_page(driver) -> None:
    """Loga a estrutura encontrada na página para ajudar a identificar seletores errados."""
    log.warning("  ── DIAGNÓSTICO DA PÁGINA ──")

    # Painéis Bootstrap com heading
    panels = driver.find_elements(By.XPATH, "//div[contains(@class,'panel')]")
    log.warning("  Painéis (.panel) encontrados: %d", len(panels))
    for panel in panels:
        headings = panel.find_elements(By.XPATH, ".//*[self::h1 or self::h2 or self::h3 or self::h4]")
        heading_text = headings[0].text.strip() if headings else "(sem heading)"
        tables = panel.find_elements(By.TAG_NAME, "table")
        table_ids = [t.get_attribute("id") or "(sem id)" for t in tables]
        headers = []
        if tables:
            headers = [th.text.strip() for th in tables[0].find_elements(By.XPATH, ".//thead//th")]
        log.warning("    Painel: '%s' | tabelas: %s | headers: %s", heading_text, table_ids, headers)

    # Abas disponíveis
    tabs = driver.find_elements(By.XPATH, "//li[@role='presentation'] | //li[@role='tab']")
    log.warning("  Abas encontradas (%d):", len(tabs))
    for tab in tabs:
        log.warning("    '%s'", tab.text.strip())

    log.warning("  ── FIM DO DIAGNÓSTICO ──")


# ---------------------------------------------------------------------------
# Extração de campos da página de detalhe
# ---------------------------------------------------------------------------

def _extract_product_name(driver) -> str:
    """Tenta extrair o nome do produto do heading principal da página de detalhe."""
    for xpath in ("//h1", "//h2", "//*[contains(@class,'product-name')]"):
        els = driver.find_elements(By.XPATH, xpath)
        if els:
            text = els[0].text.strip()
            if text:
                return text
    return ""


def _extract_metadata_field(driver, field_name: str) -> str:
    """
    Extrai o valor de um campo de metadados pelo label em <strong>.
    Estrutura: <td><strong>Label</strong></td><td>valor ou <a href>valor</a></td>
    """
    try:
        cell = driver.find_element(By.XPATH,
            f"//td[.//strong[contains(normalize-space(),'{field_name}')]]/following-sibling::td[1]"
        )
        # Se o valor estiver num link, prefere o href; caso contrário usa o texto visível
        links = cell.find_elements(By.TAG_NAME, "a")
        if links:
            return (links[0].get_attribute("href") or links[0].text).strip()
        return cell.text.strip()
    except NoSuchElementException:
        log.warning("  Campo '%s' não encontrado na página.", field_name)
        return ""


# ---------------------------------------------------------------------------
# Extração por seção (panel-heading + panel-body > table)
# ---------------------------------------------------------------------------

def _extract_table_section(driver, h3_text: str, needed_columns: list[str]) -> dict:
    """
    Localiza o painel Bootstrap cujo heading contém h3_text e extrai
    needed_columns da primeira linha da tabela no panel-body.
    Correspondência feita pelo nome do header — sem índices fixos.
    """
    empty = {col: "" for col in needed_columns}

    # Estrutura real: div.panel > div.panel-heading (com h3) + div.panel-body > table
    xpath = (
        f"//div[contains(@class,'panel') and "
        f".//*[contains(normalize-space(),'{h3_text}')]]"
        f"//div[contains(@class,'panel-body')]//table"
    )
    try:
        table = driver.find_element(By.XPATH, xpath)
    except NoSuchElementException:
        log.warning("  Seção '%s' não encontrada (panel-heading).", h3_text)
        return empty

    # Lê os headers para mapear nome -> índice de coluna
    headers = [
        th.text.strip().lower()
        for th in table.find_elements(By.XPATH, ".//thead//th")
    ]
    if not headers:
        log.warning("  Seção '%s': nenhum header encontrado.", h3_text)
        return empty

    log.debug("  Seção '%s' — headers: %s", h3_text, headers)

    # Lê a primeira linha de dados
    rows = table.find_elements(By.XPATH, ".//tbody/tr")
    if not rows:
        log.warning("  Seção '%s': nenhuma linha de dados.", h3_text)
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
            log.info("-" * 60)
            log.info("[%d/%d] %s", i, total, name)
            log.info("  URL: %s", href)

            driver.get(href)
            _wait_page(driver)
            _click_overview_tab(driver)

            # Nome do produto: fallback para o heading da página se o link da lista vier vazio
            produto   = name or _extract_product_name(driver)
            sigla_app = _extract_metadata_field(driver, "Sigla app")
            repox     = _extract_metadata_field(driver, "REPOX")

            # AJUSTE: textos exatos dos h3/panel-heading conforme aparecem na tela
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

            log.info("  Sigla app       : %s", sigla_app or "(vazio)")
            log.info("  REPOX           : %s", repox     or "(vazio)")
            log.info("  Produto         : %s", produto   or "(vazio)")
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
                "produto":                  produto,
                "sigla_app":                sigla_app,
                "repox":                    repox,
                "url":                      href,
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

        log.info("-" * 60)
        log.info("Extração concluída: %d/%d registro(s) capturado(s).", len(results), total)

    finally:
        _save_cookies(driver, AUTH_STATE_FILE)
        driver.quit()

    return results
