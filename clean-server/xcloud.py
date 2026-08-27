import asyncio
import json
from urllib.parse import quote

PANEL_LOGIN = "https://panel.xtream.cloud/#/login"
PANEL_DEVICES = "https://panel-v2.xtream.cloud/dashboard/devices"
PLAYLIST_BASE = "https://xtream.cloud/custom-playlist"


class XCloudError(Exception):
    pass


HELPERS = r'''
function post(type,code,message){
  window.__MXCLOUD_EVENT__={type,code,message,at:Date.now()};
}
function clickReal(button){
  try{
    button.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,cancelable:true}));
    button.dispatchEvent(new PointerEvent('pointerup',{bubbles:true,cancelable:true}));
  }catch(e){}
  button.click();
}
function setReactInput(input,value){
  const own=Object.getOwnPropertyDescriptor(input,'value');
  const proto=Object.getPrototypeOf(input);
  const pd=Object.getOwnPropertyDescriptor(proto,'value');
  if(pd&&pd.set&&(!own||own.set!==pd.set)){pd.set.call(input,value);}
  else if(own&&own.set){own.set.call(input,value);}
  else{input.value=value;}
  input.dispatchEvent(new Event('input',{bubbles:true}));
  input.dispatchEvent(new Event('change',{bubbles:true}));
  if(input._valueTracker){
    input._valueTracker.setValue('');
    input.dispatchEvent(new Event('input',{bubbles:true}));
  }
}
'''


async def _wait_event(page, success_codes, timeout=30000, progress_codes=None):
    success_codes = set(success_codes)
    progress_codes = set(progress_codes or [])
    deadline = asyncio.get_running_loop().time() + timeout / 1000
    last = None
    while asyncio.get_running_loop().time() < deadline:
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
            if typ == "progress" and code in progress_codes:
                return event
        await asyncio.sleep(0.10)
    raise XCloudError("Tempo limite da automação excedido.")


async def _run_js(page, js, success_codes, timeout=30000, progress_codes=None):
    await page.evaluate("window.__MXCLOUD_EVENT__ = null")
    await page.evaluate(js)
    return await _wait_event(page, success_codes, timeout, progress_codes)


async def login(page, email, password):
    await page.goto(PANEL_LOGIN, wait_until="load", timeout=45000)
    js = f'''
    (function(){{
      const EMAIL={json.dumps(email)};
      const PASSWORD={json.dumps(password)};
      {HELPERS}
      let attempts=0;
      const timer=setInterval(()=>{{
        attempts++;
        const inputs=[...document.querySelectorAll('input')];
        const emailInput=inputs.find(i=>i.type==='email')
          ||inputs.find(i=>/email|e-mail|user|usuario/i.test(i.name||''))
          ||inputs.find(i=>/email|e-mail|usuario|usuário/i.test(i.placeholder||''))
          ||inputs.find(i=>/username|email/i.test(i.autocomplete||''))
          ||inputs.find(i=>i.type==='text');
        const passInput=inputs.find(i=>i.type==='password')
          ||inputs.find(i=>/password|senha/i.test(i.name||''))
          ||inputs.find(i=>/password|senha/i.test(i.placeholder||''))
          ||inputs.find(i=>/current-password|password/i.test(i.autocomplete||''));
        if(!emailInput||!passInput){{
          if(attempts>=60){{clearInterval(timer);post('error','LOGIN_FIELDS_NOT_FOUND','Campos de login não encontrados.');}}
          return;
        }}
        clearInterval(timer);
        post('progress','LOGIN_FILL','Autenticando no painel...');
        setReactInput(emailInput,EMAIL);
        setReactInput(passInput,PASSWORD);
        const form=passInput.closest('form')||emailInput.closest('form');
        const submit=(form&&form.querySelector('button[type="submit"]'))
          ||[...document.querySelectorAll('button')].find(b=>/login|entrar|sign in/i.test((b.textContent||'').trim()));
        if(form&&typeof form.requestSubmit==='function')form.requestSubmit();
        else if(submit)clickReal(submit);
        else if(form)form.submit();
        post('progress','LOGIN_SUBMITTED','Login enviado.');
      }},500);
    }})();true;
    '''
    await page.evaluate(js)
    try:
        await page.wait_for_function(
            "() => { const u=String(location.href||'').toLowerCase(); return u.includes('/dashboard') && !u.includes('/login') && !u.includes('#/login'); }",
            polling=100,
            timeout=20000,
        )
    except Exception:
        try:
            event = await page.evaluate("window.__MXCLOUD_EVENT__ || null")
            if event and event.get("type") == "error":
                raise XCloudError(str(event.get("message") or "Falha no login."))
        except XCloudError:
            raise
        raise XCloudError("Login não confirmado. Confira e-mail e senha.")
    return True


