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
  window.__MXCLOUD_EVENT__ = {
    type: type,
    code: code,
    message: message,
    at: Date.now()
  };
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
  if (pd && pd.set && (!own || own.set !== pd.set)) {
    pd.set.call(input, value);
  } else if (own && own.set) {
    own.set.call(input, value);
  } else {
    input.value = value;
  }
  input.dispatchEvent(new Event('input', {bubbles:true}));
  input.dispatchEvent(new Event('change', {bubbles:true}));
  if (input._valueTracker) {
    input._valueTracker.setValue('');
    input.dispatchEvent(new Event('input', {bubbles:true}));
  }
}
"""


async def _wait_event(page, success_codes, timeout=30000):
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

        await asyncio.sleep(0.25)

    raise XCloudError("Tempo limite da automação excedido.")


async def _run_js(page, js, success_codes, timeout=30000):
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
          if(attempts>=60) {{
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
          [...document.querySelectorAll('button')].find(b=>
            /login|entrar|sign in/i.test((b.textContent||'').trim()));

        if(form && typeof form.requestSubmit==='function') form.requestSubmit();
        else if(submit) clickReal(submit);
        else if(form) form.submit();
        else {{
          post('error','LOGIN_SUBMIT_NOT_FOUND','Botão de login não encontrado.');
          return;
        }}

        post('success','LOGIN_SUBMITTED','Login enviado.');
      }},500);
    }})()
    """

    await _run_js(page, js, {"LOGIN_SUBMITTED"}, timeout=35000)

    try:
        await page.wait_for_url(lambda u: "login" not in u.lower(), timeout=20000)
    except Exception:
        pass

    await asyncio.sleep(2)
    if "login" in page.url.lower():
        raise XCloudError("Login não confirmado. Confira e-mail e senha.")
    return True


