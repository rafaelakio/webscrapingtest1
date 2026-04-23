"""
Automação de navegação via Selenium.

AJUSTES NECESSÁRIOS:
  Antes de rodar, inspecione o HTML da aplicação (F12 no browser) e ajuste
  os seletores marcados com "# AJUSTE" conforme os atributos reais dos elementos.
  Execute com SLOW_MO=1000 no .env para ver a automação em câmera lenta.
"""
import json
import time
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from config import APP_URL, AUTH_STATE_FILE, SIGLA, SLOW_MO

TIMEOUT = 15  # segundos para esperar elementos


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def _make_driver() -> webdriver.Chrome:
    options = webdriver.ChromeOptions()
    # options.add_argument("--headless=new")  # descomente para rodar sem janela
    options.add_argument("--start-maximized")
    return webdriver.Chrome(options=options)  # Selenium Manager baixa o ChromeDriver automaticamente


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


def _restore_or_login(driver) -> None:
    if Path(AUTH_STATE_FILE).exists():
        _load_cookies(driver, AUTH_STATE_FILE)
        driver.get(APP_URL)
        _wait_page(driver)
        if not _is_login_page(driver.current_url):
            print("Sessão restaurada com sucesso.")
            return
        print("Sessão expirada. Necessário novo login.")

    driver.get(APP_URL)
    _wait_page(driver)

    if _is_login_page(driver.current_url):
        print("\nLogin SSO detectado.")
        print("Complete o login no browser aberto e pressione Enter aqui...")
        input()
        _wait_page(driver)

    _save_cookies(driver, AUTH_STATE_FILE)
    print(f"Cookies salvos em '{AUTH_STATE_FILE}'.")


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
# Navegação
# ---------------------------------------------------------------------------

def _go_to_all_products(driver) -> None:
    wait = WebDriverWait(driver, TIMEOUT)

    # AJUSTE: link "Products" no menu lateral
    wait.until(EC.element_to_be_clickable((By.XPATH,
        "//nav//a[contains(normalize-space(),'Products')]"
        " | //aside//a[contains(normalize-space(),'Products')]"
        " | //*[contains(@class,'sidebar')]//a[contains(normalize-space(),'Products')]"
    ))).click()
    _wait_page(driver)

    # AJUSTE: link "All Products" no submenu
    wait.until(EC.element_to_be_clickable((By.XPATH,
        "//a[contains(normalize-space(),'All Products')]"
    ))).click()
    _wait_page(driver)


def _apply_filter(driver) -> None:
    wait = WebDriverWait(driver, TIMEOUT)

    # AJUSTE: campo Sigla
    sigla = wait.until(EC.presence_of_element_located((By.XPATH,
        "//input[@name='sigla'"
        " or contains(@id,'sigla')"
        " or contains(translate(@placeholder,'SIGLA','sigla'),'sigla')]"
    )))
    sigla.clear()
    sigla.send_keys(SIGLA)

    # AJUSTE: botão Apply Filter
    wait.until(EC.element_to_be_clickable((By.XPATH,
        "//button[contains(normalize-space(),'Apply Filter')]"
        " | //input[@type='submit' and contains(@value,'Apply Filter')]"
        " | //button[contains(normalize-space(),'Filtrar')]"
    ))).click()
    _wait_page(driver)


def _set_pagesize_all(driver) -> None:
    # AJUSTE: combobox pagesize
    try:
        el = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH,
            "//select[@name='pagesize'"
            " or contains(@id,'pagesize')"
            " or contains(@class,'pagesize')]"
        )))
        sel = Select(el)
        for opt in sel.options:
            if opt.text.strip().lower() in ("all", "todos", "tudo"):
                sel.select_by_visible_text(opt.text.strip())
                _wait_page(driver)
                print(f"Pagesize definido para '{opt.text.strip()}'.")
                return
        # Fallback: última opção (geralmente a de maior volume)
        sel.select_by_index(len(sel.options) - 1)
        _wait_page(driver)
    except TimeoutException:
        print("AVISO: combobox 'pagesize' não encontrado. Continuando com paginação padrão.")


# ---------------------------------------------------------------------------
# Coleta dos links da listagem
# ---------------------------------------------------------------------------

def _collect_product_links(driver) -> list[tuple[str, str | None]]:
    # AJUSTE: seletor das linhas e do link de detalhe em cada linha
    rows = driver.find_elements(By.XPATH, "//table//tbody//tr")
    items = []
    for row in rows:
        try:
            link = row.find_element(By.XPATH, ".//td//a")
            items.append((link.text.strip(), link.get_attribute("href")))
        except NoSuchElementException:
            continue
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

    # AJUSTE: labels exatos conforme o HTML
    return {
        "completion_date": _get_field(section, "Completion Date"),
        "expiration_date": _get_field(section, "Expiration Date"),
        "responder":       _get_field(section, "Responder"),
        "status":          _get_field(section, "Status"),
    }


# ---------------------------------------------------------------------------
# Fluxo principal
# ---------------------------------------------------------------------------

def scrape() -> list[dict]:
    results = []
    driver = _make_driver()

    try:
        _restore_or_login(driver)
        _go_to_all_products(driver)
        _apply_filter(driver)
        _set_pagesize_all(driver)

        products = _collect_product_links(driver)
        total = len(products)
        print(f"\n{total} produto(s) encontrado(s). Iniciando extração...\n")

        list_url = driver.current_url

        for i, (name, href) in enumerate(products, 1):
            print(f"[{i}/{total}] {name}")

            if href:
                driver.get(href)
            else:
                # Sem href: volta à lista e clica pelo índice
                driver.get(list_url)
                _wait_page(driver)
                driver.find_elements(By.XPATH, "//table//tbody//tr")[i - 1] \
                    .find_element(By.XPATH, ".//td//a").click()

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