async def _goto_devices(page):
    await page.goto(PANEL_DEVICES, wait_until="load", timeout=45000)
    if "login" in page.url.lower():
        raise XCloudError("Sessão expirada.")


async def add_device(page, device):
    device = device.strip().upper()
    await _goto_devices(page)
    js = f'''
    (function(){{
      const MAC={json.dumps(device)};
      {HELPERS}
      function findAdd(){{
        const buttons=[...document.querySelectorAll('button')];
        let btn=buttons.find(b=>{{const c=String(b.className||'');const t=(b.textContent||'').toLowerCase().trim();return c.includes('bg-primary')&&c.includes('w-full')&&(t.includes('add')||t.includes('novo'));}});
        if(btn)return btn;
        btn=buttons.find(b=>{{const c=String(b.className||'');return c.includes('bg-primary')&&c.includes('w-full');}});
        if(btn)return btn;
        const plus=document.querySelector('svg.lucide-plus');
        if(plus)return plus.closest('button');
        return buttons.find(b=>{{const t=(b.textContent||'').toLowerCase().trim();return (t.includes('add')&&t.includes('device'))||t==='add'||t.includes('adicionar dispositivo');}})||null;
      }}
      const add=findAdd();
      if(!add){{post('error','ADD_DEVICE_BUTTON_NOT_FOUND','Botão Add Device não encontrado.');return;}}
      post('progress','OPEN_DEVICE_DIALOG','Abrindo cadastro do dispositivo...');clickReal(add);
      let attempts=0;
      const timer=setInterval(()=>{{
        attempts++;
        const dialog=document.querySelector('[role="dialog"]');
        if(!dialog&&(attempts===4||attempts===8)){{const r=findAdd();if(r)clickReal(r);}}
        if(!dialog){{if(attempts>=20){{clearInterval(timer);post('error','DEVICE_DIALOG_TIMEOUT','O modal de cadastro não abriu.');}}return;}}
        clearInterval(timer);post('progress','DEVICE_DIALOG_OPEN','Cadastro aberto.');
        const inputs=[...dialog.querySelectorAll('input')];
        let keyInput=inputs.find(i=>{{if(['radio','checkbox','hidden'].includes(i.type))return false;const p=(i.placeholder||'').toLowerCase();return p.includes('device')||p.includes('key')||p.includes('mac')||p.includes('codigo')||p.includes('código');}});
        keyInput=keyInput||inputs.find(i=>!['radio','checkbox','hidden'].includes(i.type));
        if(!keyInput){{post('error','DEVICE_KEY_INPUT_NOT_FOUND','Campo Device Key não encontrado.');return;}}
        setReactInput(keyInput,MAC);keyInput.blur();post('progress','DEVICE_KEY_FILLED','Device Key preenchida.');
        setTimeout(()=>{{
          const form=dialog.querySelector('form');
          let submit=form&&form.querySelector('button[type="submit"]');
          if(!submit)submit=[...dialog.querySelectorAll('button')].reverse().find(b=>{{const t=(b.textContent||'').toLowerCase().trim();return t&&!t.includes('cancel')&&!t.includes('voltar');}});
          post('progress','DEVICE_SAVING','Salvando dispositivo...');
          if(form&&typeof form.requestSubmit==='function')form.requestSubmit();
          else if(submit)clickReal(submit);
          else if(form)form.submit();
          else{{post('error','DEVICE_SAVE_NOT_FOUND','Botão de salvar não encontrado.');return;}}
          let wait=0, verifyingShown=false;
          const close=setInterval(()=>{{
            wait++;
            const rows=[...document.querySelectorAll('tr')];
            const found=rows.some(r=>(r.innerText||'').toUpperCase().includes(MAC.toUpperCase()));
            if(found){{clearInterval(close);post('success','DEVICE_ADDED','Dispositivo cadastrado e confirmado no painel.');return;}}
            const open=document.querySelector('[role="dialog"]');
            if(!open&&!verifyingShown){{verifyingShown=true;post('progress','DEVICE_VERIFYING','Confirmando cadastro no painel...');}}
            if(wait>=40){{clearInterval(close);post('error','DEVICE_ADD_NOT_CONFIRMED','O dispositivo não apareceu no painel após o cadastro.');}}
          }},500);
        }},1200);
      }},500);
    }})();true;
    '''
    await _run_js(page, js, {"DEVICE_ADDED"}, timeout=36000)