async def _goto_devices(page):
    await page.goto(PANEL_DEVICES, wait_until="domcontentloaded", timeout=45000)
    await asyncio.sleep(1.5)
    if "login" in page.url.lower():
        raise XCloudError("Sessão expirada.")


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
          return c.includes('bg-primary') && c.includes('w-full') &&
                 (t.includes('add') || t.includes('novo'));
        }});
        if(btn) return btn;

        btn=buttons.find(b=>{{
          const c=String(b.className||'');
          return c.includes('bg-primary') && c.includes('w-full');
        }});
        if(btn) return btn;

        const plus=document.querySelector('svg.lucide-plus');
        if(plus) return plus.closest('button');

        return buttons.find(b=>{{
          const t=(b.textContent||'').toLowerCase().trim();
          return (t.includes('add')&&t.includes('device')) ||
                 t==='add' || t.includes('adicionar dispositivo');
        }}) || null;
      }}

      const add=findAdd();
      if(!add) {{
        post('error','ADD_DEVICE_BUTTON_NOT_FOUND','Botão Add Device não encontrado.');
        return;
      }}

      post('progress','OPEN_DEVICE_DIALOG','Abrindo cadastro do dispositivo...');
      clickReal(add);

      let attempts=0;
      const timer=setInterval(()=>{{
        attempts++;
        const dialog=document.querySelector('[role="dialog"]');

        if(!dialog && (attempts===4 || attempts===8)) {{
          const again=findAdd();
          if(again) clickReal(again);
        }}

        if(!dialog) {{
          if(attempts>=20) {{
            clearInterval(timer);
            post('error','DEVICE_DIALOG_TIMEOUT','O modal de cadastro não abriu.');
          }}
          return;
        }}

        clearInterval(timer);

        const inputs=[...dialog.querySelectorAll('input')];
        let keyInput=inputs.find(i=>{{
          if(['radio','checkbox','hidden'].includes(i.type)) return false;
          const p=(i.placeholder||'').toLowerCase();
          return p.includes('device') || p.includes('key') ||
                 p.includes('mac') || p.includes('codigo') ||
                 p.includes('código');
        }});

        keyInput=keyInput ||
          inputs.find(i=>!['radio','checkbox','hidden'].includes(i.type));

        if(!keyInput) {{
          post('error','DEVICE_KEY_INPUT_NOT_FOUND','Campo Device Key não encontrado.');
          return;
        }}

        keyInput.focus();
        setReactInput(keyInput,MAC);
        keyInput.blur();

        setTimeout(()=>{{
          const form=dialog.querySelector('form');
          let submit=form&&form.querySelector('button[type="submit"]');

          if(!submit) {{
            submit=[...dialog.querySelectorAll('button')].reverse().find(b=>{{
              const t=(b.textContent||'').toLowerCase().trim();
              return t && !t.includes('cancel') && !t.includes('voltar');
            }});
          }}

          if(form && typeof form.requestSubmit==='function') form.requestSubmit();
          else if(submit) clickReal(submit);
          else if(form) form.submit();
          else {{
            post('error','DEVICE_SAVE_NOT_FOUND','Botão de salvar não encontrado.');
            return;
          }}

          let wait=0;
          const verify=setInterval(()=>{{
            wait++;
            const rows=[...document.querySelectorAll('tr')];
            const found=rows.some(r=>
              (r.innerText||'').toUpperCase().includes(MAC.toUpperCase()));

            if(found) {{
              clearInterval(verify);
              post('success','DEVICE_ADDED','Dispositivo cadastrado e confirmado no painel.');
              return;
            }}

            if(wait>=40) {{
              clearInterval(verify);
              /*
               * Igual ao app, mas com um fallback adicional:
               * depois do submit, se o modal fechou, recarregamos a lista
               * antes de concluir que falhou.
               */
              if(!document.querySelector('[role="dialog"]')) {{
                post('success','DEVICE_SUBMITTED','Cadastro enviado; confirmando após recarregar.');
              }} else {{
                post('error','DEVICE_ADD_NOT_CONFIRMED','O dispositivo não apareceu no painel após o cadastro.');
              }}
            }}
          }},500);
        }},1200);
      }},500);
    }})()
    """

    event = await _run_js(
        page,
        js,
        {"DEVICE_ADDED", "DEVICE_SUBMITTED"},
        timeout=30000,
    )

    if event["code"] == "DEVICE_ADDED":
        return

    # Fallback do backend: recarrega a listagem depois do submit,
    # porque no Render o DOM pode não atualizar tão rápido quanto no WebView.
    await _goto_devices(page)

    verify_js = f"""
    (() => {{
      const MAC={json.dumps(device)};
      {HELPERS}
      let n=0;
      const timer=setInterval(()=>{{
        n++;
        const rows=[...document.querySelectorAll('tr')];
        const found=rows.some(r=>
          (r.innerText||'').toUpperCase().includes(MAC.toUpperCase()));
        if(found) {{
          clearInterval(timer);
          post('success','DEVICE_ADDED','Dispositivo confirmado após recarregar a lista.');
        }} else if(n>=30) {{
          clearInterval(timer);
          post('error','DEVICE_ADD_NOT_CONFIRMED','O dispositivo não apareceu no painel após o cadastro.');
        }}
      }},500);
    }})()
    """
    await _run_js(page, verify_js, {"DEVICE_ADDED"}, timeout=20000)


async def add_playlist(page, device, playlist):
    device = device.strip().upper()
    playlist = playlist.strip()

    url = f"{PLAYLIST_BASE}?device_key={quote(device)}&type=xtream&mode=add"
    await page.goto(url, wait_until="domcontentloaded", timeout=45000)
    await asyncio.sleep(1)

    js = f"""
    (() => {{
      const MAC={json.dumps(device)};
      const URL_LISTA={json.dumps(playlist)};
      {HELPERS}

      let attempts=0;
      const timer=setInterval(()=>{{
        attempts++;
        const inputs=[...document.querySelectorAll('input')];

        const urlInput=inputs.find(i=>{{
          const p=(i.placeholder||'').toLowerCase();
          const a=i.getAttribute('aria-label')||'';
          return p.includes('http') || p.includes('url') ||
                 p.includes('link') || p.includes('playlist') ||
                 /url|playlist/i.test(a);
        }});

        if(!urlInput) {{
          if(attempts>=30) {{
            clearInterval(timer);
            post('error','PLAYLIST_URL_INPUT_NOT_FOUND','Campo da URL não encontrado.');
          }}
          return;
        }}

        clearInterval(timer);
        urlInput.focus();
        setReactInput(urlInput,URL_LISTA);
        urlInput.blur();

        setTimeout(()=>{{
          const form=urlInput.closest('form');
          const buttons=[...document.querySelectorAll('button')];
          const save=(form&&form.querySelector('button[type="submit"]')) ||
            buttons.find(b=>{{
              const t=(b.textContent||'').toLowerCase();
              return t.includes('save') || t.includes('add') ||
                     t.includes('salvar') || t.includes('adicionar');
            }});

          if(form && typeof form.requestSubmit==='function') form.requestSubmit();
          else if(save) clickReal(save);
          else if(form) form.submit();
          else {{
            post('error','PLAYLIST_SAVE_NOT_FOUND','Botão Save não encontrado.');
            return;
          }}

          let check=0;
          const verify=setInterval(()=>{{
            check++;

            const notices=[
              ...document.querySelectorAll(
                '[role="alert"],[role="status"],.toast,.Toastify__toast,[class*="toast"],[class*="alert"]'
              )
            ];

            const txt=notices
              .map(n=>(n.innerText||n.textContent||'').toLowerCase())
              .join(' ');

            const bad=/invalid|failed|error|required|erro|inválid|falhou/.test(txt);
            const good=/success|saved|added|sucesso|salv|adicion/.test(txt);

            if(bad) {{
              clearInterval(verify);
              post('error','PLAYLIST_SAVE_ERROR','O painel informou erro ao salvar a lista.');
              return;
            }}

            if(good) {{
              clearInterval(verify);
              post('success','PLAYLIST_ADDED','Lista salva com sucesso.');
              return;
            }}

            /*
             * O app aceita que alguns painéis não exibam uma confirmação clara.
             * Após alguns segundos sem erro, tratamos o submit como concluído.
             */
            if(check>=12) {{
              clearInterval(verify);
              post('success','PLAYLIST_SUBMITTED','Lista enviada ao painel sem erro visível.');
            }}
          }},500);
        }},700);
      }},500);
    }})()
    """

    await _run_js(
        page,
        js,
        {"PLAYLIST_ADDED", "PLAYLIST_SUBMITTED"},
        timeout=25000,
    )


async def delete_device(page, device):
    """
    Fluxo em duas fases, igual ao comportamento observado no painel:
    1) Se estiver Active, desativa e CONFIRMA.
    2) Recarrega a página, procura o dispositivo novamente e EXCLUI.
    Isso evita tentar encontrar o botão Delete no mesmo menu/DOM após o Deactivate.
    """
    device = device.strip().upper()
    await _goto_devices(page)

    phase1_js = f"""
    (() => {{
      const MAC={json.dumps(device)};
      {HELPERS}

      function findRow() {{
        return [...document.querySelectorAll('tr')].find(r=>
          (r.innerText||'').toUpperCase().includes(MAC.toUpperCase()));
      }}

      function menuButton(row) {{
        const icon=row.querySelector('svg.lucide-ellipsis') ||
                   row.querySelector('svg[class*="ellipsis"]');
        return icon ? icon.closest('button') :
               row.querySelector('button[aria-haspopup="menu"]');
      }}

      function findAction(words) {{
        const els=[
          ...document.querySelectorAll('[role="menuitem"]'),
          ...document.querySelectorAll('button')
        ];
        return els.find(e=>{{
          const t=(e.textContent||'').trim().toLowerCase();
          return t && t.length<80 && words.some(w=>t.includes(w));
        }}) || null;
      }}

      function confirmDialog() {{
        const dialogs=[...document.querySelectorAll('[role="dialog"]')];
        const d=dialogs[dialogs.length-1];
        if(!d) return false;

        const buttons=[...d.querySelectorAll('button')];
        const ok=buttons.reverse().find(b=>{{
          const t=(b.textContent||'').trim().toLowerCase();
          return t &&
            !t.includes('cancel') &&
            !t.includes('não') &&
            !t.includes('nao') &&
            t!=='no';
        }});

        if(!ok) return false;
        clickReal(ok);
        return true;
      }}

      // Abre a busca caso exista um botão Search.
      const searchBtn=[...document.querySelectorAll('button')].find(b=>{{
        const t=(b.textContent||'').trim().toLowerCase();
        return t==='search' || t==='pesquisar';
      }});
      if(searchBtn) clickReal(searchBtn);

      let tries=0;
      const timer=setInterval(()=>{{
        tries++;

        const inputs=[...document.querySelectorAll('input')];
        const search=
          inputs.find(i=>i.type==='search') ||
          inputs.find(i=>/search|busca|filtr/i.test(i.placeholder||'')) ||
          inputs.find(i=>i.offsetParent!==null&&(i.type==='text'||!i.type));

        if(search) setReactInput(search,MAC);

        const row=findRow();
        if(!row) {{
          if(tries>=20) {{
            clearInterval(timer);
            post('error','DEVICE_NOT_FOUND','Dispositivo não encontrado.');
          }}
          return;
        }}

        clearInterval(timer);

        const menu=menuButton(row);
        if(!menu) {{
          post('error','DEVICE_MENU_NOT_FOUND','Menu do dispositivo não encontrado.');
          return;
        }}

        clickReal(menu);

        setTimeout(()=>{{
          // Se Delete já estiver disponível, não precisa desativar.
          const del=findAction(['delete','excluir','deletar','remove','apagar','trash','lixeira']);
          if(del) {{
            clickReal(del);
            setTimeout(()=>{{
              confirmDialog();
              post('success','DELETE_CLICKED','Exclusão enviada ao painel.');
            }},700);
            return;
          }}

          const deact=findAction(['deactivate','desativar','disable','inactiv']);
          if(!deact) {{
            post('error','DEACTIVATE_NOT_FOUND','Ação Deactivate/Delete não encontrada.');
            return;
          }}

          clickReal(deact);

          setTimeout(()=>{{
            confirmDialog();
            // Não tenta excluir aqui. O Python vai recarregar a página.
            setTimeout(()=>{{
              post('success','DEVICE_DEACTIVATED','Dispositivo desativado; recarregando para excluir.');
            }},900);
          }},700);
        }},700);
      }},500);
    }})()
    """

    first = await _run_js(
        page,
        phase1_js,
        {"DELETE_CLICKED", "DEVICE_DEACTIVATED"},
        timeout=30000,
    )

    if first["code"] == "DELETE_CLICKED":
        # Confirma que realmente sumiu.
        await asyncio.sleep(1.2)
        await _goto_devices(page)

        confirm_deleted_js = f"""
        (() => {{
          const MAC={json.dumps(device)};
          {HELPERS}
          let n=0;
          const timer=setInterval(()=>{{
            n++;
            const found=[...document.querySelectorAll('tr')].some(r=>
              (r.innerText||'').toUpperCase().includes(MAC.toUpperCase()));
            if(!found) {{
              clearInterval(timer);
              post('success','DEVICE_DELETED','Dispositivo excluído.');
            }} else if(n>=20) {{
              clearInterval(timer);
              post('error','DELETE_NOT_CONFIRMED','O dispositivo ainda aparece na lista.');
            }}
          }},500);
        }})()
        """
        await _run_js(page, confirm_deleted_js, {"DEVICE_DELETED"}, timeout=15000)
        return

    # O dispositivo estava Active e acabou de ser desativado.
    # Reabre a lista inteira antes da etapa Delete.
    await asyncio.sleep(1)
    await _goto_devices(page)

    phase2_js = f"""
    (() => {{
      const MAC={json.dumps(device)};
      {HELPERS}

      function findRow() {{
        return [...document.querySelectorAll('tr')].find(r=>
          (r.innerText||'').toUpperCase().includes(MAC.toUpperCase()));
      }}

      function menuButton(row) {{
        const icon=row.querySelector('svg.lucide-ellipsis') ||
                   row.querySelector('svg[class*="ellipsis"]');
        return icon ? icon.closest('button') :
               row.querySelector('button[aria-haspopup="menu"]');
      }}

      function findDelete() {{
        const els=[
          ...document.querySelectorAll('[role="menuitem"]'),
          ...document.querySelectorAll('button')
        ];
        return els.find(e=>{{
          const t=(e.textContent||'').trim().toLowerCase();
          return t && t.length<80 &&
            ['delete','excluir','deletar','remove','apagar','trash','lixeira']
              .some(w=>t.includes(w));
        }}) || null;
      }}

      function confirmDialog() {{
        const dialogs=[...document.querySelectorAll('[role="dialog"]')];
        const d=dialogs[dialogs.length-1];
        if(!d) return false;

        const buttons=[...d.querySelectorAll('button')];
        const ok=buttons.reverse().find(b=>{{
          const t=(b.textContent||'').trim().toLowerCase();
          return t &&
            !t.includes('cancel') &&
            !t.includes('não') &&
            !t.includes('nao') &&
            t!=='no';
        }});

        if(!ok) return false;
        clickReal(ok);
        return true;
      }}

      const searchBtn=[...document.querySelectorAll('button')].find(b=>{{
        const t=(b.textContent||'').trim().toLowerCase();
        return t==='search' || t==='pesquisar';
      }});
      if(searchBtn) clickReal(searchBtn);

      let tries=0;
      const timer=setInterval(()=>{{
        tries++;

        const inputs=[...document.querySelectorAll('input')];
        const search=
          inputs.find(i=>i.type==='search') ||
          inputs.find(i=>/search|busca|filtr/i.test(i.placeholder||'')) ||
          inputs.find(i=>i.offsetParent!==null&&(i.type==='text'||!i.type));

        if(search) setReactInput(search,MAC);

        const row=findRow();
        if(!row) {{
          if(tries>=20) {{
            clearInterval(timer);
            post('error','DEVICE_NOT_FOUND_AFTER_DEACTIVATE',
                 'Dispositivo não encontrado após desativar.');
          }}
          return;
        }}

        clearInterval(timer);

        const menu=menuButton(row);
        if(!menu) {{
          post('error','DEVICE_MENU_NOT_FOUND_AFTER_DEACTIVATE',
               'Menu não encontrado após desativar.');
          return;
        }}

        clickReal(menu);

        setTimeout(()=>{{
          const del=findDelete();
          if(!del) {{
            post('error','DELETE_ACTION_NOT_FOUND',
                 'Ação Delete não encontrada após recarregar.');
            return;
          }}

          clickReal(del);

          setTimeout(()=>{{
            confirmDialog();

            let n=0;
            const verify=setInterval(()=>{{
              n++;
              const still=findRow();
              if(!still) {{
                clearInterval(verify);
                post('success','DEVICE_DELETED','Dispositivo excluído.');
              }} else if(n>=20) {{
                clearInterval(verify);
                post('success','DELETE_SENT',
                     'Exclusão enviada; confirmando após recarregar.');
              }}
            }},500);
          }},700);
        }},700);
      }},500);
    }})()
    """

    second = await _run_js(
        page,
        phase2_js,
        {"DEVICE_DELETED", "DELETE_SENT"},
        timeout=30000,
    )

    if second["code"] == "DEVICE_DELETED":
        return

    # Confirmação final após reload.
    await asyncio.sleep(1)
    await _goto_devices(page)

    final_js = f"""
    (() => {{
      const MAC={json.dumps(device)};
      {HELPERS}
      const found=[...document.querySelectorAll('tr')].some(r=>
        (r.innerText||'').toUpperCase().includes(MAC.toUpperCase()));
      if(!found)
        post('success','DEVICE_DELETED','Dispositivo excluído e confirmado.');
      else
        post('error','DELETE_NOT_CONFIRMED','O dispositivo ainda aparece na lista.');
    }})()
    """
    await _run_js(page, final_js, {"DEVICE_DELETED"}, timeout=8000)
