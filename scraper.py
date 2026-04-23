"""
Automação de navegação via Selenium.

AJUSTES NECESSÁRIOS:
  Seletores marcados com "# AJUSTE" devem ser conferidos com F12 no browser.
  Execute com SLOW_MO=1000 no .env para ver a automação em câmera lenta.
"""
import json
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
            print("Sessão restaurada com sucesso.")
            return
        print("Sessão expirada. Necessário novo login.")

    driver.get(target_url)
    _wait_page(driver)

    if _is_login_page(driver.current_url):
        print("\nLogin SSO detectado.")
        print("Complete o login no browser aberto e pressione Enter aqui...")
        input()
        _wait_page(driver)

    _save_cookies(driver, AUTH_STATE_FILE)
    print(f"Cookies salvos em '{AUTH_STATE_FILE}'.\n")


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
        raise RuntimeError("Tabela 'table#products' não encontrada na página. Verifique a URL informada.")

    # AJUSTE: se o link de detalhe não for o primeiro <a> da linha, ajuste o seletor
    links = driver.find_elements(By.CSS_SELECTOR, "table#products tbody tr td a")
    items = []
    for link in links:
        href = link.get_attribute("href")
        name = link.text.strip()
        if href:
            items.append((name, href))
    return items


# ---------------------------------------------------------------------------
# Extração de dados do detalhe
# ---------------------------------------------------------------------------

def _get_field(section, label: str) -> str:
    for xpath in (
        f".//th[contains(normalize-space(),'{label}')]/following-sibling::td[1]",
        f".//td[contains(normalize-space(),'{label}')]/following-sibling::td[1]",
        f".//dt[contains(normalize-space(),'{label}')]/following-sibling::dd[1]",
        f".//label[contains(normalize-space(),'{label}')]/following-sibling::*[1]",
        f".//strong[contains(normalize-space(),'{label}')]/following-sibling::span[1]",
    ):
        try:
            el = section.find_element(By.XPATH, xpath)
            return el.text.strip()
        except NoSuchElementException:
            continue
    return ""


def _extract_questionnaire(driver, section_title: str) -> dict:
    # AJUSTE: padrão do bloco/seção Bootstrap (panel, card, box, fieldset)
    xpath = (
        f"//*[contains(@class,'panel') and .//*[contains(normalize-space(),'{section_title}')]]"
        f" | //*[contains(@class,'card') and .//*[contains(normalize-space(),'{section_title}')]]"
        f" | //*[contains(@class,'box') and .//*[contains(normalize-space(),'{section_title}')]]"
        f" | //fieldset[.//legend[contains(normalize-space(),'{section_title}')]]"
    )
    try:
        section = driver.find_element(By.XPATH, xpath)
    except NoSuchElementException:
        print(f"  AVISO: seção '{section_title}' não encontrada na página.")
        return {k: "" for k in ("completion_date", "expiration_date", "responder", "status")}

    # AJUSTE: labels exatos conforme o HTML da página de detalhe
    return {
        "completion_date": _get_field(section, "Completion Date"),
        "expiration_date": _get_field(section, "Expiration Date"),
        "responder":       _get_field(section, "Responder"),
        "status":          _get_field(section, "Status"),
    }


# ---------------------------------------------------------------------------
# Fluxo principal
# ---------------------------------------------------------------------------

def scrape(url: str) -> list[dict]:
    results = []
    driver = _make_driver()

    try:
        _restore_or_login(driver, url)

        # Garante que está na URL correta após o login
        if driver.current_url != url:
            driver.get(url)
            _wait_page(driver)

        products = _collect_product_links(driver)
        total = len(products)
        print(f"{total} produto(s) encontrado(s). Iniciando extração...\n")

        for i, (name, href) in enumerate(products, 1):
            print(f"[{i}/{total}] {name}")
            driver.get(href)
            _wait_page(driver)

            # AJUSTE: títulos exatos das seções conforme aparecem na tela
            risk   = _extract_questionnaire(driver, "Risk Assessment")
            access = _extract_questionnaire(driver, "Access")

            results.append({
                "produto":                name,
                "risk_completion_date":   risk["completion_date"],
                "risk_expiration_date":   risk["expiration_date"],
                "risk_responder":         risk["responder"],
                "risk_status":            risk["status"],
                "access_completion_date": access["completion_date"],
                "access_expiration_date": access["expiration_date"],
                "access_responder":       access["responder"],
                "access_status":          access["status"],
            })

            driver.back()
            _wait_page(driver)

    finally:
        _save_cookies(driver, AUTH_STATE_FILE)
        driver.quit()

    return results
