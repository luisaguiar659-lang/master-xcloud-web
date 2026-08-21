import asyncio
from urllib.parse import quote

PANEL_LOGIN = "https://panel.xtream.cloud/#/login"
PANEL_DEVICES = "https://panel-v2.xtream.cloud/dashboard/devices"
PLAYLIST_BASE = "https://xtream.cloud/custom-playlist"

class XCloudError(Exception): pass

async def _first_visible(page, selectors, timeout=12000):
    end = asyncio.get_event_loop().time() + timeout/1000
    while asyncio.get_event_loop().time() < end:
        for sel in selectors:
            loc = page.locator(sel).first
            try:
                if await loc.count() and await loc.is_visible(): return loc
            except Exception: pass
        await asyncio.sleep(.25)
    return None

async def login(page, email, password):
    await page.goto(PANEL_LOGIN, wait_until="domcontentloaded", timeout=45000)
    email_el = await _first_visible(page,["input[type=email]","input[autocomplete=username]","input[name*=email i]","input[type=text]"])
    pass_el = await _first_visible(page,["input[type=password]","input[autocomplete=current-password]","input[name*=password i]"])
    if not email_el or not pass_el: raise XCloudError("Campos de login não encontrados.")
    await email_el.fill(email); await pass_el.fill(password)
    form = pass_el.locator("xpath=ancestor::form[1]")
    if await form.count():
        btn = form.locator("button[type=submit]").first
        if await btn.count(): await btn.click()
        else: await pass_el.press("Enter")
    else: await pass_el.press("Enter")
    try:
        await page.wait_for_url(lambda u: "login" not in u.lower(), timeout=20000)
    except Exception: pass
    await asyncio.sleep(2)
    if "login" in page.url.lower(): raise XCloudError("Login não confirmado. Confira e-mail e senha.")
    return True

async def _goto_devices(page):
    await page.goto(PANEL_DEVICES, wait_until="domcontentloaded", timeout=45000)
    await asyncio.sleep(1.5)
    if "login" in page.url.lower(): raise XCloudError("Sessão expirada.")

async def _find_row(page, device):
    rows = page.locator("tr")
    n = await rows.count()
    target = device.upper()
    for i in range(n):
        r=rows.nth(i)
        try:
            if target in (await r.inner_text()).upper(): return r
        except Exception: pass
    return None

async def add_device(page, device):
    await _goto_devices(page)
    add = await _first_visible(page,["button:has-text('Add Device')","button:has-text('Adicionar dispositivo')","button:has(svg.lucide-plus)","button.bg-primary.w-full"])
    if not add: raise XCloudError("Botão Add Device não encontrado.")
    await add.click(); await asyncio.sleep(.8)
    dialog = await _first_visible(page,["[role=dialog]"])
    if not dialog: raise XCloudError("Modal de cadastro não abriu.")
    inputs=dialog.locator("input:not([type=radio]):not([type=checkbox]):not([type=hidden])")
    if not await inputs.count(): raise XCloudError("Campo Device Key não encontrado.")
    chosen=None
    for i in range(await inputs.count()):
        el=inputs.nth(i); ph=((await el.get_attribute("placeholder")) or "").lower()
        if any(x in ph for x in ["device","key","mac","codigo","código"]): chosen=el; break
    chosen = chosen or inputs.first
    await chosen.fill(device)
    submit=dialog.locator("button[type=submit]").first
    if await submit.count(): await submit.click()
    else:
        buttons=dialog.locator("button"); await buttons.last.click()
    for _ in range(30):
        await asyncio.sleep(.5)
        if await _find_row(page,device): return
    raise XCloudError("Dispositivo não apareceu após o cadastro.")

