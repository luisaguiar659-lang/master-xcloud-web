import asyncio
import json
from urllib.parse import quote

PANEL_LOGIN = "https://panel.xtream.cloud/#/login"
PANEL_DEVICES = "https://panel-v2.xtream.cloud/dashboard/devices"
PLAYLIST_BASE = "https://xtream.cloud/custom-playlist"


class XCloudError(Exception):
    pass


HELPERS = r"""
function post(type, code, message) {
  window.__MXCLOUD_EVENT__ = { type, code, message, at: Date.now() };
}
function clickReal(button) {
  try {
    button.dispatchEvent(new PointerEvent('pointerdown', {bubbles:true,cancelable:true}));
    button.dispatchEvent(new PointerEvent('pointerup', {bubbles:true,cancelable:true}));
  } catch(e) {}
  button.click();
}
function setReactInput(input, value) {
  const own = Object.getOwnPropertyDescriptor(input, 'value');
  const proto = Object.getPrototypeOf(input);
  const pd = Object.getOwnPropertyDescriptor(proto, 'value');
  if (pd && pd.set && (!own || own.set !== pd.set)) pd.set.call(input, value);
  else if (own && own.set) own.set.call(input, value);
  else input.value = value;
  input.dispatchEvent(new Event('input', {bubbles:true}));
  input.dispatchEvent(new Event('change', {bubbles:true}));
  if (input._valueTracker) {
    input._valueTracker.setValue('');
    input.dispatchEvent(new Event('input', {bubbles:true}));
  }
}
"""


async def _wait_event(page, success_codes, timeout=20000):
    end = asyncio.get_running_loop().time() + timeout / 1000
    last = None
    while asyncio.get_running_loop().time() < end:
        try:
            event = await page.evaluate("window.__MXCLOUD_EVENT__ || null")
        except Exception:
            event = None

        if event and event != last:
            last = event
            typ = str(event.get("type", ""))
            code = str(event.get("code", ""))
            msg = str(event.get("message", code))
            if typ == "error":
                raise XCloudError(msg)
            if typ == "success" and code in success_codes:
                return event

        await asyncio.sleep(0.10)

    raise XCloudError("Tempo limite da automação excedido.")


async def _run_js(page, js, success_codes, timeout=20000):
    await page.evaluate("window.__MXCLOUD_EVENT__ = null")
    await page.evaluate(js)
    return await _wait_event(page, set(success_codes), timeout)


async def login(page, email, password):
    await page.goto(PANEL_LOGIN, wait_until="domcontentloaded", timeout=45000)

    js = f"""
    (() => {{
      const EMAIL={json.dumps(email)};
      const PASSWORD={json.dumps(password)};
      {HELPERS}
      let attempts=0;
      const timer=setInterval(() => {{
        attempts++;
        const inputs=[...document.querySelectorAll('input')];
        const emailInput=
          inputs.find(i=>i.type==='email') ||
          inputs.find(i=>/email|e-mail|user|usuario/i.test(i.name||'')) ||
          inputs.find(i=>/email|e-mail|usuario|usuário/i.test(i.placeholder||'')) ||
          inputs.find(i=>/username|email/i.test(i.autocomplete||'')) ||
          inputs.find(i=>i.type==='text');
        const passInput=
          inputs.find(i=>i.type==='password') ||
          inputs.find(i=>/password|senha/i.test(i.name||'')) ||
          inputs.find(i=>/password|senha/i.test(i.placeholder||'')) ||
          inputs.find(i=>/current-password|password/i.test(i.autocomplete||''));

        if(!emailInput || !passInput) {{
          if(attempts>=120) {{
            clearInterval(timer);
            post('error','LOGIN_FIELDS_NOT_FOUND','Campos de login não encontrados.');
          }}
          return;
        }}

        clearInterval(timer);
        setReactInput(emailInput,EMAIL);
        setReactInput(passInput,PASSWORD);
        const form=passInput.closest('form')||emailInput.closest('form');
        const submit=(form&&form.querySelector('button[type="submit"]')) ||
          [...document.querySelectorAll('button')].find(b=>/login|entrar|sign in/i.test((b.textContent||'').trim()));
        if(form && typeof form.requestSubmit==='function') form.requestSubmit();
        else if(submit) clickReal(submit);
        else if(form) form.submit();
        else {{
          post('error','LOGIN_SUBMIT_NOT_FOUND','Botão de login não encontrado.');
          return;
        }}
        post('success','LOGIN_SUBMITTED','Login enviado.');
      }},100);
    }})()
    """
    await _run_js(page, js, {"LOGIN_SUBMITTED"}, timeout=15000)

    login_confirmed_js = r"""
    () => {
      const url=(window.location.href||'').toLowerCase();
      const body=((document.body&&document.body.innerText)||'').toLowerCase();
      const appText=/dashboard|devices|playlists|reseller|logout|sign out|device key/.test(body);
      return !url.includes('login') || appText;
    }
    """
    try:
        await page.wait_for_function(login_confirmed_js, polling=100, timeout=12000)
    except Exception:
        pass

    state = await page.evaluate(r"""
      () => {
        const url=(window.location.href||'').toLowerCase();
        const body=((document.body&&document.body.innerText)||'').toLowerCase();
        const appText=/dashboard|devices|playlists|reseller|logout|sign out|device key/.test(body);
        return {url, appText};
      }
    """)
    if "login" in state["url"] and not state["appText"]:
        raise XCloudError("Login não confirmado. Confira e-mail e senha.")
    return True


