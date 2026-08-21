import asyncio
from urllib.parse import quote, urlparse

PANEL_LOGIN = "https://panel.xtream.cloud/#/login"
PANEL_DEVICES = "https://panel-v2.xtream.cloud/dashboard/devices"
PLAYLIST_BASE = "https://xtream.cloud/custom-playlist"


class XCloudError(Exception):
    pass


async def _first_visible(page, selectors, timeout=12000):
    end = asyncio.get_event_loop().time() + timeout / 1000
    while asyncio.get_event_loop().time() < end:
        for sel in selectors:
            loc = page.locator(sel).first
            try:
                if await loc.count() and await loc.is_visible():
                    return loc
            except Exception:
                pass
        await asyncio.sleep(0.25)
    return None


async def _body_text(page):
    try:
        return (await page.locator("body").inner_text()).strip()
    except Exception:
        return ""


async def _panel_error(page):
    selectors = [
        "[role=alert]",
        "[data-sonner-toast]",
        ".toast",
        ".Toastify__toast",
        "[class*=toast i]",
        "[class*=alert i]",
    ]
    for sel in selectors:
        loc = page.locator(sel)
        try:
            count = await loc.count()
        except Exception:
            continue

        for i in range(min(count, 8)):
            el = loc.nth(i)
            try:
                if not await el.is_visible():
                    continue
                text = (await el.inner_text()).strip()
            except Exception:
                continue

            low = text.lower()
            if text and any(
                x in low
                for x in [
                    "error",
                    "failed",
                    "invalid",
                    "erro",
                    "falhou",
                    "inválid",
                    "already",
                    "exists",
                    "existente",
                ]
            ):
                return text
    return None


async def login(page, email, password):
    await page.goto(PANEL_LOGIN, wait_until="domcontentloaded", timeout=45000)

    email_el = await _first_visible(
        page,
        [
            "input[type=email]",
            "input[autocomplete=username]",
            "input[name*=email i]",
            "input[type=text]",
        ],
    )
    pass_el = await _first_visible(
        page,
        [
            "input[type=password]",
            "input[autocomplete=current-password]",
            "input[name*=password i]",
        ],
    )

    if not email_el or not pass_el:
        raise XCloudError("Campos de login não encontrados.")

    await email_el.fill(email)
    await pass_el.fill(password)

    form = pass_el.locator("xpath=ancestor::form[1]")
    if await form.count():
        btn = form.locator("button[type=submit]").first
        if await btn.count():
            await btn.click()
        else:
            await pass_el.press("Enter")
    else:
        await pass_el.press("Enter")

    try:
        await page.wait_for_url(lambda u: "login" not in u.lower(), timeout=20000)
    except Exception:
        pass

    await asyncio.sleep(2)

    if "login" in page.url.lower():
        raise XCloudError("Login não confirmado. Confira e-mail e senha.")

    return True


async def _goto_devices(page, reload=False):
    if reload and "dashboard/devices" in page.url:
        await page.reload(wait_until="domcontentloaded", timeout=45000)
    else:
        await page.goto(PANEL_DEVICES, wait_until="domcontentloaded", timeout=45000)

    await asyncio.sleep(1.5)

    if "login" in page.url.lower():
        raise XCloudError("Sessão expirada.")


async def _find_device_element(page, device):
    """
    Procura o device em vários formatos de listagem.
    O painel pode usar tabela, divs/cards ou linhas com role=row.
    """
    target = device.strip().upper()
    if not target:
        return None

    selectors = [
        "tr",
        "[role=row]",
        "[data-row-key]",
        "[data-state]",
        "li",
        "article",
    ]

    for sel in selectors:
        items = page.locator(sel)
        try:
            count = await items.count()
        except Exception:
            continue

        for i in range(min(count, 300)):
            item = items.nth(i)
            try:
                txt = (await item.inner_text()).upper()
            except Exception:
                continue

            if target in txt:
                return item

    # Fallback: busca qualquer texto exato/contendo o device e sobe até um container útil.
    try:
        text_loc = page.get_by_text(device, exact=False).first
        if await text_loc.count() and await text_loc.is_visible():
            for xp in [
                "xpath=ancestor::tr[1]",
                "xpath=ancestor::*[@role='row'][1]",
                "xpath=ancestor::li[1]",
                "xpath=ancestor::article[1]",
                "xpath=ancestor::div[1]",
            ]:
                parent = text_loc.locator(xp)
                if await parent.count():
                    return parent
            return text_loc
    except Exception:
        pass

    return None


