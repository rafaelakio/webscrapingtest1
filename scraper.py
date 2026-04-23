"""
Automação de navegação via Playwright.

AJUSTES NECESSÁRIOS:
  Antes de rodar, inspecione o HTML da aplicação (F12 no browser) e ajuste
  os seletores marcados com "# AJUSTE" conforme os atributos reais dos elementos.
  Execute com SLOW_MO=500 no .env para ver a automação em câmera lenta.
"""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright, Page, BrowserContext

from config import APP_URL, AUTH_STATE_FILE, SIGLA, SLOW_MO


# ---------------------------------------------------------------------------
# Autenticação
# ---------------------------------------------------------------------------

def _is_login_page(url: str) -> bool:
    return any(k in url.lower() for k in ("login", "sso", "auth", "signin", "adfs"))


async def _restore_or_login(browser) -> tuple[BrowserContext, Page]:
    if Path(AUTH_STATE_FILE).exists():
        ctx = await browser.new_context(storage_state=AUTH_STATE_FILE)
        page = await ctx.new_page()
        await page.goto(APP_URL, wait_until="networkidle")
        if not _is_login_page(page.url):
            print("Sessão restaurada com sucesso.")
            return ctx, page
        print("Sessão expirada. Necessário novo login.")
        await ctx.close()

    ctx = await browser.new_context()
    page = await ctx.new_page()
    await page.goto(APP_URL, wait_until="networkidle")

    if _is_login_page(page.url):
        print("\nLogin SSO detectado.")
        print("Por favor, complete o login no browser aberto e pressione Enter aqui...")
        await asyncio.get_event_loop().run_in_executor(None, input)
        await page.wait_for_load_state("networkidle")

    await ctx.storage_state(path=AUTH_STATE_FILE)
    print(f"Estado de autenticação salvo em '{AUTH_STATE_FILE}'.")
    return ctx, page


# ---------------------------------------------------------------------------
# Navegação
# ---------------------------------------------------------------------------

async def _go_to_all_products(page: Page) -> None:
    # AJUSTE: selecione o item "Products" no menu lateral
    # Inspecione o elemento e troque o seletor se necessário.
    await page.locator(".sidebar a:has-text('Products'), nav a:has-text('Products'), aside a:has-text('Products')").first.click()
    await page.wait_for_load_state("networkidle")

    # AJUSTE: selecione o submenu "All Products"
    await page.locator("a:has-text('All Products')").first.click()
    await page.wait_for_load_state("networkidle")


async def _apply_filter(page: Page) -> None:
    # AJUSTE: seletor do campo "Sigla" — inspecione o name, id ou placeholder do input
    sigla_input = page.locator(
        "input[name='sigla'], input[id*='sigla'], input[placeholder*='igla']"
    ).first
    await sigla_input.clear()
    await sigla_input.fill(SIGLA)

    # AJUSTE: seletor do botão Apply Filter
    await page.locator(
        "button:has-text('Apply Filter'), input[value*='Apply Filter'], button:has-text('Filtrar')"
    ).first.click()
    await page.wait_for_load_state("networkidle")


async def _set_pagesize_all(page: Page) -> None:
    # AJUSTE: seletor do combobox "pagesize"
    pagesize = page.locator(
        "select[name='pagesize'], select[id*='pagesize'], select.pagesize"
    ).first

    if await pagesize.count() == 0:
        print("AVISO: combobox 'pagesize' não encontrado. Continuando com a paginação padrão.")
        return

    # Tenta selecionar a opção "All" por label ou por valor comum
    for value in ("All", "all", "-1", "0", "999999"):
        try:
            await pagesize.select_option(label=value)
            await page.wait_for_load_state("networkidle")
            print(f"Pagesize definido para '{value}'.")
            return
        except Exception:
            pass

    # Fallback: dropdown customizado (jQuery/Select2)
    try:
        await pagesize.click()
        await page.locator("li:has-text('All'), option:has-text('All')").first.click()
        await page.wait_for_load_state("networkidle")
    except Exception:
        print("AVISO: não foi possível selecionar 'All' no pagesize.")


