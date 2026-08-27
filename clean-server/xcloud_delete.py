import json

from xcloud import HELPERS, XCloudError, _goto_devices, _run_js, add_device, add_playlist


async def _wait_devices_ready(page):
    """Espera a SPA de Devices terminar de montar antes de injetar a automação."""
    try:
        await page.wait_for_function(
            r"""
            () => {
              const body=((document.body&&document.body.innerText)||'').toLowerCase();
              const hasDeviceScreen=/devices|device key|add new device|dispositiv/.test(body);
              return hasDeviceScreen && document.querySelectorAll('button').length > 0;
            }
            """,
            polling=150,
            timeout=20000,
        )
    except Exception:
        # O fluxo JS abaixo ainda possui sua própria espera/retry.
        pass


async def delete_device(page, device, playlist=""):
    """Remove o dispositivo usando a mesma etapa de exclusão usada pelo Reset.

    O campo playlist é recebido para reproduzir exatamente a entrada do fluxo
    funcional (Device Key + M3U/DNS), embora a URL M3U não seja enviada ao painel
    durante o clique de exclusão.
    """
    device = device.strip().upper()
    playlist = (playlist or "").strip()

    await _goto_devices(page)
    await _wait_devices_ready(page)

    js = r'''
    (() => {
      const MAC=__MAC__;
      __HELPERS__

      function findRow(){
        return [...document.querySelectorAll('tr')].find(r=>
          (r.innerText||'').toUpperCase().includes(MAC.toUpperCase()));
      }

      function menuButton(row){
        const icon=row.querySelector('svg.lucide-ellipsis')
          || row.querySelector('svg[class*="ellipsis"]');
        return icon ? icon.closest('button') : row.querySelector('button[aria-haspopup="menu"]');
      }

      function action(words){
        const els=[
          ...document.querySelectorAll('[role="menuitem"]'),
          ...document.querySelectorAll('button')
        ];
        return els.find(e=>{
          const t=(e.textContent||'').trim().toLowerCase();
          return t && t.length<80 && words.some(w=>t.includes(w));
        }) || null;
      }

      function searchButton(){
        const buttons=[...document.querySelectorAll('button')];
        return buttons.find(b=>{
          const t=(b.textContent||'').trim().toLowerCase();
          const a=(b.getAttribute('aria-label')||'').trim().toLowerCase();
          const title=(b.getAttribute('title')||'').trim().toLowerCase();
          return t==='search' || t==='pesquisar' ||
                 a.includes('search') || a.includes('pesquis') ||
                 title.includes('search') || title.includes('pesquis') ||
                 !!b.querySelector('svg.lucide-search, svg[class*="search"]');
        }) || null;
      }

      function searchInput(){
        const inputs=[...document.querySelectorAll('input')];
        return inputs.find(i=>i.type==='search' && i.offsetParent!==null)
          || inputs.find(i=>{
               const p=(i.placeholder||'').toLowerCase();
               const a=(i.getAttribute('aria-label')||'').toLowerCase();
               return i.offsetParent!==null && /search|busca|pesquis|filtr/.test(p+' '+a);
             })
          || inputs.find(i=>i.offsetParent!==null && (i.type==='text'||!i.type));
      }

      function confirmDialog(){
        const ds=[...document.querySelectorAll('[role="dialog"]')];
        const d=ds[ds.length-1];
        if(!d) return false;

        const buttons=[...d.querySelectorAll('button')];
        const preferred=buttons.find(x=>{
          const t=(x.textContent||'').trim().toLowerCase();
          return /confirm|desativ|deactiv|delete|excluir|remove|sim|yes/.test(t)
            && !/cancel|não|nao|no$/.test(t);
        });
        const fallback=[...buttons].reverse().find(x=>{
          const t=(x.textContent||'').trim().toLowerCase();
          return t && !t.includes('cancel') && !t.includes('não') &&
                 !t.includes('nao') && t!=='no';
        });

        const b=preferred||fallback;
        if(!b) return false;
        clickReal(b);
        return true;
      }

      function verifyDeleted(){
        post('progress','DELETE_VERIFYING','Confirmando exclusão...');
        let n=0;
        const v=setInterval(()=>{
          n++;
          const row=findRow();
          if(!row){
            clearInterval(v);
            post('success','DEVICE_DELETED','Dispositivo removido e confirmado.');
          } else if(n>=16){
            clearInterval(v);
            post('error','DELETE_NOT_CONFIRMED','O painel não confirmou a exclusão do dispositivo.');
          }
        },500);
      }

      function beginDelete(row){
        const menu=menuButton(row);
        if(!menu){
          post('error','DEVICE_MENU_NOT_FOUND','Menu não encontrado.');
          return;
        }

        clickReal(menu);

        setTimeout(()=>{
          const deact=action(['deactivate','desativar','disable','inactiv']);
          const del0=action(['delete','excluir','deletar','remove','apagar','trash','lixeira']);

          if(deact){
            post('progress','DEACTIVATING','Desativando no painel...');
            clickReal(deact);

            setTimeout(()=>{
              confirmDialog();

              // Igual ao fluxo funcional: permanece na mesma tela/DOM após desativar.
              setTimeout(()=>{
                const row2=findRow();
                if(!row2){
                  post('error','DEVICE_NOT_VISIBLE_AFTER_DEACTIVATE',
                    'O dispositivo saiu da lista após desativar, mas a exclusão ainda não foi confirmada.');
                  return;
                }

                const menu2=menuButton(row2);
                if(!menu2){
                  post('error','SECOND_MENU_NOT_FOUND','Não foi possível reabrir o menu.');
                  return;
                }

                clickReal(menu2);

                setTimeout(()=>{
                  const del=action(['delete','excluir','deletar','remove','apagar','trash','lixeira']);
                  if(!del){
                    post('error','DELETE_ACTION_NOT_FOUND','Ação Delete não encontrada.');
                    return;
                  }

                  post('progress','DELETING','Removendo dispositivo...');
                  clickReal(del);

                  setTimeout(()=>{
                    confirmDialog();
                    setTimeout(()=>verifyDeleted(),900);
                  },900);
                },1400);
              },2400);
            },900);
            return;
          }

          if(del0){
            post('progress','DELETING','Removendo dispositivo...');
            clickReal(del0);
            setTimeout(()=>{
              confirmDialog();
              setTimeout(()=>verifyDeleted(),900);
            },900);
            return;
          }

          post('error','DELETE_ACTION_NOT_FOUND','Deactivate/Delete não encontrado.');
        },1200);
      }

      post('progress','DELETE_SEARCH','Procurando dispositivo...');

      // Não torna o campo Search obrigatório. Se o MAC já estiver na tabela,
      // usa a linha diretamente. Isso evita o erro observado no Chromium headless.
      const sb=searchButton();
      if(sb) clickReal(sb);

      let attempts=0;
      const timer=setInterval(()=>{
        attempts++;

        const search=searchInput();
        if(search) setReactInput(search,MAC);

        const row=findRow();
        if(row){
          clearInterval(timer);
          beginDelete(row);
          return;
        }

        if(attempts>=30){
          clearInterval(timer);
          if(!search){
            post('error','DEVICE_NOT_FOUND_NO_SEARCH',
              'O dispositivo não apareceu na tabela e a pesquisa não abriu.');
          } else {
            post('error','DEVICE_NOT_FOUND','Dispositivo não encontrado.');
          }
        }
      },500);
    })()
    '''

    js = js.replace('__MAC__', json.dumps(device)).replace('__HELPERS__', HELPERS)
    await _run_js(page, js, {"DEVICE_DELETED"}, timeout=55000)


async def reset_device(page, device, playlist):
    # Reset e Excluir compartilham literalmente a mesma etapa de remoção.
    # O Reset apenas continua com recriação + M3U depois do DEVICE_DELETED.
    await delete_device(page, device, playlist)
    await add_device(page, device)
    await add_playlist(page, device, playlist)