async def _search_device(page, device):
    search = await _first_visible(
        page,
        [
            "input[type=search]",
            "input[placeholder*=search i]",
            "input[placeholder*=busca i]",
            "input[placeholder*=filtr i]",
            "input[placeholder*=device i]",
            "input[placeholder*=mac i]",
        ],
        timeout=5000,
    )

    if search:
        try:
            await search.fill("")
            await search.fill(device)
            await asyncio.sleep(1.2)
        except Exception:
            pass

    return await _find_device_element(page, device)


async def add_device(page, device):
    device = device.strip().upper()
    if not device:
        raise XCloudError("Informe o Device Key / MAC.")

    await _goto_devices(page)

    add = await _first_visible(
        page,
        [
            "button:has-text('Add Device')",
            "button:has-text('Adicionar dispositivo')",
            "button:has-text('Adicionar Device')",
            "button:has(svg.lucide-plus)",
            "button.bg-primary.w-full",
        ],
    )
    if not add:
        raise XCloudError("Botão Add Device não encontrado.")

    await add.click()
    await asyncio.sleep(0.8)

    dialog = await _first_visible(page, ["[role=dialog]", "[data-state=open]"], timeout=8000)
    if not dialog:
        raise XCloudError("Modal de cadastro não abriu.")

    inputs = dialog.locator(
        "input:not([type=radio]):not([type=checkbox]):not([type=hidden])"
    )
    if not await inputs.count():
        raise XCloudError("Campo Device Key não encontrado.")

    chosen = None
    for i in range(await inputs.count()):
        el = inputs.nth(i)
        try:
            ph = ((await el.get_attribute("placeholder")) or "").lower()
            name = ((await el.get_attribute("name")) or "").lower()
            aria = ((await el.get_attribute("aria-label")) or "").lower()
        except Exception:
            ph = name = aria = ""

        hint = " ".join([ph, name, aria])
        if any(x in hint for x in ["device", "key", "mac", "codigo", "código"]):
            chosen = el
            break

    chosen = chosen or inputs.first
    await chosen.fill(device)

    submit = dialog.locator("button[type=submit]").first
    if await submit.count():
        await submit.click()
    else:
        buttons = dialog.locator("button")
        if not await buttons.count():
            raise XCloudError("Botão de confirmação do cadastro não encontrado.")
        await buttons.last.click()

    # Dá tempo para a requisição terminar e verifica mensagens de erro do painel.
    await asyncio.sleep(1.5)

    err = await _panel_error(page)
    if err:
        raise XCloudError(f"Painel recusou o cadastro: {err}")

    # 1) Tenta localizar na tela atual.
    for _ in range(10):
        found = await _find_device_element(page, device)
        if found:
            return
        await asyncio.sleep(0.5)

    # 2) Reabre a listagem para forçar atualização.
    await _goto_devices(page, reload=True)

    # 3) Usa o campo de busca quando disponível.
    for attempt in range(3):
        found = await _search_device(page, device)
        if found:
            return

        if attempt < 2:
            await asyncio.sleep(1.5)
            await _goto_devices(page, reload=True)

    # 4) Último fallback: verifica se o texto aparece em qualquer lugar da página.
    body = (await _body_text(page)).upper()
    if device in body:
        return

    raise XCloudError(
        "Cadastro foi enviado, mas o dispositivo ainda não apareceu na lista. "
        "Atualize o painel e confirme se ele foi criado."
    )