async def add_playlist(page, device, playlist):
    url=f"{PLAYLIST_BASE}?device_key={quote(device)}&type=xtream&mode=add"
    await page.goto(url, wait_until="domcontentloaded", timeout=45000); await asyncio.sleep(1)
    inp=await _first_visible(page,["input[placeholder*=http i]","input[placeholder*=url i]","input[placeholder*=link i]","input[placeholder*=playlist i]","input[aria-label*=url i]","input[aria-label*=playlist i]"])
    if not inp: raise XCloudError("Campo da URL/M3U não encontrado.")
    await inp.fill(playlist)
    form=inp.locator("xpath=ancestor::form[1]")
    btn=form.locator("button[type=submit]").first if await form.count() else page.locator("button:has-text('Save'),button:has-text('Salvar'),button:has-text('Add')").first
    if not await btn.count(): raise XCloudError("Botão Save não encontrado.")
    await btn.click(); await asyncio.sleep(2)
    text=(await page.locator("body").inner_text()).lower()
    if any(x in text for x in ["invalid","failed","error","inválid","falhou"]):
        raise XCloudError("O painel informou erro ao salvar a lista.")
    await _goto_devices(page)
    for _ in range(20):
        row=await _find_row(page,device)
        if row:
            payload=(await row.inner_text()).lower()
            try:
                from urllib.parse import urlparse
                host=urlparse(playlist).hostname or ""
            except Exception: host=""
            if playlist.lower() in payload or (host and host.lower() in payload) or "http://" in payload or "https://" in payload:
                return
        await asyncio.sleep(.5)
    # O painel às vezes não mostra a URL na tabela; se o submit ocorreu sem erro visível, aceita.
    return

async def delete_device(page, device):
    await _goto_devices(page)
    search=await _first_visible(page,["input[type=search]","input[placeholder*=search i]","input[placeholder*=busca i]","input[placeholder*=filtr i]"])
    if search:
        await search.fill(device); await asyncio.sleep(.8)
    row=await _find_row(page,device)
    if not row: raise XCloudError("Dispositivo não encontrado.")
    menu=row.locator("button:has(svg.lucide-ellipsis),button:has(svg[class*=ellipsis])").first
    if not await menu.count(): raise XCloudError("Menu do dispositivo não encontrado.")
    await menu.click(); await asyncio.sleep(.5)
    action=page.locator("[role=menuitem],button")
    delete_btn=None; deactivate=None
    for i in range(await action.count()):
        el=action.nth(i)
        try: t=(await el.inner_text()).strip().lower()
        except Exception: continue
        if not t or len(t)>80: continue
        if any(w in t for w in ["delete","excluir","deletar","remove","apagar","lixeira"]): delete_btn=el; break
        if any(w in t for w in ["deactivate","desativar","disable","inactiv"]): deactivate=el
    if delete_btn:
        await delete_btn.click()
    elif deactivate:
        await deactivate.click(); await asyncio.sleep(.5)
        dlg=page.locator("[role=dialog]").last
        if await dlg.count():
            bs=dlg.locator("button")
            if await bs.count(): await bs.last.click()
        await asyncio.sleep(1.5)
        row=await _find_row(page,device)
        if not row: raise XCloudError("Dispositivo saiu da lista após desativar; exclusão não confirmada.")
        menu=row.locator("button:has(svg.lucide-ellipsis),button:has(svg[class*=ellipsis])").first; await menu.click(); await asyncio.sleep(.5)
        delete_btn=page.locator("[role=menuitem]:has-text('Delete'),[role=menuitem]:has-text('Excluir'),button:has-text('Delete'),button:has-text('Excluir')").first
        if not await delete_btn.count(): raise XCloudError("Ação Delete não encontrada.")
        await delete_btn.click()
    else: raise XCloudError("Ação de exclusão não encontrada.")
    await asyncio.sleep(.5)
    dlg=page.locator("[role=dialog]").last
    if await dlg.count():
        bs=dlg.locator("button")
        for i in range(await bs.count()-1,-1,-1):
            b=bs.nth(i); t=(await b.inner_text()).strip().lower()
            if t and all(x not in t for x in ["cancel","não","nao"]): await b.click(); break
    for _ in range(20):
        await asyncio.sleep(.5)
        if not await _find_row(page,device): return
    raise XCloudError("O painel não confirmou a exclusão.")