async def _verify_playlist_in_devices(page, device, playlist):
    await _goto_devices(page)
    js = f'''
    (function(){{
      const MAC={json.dumps(device)};
      const URL_LISTA={json.dumps(playlist)};
      {HELPERS}
      function rowPayload(row){{let out=(row.innerText||row.textContent||'');row.querySelectorAll('*').forEach(el=>{{['title','value','href','aria-label','data-original-title'].forEach(a=>{{const v=el.getAttribute&&el.getAttribute(a);if(v)out+=' '+v;}});}});return out;}}
      let tries=0;
      const verify=setInterval(()=>{{
        tries++;
        const rows=[...document.querySelectorAll('tr')];
        const row=rows.find(r=>rowPayload(r).toUpperCase().includes(MAC.toUpperCase()));
        if(row){{
          const hay=rowPayload(row);let expectedHost='';try{{expectedHost=(new URL(URL_LISTA)).host.toLowerCase();}}catch(e){{}}
          const low=hay.toLowerCase(), exact=hay.includes(URL_LISTA), hostMatch=expectedHost&&low.includes(expectedHost), hasHttp=/http:\/\//i.test(hay);
          if(exact||hostMatch||hasHttp){{clearInterval(verify);post('success','PLAYLIST_ADDED','M3U salva e confirmada na tabela de dispositivos.');return;}}
        }}
        if(tries>=40){{clearInterval(verify);post('error','PLAYLIST_NOT_CONFIRMED','A M3U não apareceu na tabela de dispositivos.');}}
      }},500);
    }})();true;
    '''
    await _run_js(page, js, {"PLAYLIST_ADDED"}, timeout=24000)


async def add_playlist(page, device, playlist):
    device = device.strip().upper(); playlist = playlist.strip()
    url = f"{PLAYLIST_BASE}?device_key={quote(device)}&type=xtream&mode=add"
    await page.goto(url, wait_until="load", timeout=45000)
    js = f'''
    (function(){{
      const MAC={json.dumps(device)};const URL_LISTA={json.dumps(playlist)};
      {HELPERS}
      let attempts=0;
      const timer=setInterval(()=>{{
        attempts++;
        const inputs=[...document.querySelectorAll('input')];
        const urlInput=inputs.find(i=>{{const p=(i.placeholder||'').toLowerCase();const a=i.getAttribute('aria-label')||'';return p.includes('http')||p.includes('url')||p.includes('link')||p.includes('playlist')||/url|playlist/i.test(a);}});
        if(!urlInput){{if(attempts>=30){{clearInterval(timer);post('error','PLAYLIST_URL_INPUT_NOT_FOUND','Campo da URL não encontrado.');}}return;}}
        clearInterval(timer);post('progress','PLAYLIST_FILL','Enviando lista...');urlInput.focus();setReactInput(urlInput,URL_LISTA);urlInput.blur();
        setTimeout(()=>{{
          const form=urlInput.closest('form');const buttons=[...document.querySelectorAll('button')];
          const save=(form&&form.querySelector('button[type="submit"]'))||buttons.find(b=>{{const t=(b.textContent||'').toLowerCase();return t.includes('save')||t.includes('add')||t.includes('salvar');}});
          if(form&&typeof form.requestSubmit==='function')form.requestSubmit();
          else if(save)clickReal(save);
          else if(form)form.submit();
          else{{post('error','PLAYLIST_SAVE_NOT_FOUND','Botão Save não encontrado.');return;}}
          post('progress','PLAYLIST_VERIFYING','Confirmando lista no painel...');
          let check=0;const verify=setInterval(()=>{{
            check++;
            const notices=[...document.querySelectorAll('[role="alert"],[role="status"],.toast,.Toastify__toast,[class*="toast"],[class*="alert"]')];
            const txt=notices.map(n=>(n.innerText||n.textContent||'').toLowerCase()).join(' ');
            const bad=/invalid|failed|error|required|erro|inválid|falhou/.test(txt), good=/success|saved|added|created|sucesso|salv|adicion/.test(txt);
            if(bad){{clearInterval(verify);post('error','PLAYLIST_VISIBLE_ERROR','O painel informou erro ao salvar a lista.');}}
            else if(good){{clearInterval(verify);post('success','PLAYLIST_ADDED','Lista adicionada e confirmada.');}}
            else if(check>=12){{clearInterval(verify);post('progress','PLAYLIST_VERIFY_ON_DEVICES','Verificando a M3U na lista de dispositivos...');}}
          }},500);
        }},900);
      }},500);
    }})();true;
    '''
    event = await _run_js(page, js, {"PLAYLIST_ADDED"}, timeout=30000, progress_codes={"PLAYLIST_VERIFY_ON_DEVICES"})
    if event.get("code") == "PLAYLIST_VERIFY_ON_DEVICES":
        await _verify_playlist_in_devices(page, device, playlist)


