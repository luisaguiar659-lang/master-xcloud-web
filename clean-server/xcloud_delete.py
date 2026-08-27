import asyncio
import json

from xcloud import HELPERS, _goto_devices, _run_js, add_device, add_playlist


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


async def reset_device(page, device, playlist):
    await delete_device(page, device)
    await add_device(page, device)
    await add_playlist(page, device, playlist)