async def _goto_devices(page):
    await page.goto(PANEL_DEVICES, wait_until="domcontentloaded", timeout=45000)
    if "login" in page.url.lower():
        raise XCloudError("Sessão expirada.")

    # Em vez de dormir 1,5 s sempre, libera assim que a tela útil aparece.
    try:
        await page.wait_for_function(r"""
          () => {
            const buttons=[...document.querySelectorAll('button')];
            const plus=document.querySelector('svg.lucide-plus');
            const useful=plus || buttons.some(b=>{
              const t=(b.textContent||'').toLowerCase();
              const c=String(b.className||'');
              return t.includes('add') || t.includes('novo') || c.includes('bg-primary');
            });
            return !!useful;
          }
        """, polling=100, timeout=8000)
    except Exception:
        pass


async def add_device(page, device):
    device = device.strip().upper()
    await _goto_devices(page)

    js = f"""
    (() => {{
      const MAC={json.dumps(device)};
      {HELPERS}
      function findAdd() {{
        const buttons=[...document.querySelectorAll('button')];
        let btn=buttons.find(b=>{{
          const c=String(b.className||'');
          const t=(b.textContent||'').toLowerCase().trim();
          return c.includes('bg-primary') && c.includes('w-full') && (t.includes('add') || t.includes('novo'));
        }});
        if(btn) return btn;
        btn=buttons.find(b=>String(b.className||'').includes('bg-primary') && String(b.className||'').includes('w-full'));
        if(btn) return btn;
        const plus=document.querySelector('svg.lucide-plus');
        if(plus) return plus.closest('button');
        return buttons.find(b=>{{
          const t=(b.textContent||'').toLowerCase().trim();
          return (t.includes('add')&&t.includes('device')) || t==='add' || t.includes('adicionar dispositivo');
        }}) || null;
      }}

      const add=findAdd();
      if(!add) {{ post('error','ADD_DEVICE_BUTTON_NOT_FOUND','Botão Add Device não encontrado.'); return; }}
      clickReal(add);

      let attempts=0;
      const timer=setInterval(()=>{{
        attempts++;
        const dialog=document.querySelector('[role="dialog"]');
        if(!dialog && (attempts===6 || attempts===14)) {{ const again=findAdd(); if(again) clickReal(again); }}
        if(!dialog) {{
          if(attempts>=40) {{ clearInterval(timer); post('error','DEVICE_DIALOG_TIMEOUT','O modal de cadastro não abriu.'); }}
          return;
        }}
        clearInterval(timer);

        const inputs=[...dialog.querySelectorAll('input')];
        let keyInput=inputs.find(i=>{{
          if(['radio','checkbox','hidden'].includes(i.type)) return false;
          const p=(i.placeholder||'').toLowerCase();
          return p.includes('device') || p.includes('key') || p.includes('mac') || p.includes('codigo') || p.includes('código');
        }}) || inputs.find(i=>!['radio','checkbox','hidden'].includes(i.type));
        if(!keyInput) {{ post('error','DEVICE_KEY_INPUT_NOT_FOUND','Campo Device Key não encontrado.'); return; }}
        keyInput.focus(); setReactInput(keyInput,MAC); keyInput.blur();

        setTimeout(()=>{{
          const form=dialog.querySelector('form');
          let submit=form&&form.querySelector('button[type="submit"]');
          if(!submit) submit=[...dialog.querySelectorAll('button')].reverse().find(b=>{{
            const t=(b.textContent||'').toLowerCase().trim();
            return t && !t.includes('cancel') && !t.includes('voltar');
          }});
          if(form && typeof form.requestSubmit==='function') form.requestSubmit();
          else if(submit) clickReal(submit);
          else if(form) form.submit();
          else {{ post('error','DEVICE_SAVE_NOT_FOUND','Botão de salvar não encontrado.'); return; }}

          let wait=0;
          const verify=setInterval(()=>{{
            wait++;
            const found=[...document.querySelectorAll('tr')].some(r=>(r.innerText||'').toUpperCase().includes(MAC));
            if(found) {{ clearInterval(verify); post('success','DEVICE_ADDED','Dispositivo cadastrado e confirmado no painel.'); return; }}

            // Modal fechou: o painel aceitou o submit. Dá um curto período para a tabela atualizar.
            if(!document.querySelector('[role="dialog"]') && wait>=8) {{
              clearInterval(verify);
              post('success','DEVICE_SUBMITTED','Cadastro enviado; confirmando após recarregar.');
              return;
            }}
            if(wait>=60) {{
              clearInterval(verify);
              post('error','DEVICE_ADD_NOT_CONFIRMED','O dispositivo não apareceu no painel após o cadastro.');
            }}
          }},200);
        }},250);
      }},150);
    }})()
    """

    event = await _run_js(page, js, {"DEVICE_ADDED", "DEVICE_SUBMITTED"}, timeout=18000)
    if event["code"] == "DEVICE_ADDED":
        return

    await _goto_devices(page)
    verify_js = f"""
    (() => {{
      const MAC={json.dumps(device)};
      {HELPERS}
      let n=0;
      const timer=setInterval(()=>{{
        n++;
        const found=[...document.querySelectorAll('tr')].some(r=>(r.innerText||'').toUpperCase().includes(MAC));
        if(found) {{ clearInterval(timer); post('success','DEVICE_ADDED','Dispositivo confirmado após recarregar a lista.'); }}
        else if(n>=40) {{ clearInterval(timer); post('error','DEVICE_ADD_NOT_CONFIRMED','O dispositivo não apareceu no painel após o cadastro.'); }}
      }},200);
    }})()
    """
    await _run_js(page, verify_js, {"DEVICE_ADDED"}, timeout=10000)