# ---------------------------------------------------------------------------
# Coleta de links da listagem
# ---------------------------------------------------------------------------

async def _collect_product_links(page: Page) -> list[tuple[str, str | None]]:
    # AJUSTE: seletor das linhas e do link de detalhe dentro de cada linha
    rows = await page.locator("table tbody tr").all()
    items = []
    for row in rows:
        link = row.locator("td a").first
        if await link.count() == 0:
            continue
        name = (await link.inner_text()).strip()
        href = await link.get_attribute("href")
        items.append((name, href))
    return items


# ---------------------------------------------------------------------------
# Extração de dados do detalhe
# ---------------------------------------------------------------------------

async def _get_field(page: Page, section_locator, label: str) -> str:
    """Tenta extrair o valor de um campo pelo seu label dentro de uma seção."""
    for selector in (
        f"th:has-text('{label}') + td",
        f"td:has-text('{label}') + td",
        f"dt:has-text('{label}') + dd",
        f"label:has-text('{label}') + *",
        f"strong:has-text('{label}') ~ span",
    ):
        try:
            cell = section_locator.locator(selector).first
            if await cell.count():
                return (await cell.inner_text()).strip()
        except Exception:
            pass
    return ""


async def _extract_questionnaire(page: Page, section_title: str) -> dict:
    # AJUSTE: padrão do bloco/seção — Bootstrap usa .panel ou .card com heading
    section = page.locator(
        f".panel:has(.panel-heading:has-text('{section_title}')), "
        f".card:has(.card-header:has-text('{section_title}')), "
        f".box:has(.box-title:has-text('{section_title}')), "
        f"fieldset:has(legend:has-text('{section_title}'))"
    ).first

    if await section.count() == 0:
        print(f"  AVISO: seção '{section_title}' não encontrada na página.")
        return {k: "" for k in ("completion_date", "expiration_date", "responder", "status")}

    # AJUSTE: nomes exatos dos labels conforme o HTML
    return {
        "completion_date": await _get_field(page, section, "Completion Date"),
        "expiration_date": await _get_field(page, section, "Expiration Date"),
        "responder":       await _get_field(page, section, "Responder"),
        "status":          await _get_field(page, section, "Status"),
    }


# ---------------------------------------------------------------------------
# Fluxo principal
# ---------------------------------------------------------------------------

async def scrape() -> list[dict]:
    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=SLOW_MO)
        ctx, page = await _restore_or_login(browser)

        try:
            await _go_to_all_products(page)
            await _apply_filter(page)
            await _set_pagesize_all(page)

            products = await _collect_product_links(page)
            total = len(products)
            print(f"\n{total} produto(s) encontrado(s). Iniciando extração...\n")

            list_url = page.url

            for i, (name, href) in enumerate(products, 1):
                print(f"[{i}/{total}] {name}")

                if href:
                    await page.goto(href, wait_until="networkidle")
                else:
                    # Sem href: navega de volta à lista e clica pelo índice
                    await page.goto(list_url, wait_until="networkidle")
                    await page.locator("table tbody tr").nth(i - 1).locator("td a").first.click()
                    await page.wait_for_load_state("networkidle")

                # AJUSTE: títulos exatos das seções conforme aparecem na tela
                risk   = await _extract_questionnaire(page, "Risk Assessment")
                access = await _extract_questionnaire(page, "Access")

                results.append({
                    "produto":               name,
                    "risk_completion_date":  risk["completion_date"],
                    "risk_expiration_date":  risk["expiration_date"],
                    "risk_responder":        risk["responder"],
                    "risk_status":           risk["status"],
                    "access_completion_date": access["completion_date"],
                    "access_expiration_date": access["expiration_date"],
                    "access_responder":       access["responder"],
                    "access_status":          access["status"],
                })

                await page.go_back(wait_until="networkidle")

        finally:
            await ctx.storage_state(path=AUTH_STATE_FILE)
            await browser.close()

    return results