async def delete_device(page, device):
    device = device.strip().upper()
    await _goto_devices(page)
    js = f'''
    (function(){{
      const MAC={json.dumps(device)};const DIRECT=false;
      {HELPERS}
      function findRow(){{return [...document.querySelectorAll('tr')].find(r=>(r.innerText||'').toUpperCase().includes(MAC.toUpperCase()));}}
      function menuButton(row){{const icon=row.querySelector('svg.lucide-ellipsis')||row.querySelector('svg[class*="ellipsis"]');return icon?icon.closest('button'):null;}}
      function action(words){{const els=[...document.querySelectorAll('[role="menuitem"]'),...document.querySelectorAll('button')];return els.find(e=>{{const t=(e.textContent||'').trim().toLowerCase();return t&&t.length<80&&words.some(w=>t.includes(w));}})||null;}}
      function verifyDeleted(){{post('progress','DELETE_VERIFYING','Confirmando exclusão...');let n=0;const v=setInterval(()=>{{n++;const row=findRow();if(!row){{clearInterval(v);post('success','DEVICE_DELETED','Dispositivo removido e confirmado.');}}else if(n>=12){{clearInterval(v);post('error','DELETE_NOT_CONFIRMED','O painel não confirmou a exclusão do dispositivo.');}}}},500);}}
      function confirmDialog(){{const ds=[...document.querySelectorAll('[role="dialog"]')];const d=ds[ds.length-1];if(!d)return false;const b=[...d.querySelectorAll('button')].find(x=>{{const t=(x.textContent||'').trim().toLowerCase();return t&&!t.includes('cancel')&&!t.includes('não')&&!t.includes('nao')&&t!=='no';}});if(!b)return false;clickReal(b);return true;}}
      post('progress','DELETE_SEARCH','Procurando dispositivo...');
      const sb=[...document.querySelectorAll('button')].find(b=>{{const t=(b.textContent||'').trim().toLowerCase();return t==='search'||t==='pesquisar';}});if(sb)clickReal(sb);
      let attempts=0;
      const timer=setInterval(()=>{{
        attempts++;
        const inputs=[...document.querySelectorAll('input')];
        const search=inputs.find(i=>i.type==='search')||inputs.find(i=>/search|busca|filtr/i.test(i.placeholder||''))||inputs.find(i=>i.offsetParent!==null&&(i.type==='text'||!i.type));
        if(!search){{if(attempts>=20){{clearInterval(timer);post('error','SEARCH_INPUT_NOT_FOUND','Campo de pesquisa não encontrado.');}}return;}}
        clearInterval(timer);setReactInput(search,MAC);
        setTimeout(()=>{{
          const row=findRow();if(!row){{post('error','DEVICE_NOT_FOUND','Dispositivo não encontrado.');return;}}
          const menu=menuButton(row);if(!menu){{post('error','DEVICE_MENU_NOT_FOUND','Menu não encontrado.');return;}}clickReal(menu);
          setTimeout(()=>{{
            const deact=action(['deactivate','desativar','disable','inactiv']);
            const del0=action(['delete','excluir','deletar','remove','apagar','trash','lixeira']);
            if(DIRECT&&del0){{post('progress','DELETING','Removendo dispositivo para o reset...');clickReal(del0);setTimeout(()=>{{confirmDialog();setTimeout(()=>verifyDeleted(),900);}},900);return;}}
            if(deact){{
              post('progress','DEACTIVATING','Desativando no painel...');clickReal(deact);
              setTimeout(()=>{{confirmDialog();setTimeout(()=>{{
                const row2=findRow();if(!row2){{post('error','DEVICE_NOT_VISIBLE_AFTER_DEACTIVATE','O dispositivo saiu da lista após desativar, mas a exclusão ainda não foi confirmada.');return;}}
                const menu2=menuButton(row2);if(!menu2){{post('error','SECOND_MENU_NOT_FOUND','Não foi possível reabrir o menu.');return;}}clickReal(menu2);
                setTimeout(()=>{{const del=action(['delete','excluir','deletar','remove','apagar','trash','lixeira']);if(!del){{post('error','DELETE_ACTION_NOT_FOUND','Ação Delete não encontrada.');return;}}post('progress','DELETING','Removendo dispositivo...');clickReal(del);setTimeout(()=>{{confirmDialog();setTimeout(()=>verifyDeleted(),900);}},900);}},1400);
              }},2400);}},900);return;
            }}
            if(del0){{post('progress','DELETING','Removendo dispositivo...');clickReal(del0);setTimeout(()=>{{confirmDialog();setTimeout(()=>verifyDeleted(),900);}},900);return;}}
            post('error','DELETE_ACTION_NOT_FOUND','Deactivate/Delete não encontrado.');
          }},1200);
        }},800);
      }},500);
    }})();true;
    '''
    await _run_js(page, js, {"DEVICE_DELETED"}, timeout=40000)


async def reset_device(page, device, playlist):
    await delete_device(page, device)
    await add_device(page, device)
    await add_playlist(page, device, playlist)