async def add_playlist(page, device, playlist):
    device = device.strip().upper()
    playlist = playlist.strip()
    url = f"{PLAYLIST_BASE}?device_key={quote(device)}&type=xtream&mode=add"
    await page.goto(url, wait_until="domcontentloaded", timeout=45000)

    js = f"""
    (() => {{
      const URL_LISTA={json.dumps(playlist)};
      {HELPERS}
      let attempts=0;
      const timer=setInterval(()=>{{
        attempts++;
        const inputs=[...document.querySelectorAll('input')];
        const urlInput=inputs.find(i=>{{
          const p=(i.placeholder||'').toLowerCase();
          const a=i.getAttribute('aria-label')||'';
          return p.includes('http') || p.includes('url') || p.includes('link') || p.includes('playlist') || /url|playlist/i.test(a);
        }});
        if(!urlInput) {{
          if(attempts>=60) {{ clearInterval(timer); post('error','PLAYLIST_URL_INPUT_NOT_FOUND','Campo da URL não encontrado.'); }}
          return;
        }}
        clearInterval(timer);
        urlInput.focus(); setReactInput(urlInput,URL_LISTA); urlInput.blur();

        setTimeout(()=>{{
          const form=urlInput.closest('form');
          const buttons=[...document.querySelectorAll('button')];
          const save=(form&&form.querySelector('button[type="submit"]')) || buttons.find(b=>{{
            const t=(b.textContent||'').toLowerCase();
            return t.includes('save') || t.includes('add') || t.includes('salvar') || t.includes('adicionar');
          }});
          if(form && typeof form.requestSubmit==='function') form.requestSubmit();
          else if(save) clickReal(save);
          else if(form) form.submit();
          else {{ post('error','PLAYLIST_SAVE_NOT_FOUND','Botão Save não encontrado.'); return; }}

          let check=0;
          const verify=setInterval(()=>{{
            check++;
            const notices=[...document.querySelectorAll('[role="alert"],[role="status"],.toast,.Toastify__toast,[class*="toast"],[class*="alert"]')];
            const txt=notices.map(n=>(n.innerText||n.textContent||'').toLowerCase()).join(' ');
            if(/invalid|failed|error|required|erro|inválid|falhou/.test(txt)) {{
              clearInterval(verify); post('error','PLAYLIST_SAVE_ERROR','O painel informou erro ao salvar a lista.'); return;
            }}
            if(/success|saved|added|sucesso|salv|adicion/.test(txt)) {{
              clearInterval(verify); post('success','PLAYLIST_ADDED','Lista salva com sucesso.'); return;
            }}
            // Mesmo fallback do fluxo anterior, porém sem esperar 6 segundos fixos.
            if(check>=15) {{
              clearInterval(verify); post('success','PLAYLIST_SUBMITTED','Lista enviada ao painel sem erro visível.');
            }}
          }},200);
        }},200);
      }},150);
    }})()
    """

    await _run_js(page, js, {"PLAYLIST_ADDED", "PLAYLIST_SUBMITTED"}, timeout=15000)