async def add_playlist(page, device, playlist):
    device = device.strip().upper()
    playlist = playlist.strip()

    url = f"{PLAYLIST_BASE}?device_key={quote(device)}&type=xtream&mode=add"
    await page.goto(url, wait_until="domcontentloaded", timeout=45000)
    await asyncio.sleep(1)

    inp = await _first_visible(
        page,
        [
            "input[placeholder*=http i]",
            "input[placeholder*=url i]",
            "input[placeholder*=link i]",
            "input[placeholder*=playlist i]",
            "input[aria-label*=url i]",
            "input[aria-label*=playlist i]",
        ],
    )
    if not inp:
        raise XCloudError("Campo da URL/M3U não encontrado.")

    await inp.fill(playlist)

    form = inp.locator("xpath=ancestor::form[1]")
    if await form.count():
        btn = form.locator("button[type=submit]").first
    else:
        btn = page.locator(
            "button:has-text('Save'),"
            "button:has-text('Salvar'),"
            "button:has-text('Add'),"
            "button:has-text('Adicionar')"
        ).first

    if not await btn.count():
        raise XCloudError("Botão Save não encontrado.")

    await btn.click()
    await asyncio.sleep(2)

    err = await _panel_error(page)
    if err:
        raise XCloudError(f"O painel informou erro ao salvar a lista: {err}")

    text = (await _body_text(page)).lower()
    if any(x in text for x in ["invalid", "failed", "error", "inválid", "falhou"]):
        raise XCloudError("O painel informou erro ao salvar a lista.")

    await _goto_devices(page)

    for _ in range(20):
        row = await _search_device(page, device)
        if row:
            try:
                payload = (await row.inner_text()).lower()
            except Exception:
                payload = ""

            try:
                host = urlparse(playlist).hostname or ""
            except Exception:
                host = ""

            if (
                playlist.lower() in payload
                or (host and host.lower() in payload)
                or "http://" in payload
                or "https://" in payload
            ):
                return

        await asyncio.sleep(0.5)

    # Alguns painéis não exibem a URL na listagem.
    # Se o submit não apresentou erro, considera concluído.
    return


async def delete_device(page, device):
    device = device.strip().upper()
    await _goto_devices(page)

    row = await _search_device(page, device)
    if not row:
        raise XCloudError("Dispositivo não encontrado.")

    menu = row.locator(
        "button:has(svg.lucide-ellipsis),"
        "button:has(svg[class*=ellipsis]),"
        "button[aria-haspopup=menu]"
    ).first

    if not await menu.count():
        raise XCloudError("Menu do dispositivo não encontrado.")

    await menu.click()
    await asyncio.sleep(0.5)

    action = page.locator("[role=menuitem],button")
    delete_btn = None
    deactivate = None

    for i in range(await action.count()):
        el = action.nth(i)
        try:
            t = (await el.inner_text()).strip().lower()
        except Exception:
            continue

        if not t or len(t) > 80:
            continue

        if any(w in t for w in ["delete", "excluir", "deletar", "remove", "apagar", "lixeira"]):
            delete_btn = el
            break

        if any(w in t for w in ["deactivate", "desativar", "disable", "inactiv"]):
            deactivate = el

    if delete_btn:
        await delete_btn.click()

    elif deactivate:
        await deactivate.click()
        await asyncio.sleep(0.5)

        dlg = page.locator("[role=dialog]").last
        if await dlg.count():
            bs = dlg.locator("button")
            if await bs.count():
                await bs.last.click()

        await asyncio.sleep(1.5)
        row = await _search_device(page, device)

        if not row:
            raise XCloudError(
                "Dispositivo saiu da lista após desativar; exclusão não confirmada."
            )

        menu = row.locator(
            "button:has(svg.lucide-ellipsis),"
            "button:has(svg[class*=ellipsis]),"
            "button[aria-haspopup=menu]"
        ).first

        await menu.click()
        await asyncio.sleep(0.5)

        delete_btn = page.locator(
            "[role=menuitem]:has-text('Delete'),"
            "[role=menuitem]:has-text('Excluir'),"
            "button:has-text('Delete'),"
            "button:has-text('Excluir')"
        ).first

        if not await delete_btn.count():
            raise XCloudError("Ação Delete não encontrada.")

        await delete_btn.click()

    else:
        raise XCloudError("Ação de exclusão não encontrada.")

    await asyncio.sleep(0.5)

    dlg = page.locator("[role=dialog]").last
    if await dlg.count():
        bs = dlg.locator("button")
        for i in range(await bs.count() - 1, -1, -1):
            b = bs.nth(i)
            try:
                t = (await b.inner_text()).strip().lower()
            except Exception:
                continue

            if t and all(x not in t for x in ["cancel", "não", "nao"]):
                await b.click()
                break

    for attempt in range(3):
        await asyncio.sleep(1)
        await _goto_devices(page, reload=True)
        if not await _search_device(page, device):
            return

    raise XCloudError("O painel não confirmou a exclusão.")
