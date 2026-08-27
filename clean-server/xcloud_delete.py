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
        pass


async def delete_device(page, device, playlist=""):
    """Remove o dispositivo usando a mesma etapa de exclusão usada pelo Reset."""
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
        const icon=row.querySelector(
          'svg.lucide-ellipsis, svg[class*="ellipsis"], svg.lucide-more-horizontal, svg[class*="more-horizontal"], svg.lucide-more-vertical, svg[class*="more-vertical"]'
        );
        if(icon){
          const clickable=icon.closest('button,[role="button"],a');
          if(clickable) return clickable;
        }
        return row.querySelector('button[aria-haspopup="menu"],[role="button"][aria-haspopup="menu"],button');
      }

      function visible(el){
        if(!el) return false;
        const st=getComputedStyle(el);
        if(st.display==='none'||st.visibility==='hidden'||Number(st.opacity)===0) return false;
        const r=el.getBoundingClientRect();
        return r.width>0&&r.height>0;
      }

      function textOf(el){
        return [
          el.textContent||'',
          el.getAttribute&&el.getAttribute('aria-label')||'',
          el.getAttribute&&el.getAttribute('title')||'',
          el.getAttribute&&el.getAttribute('data-value')||'',
          el.getAttribute&&el.getAttribute('data-testid')||''
        ].join(' ').trim().toLowerCase();
      }

      function clickableOf(el){
        if(!el) return null;
        return el.closest('button,[role="menuitem"],[role="button"],a') || el;
      }

      function action(words, iconWords){
        const selectors='[role="menuitem"],button,a,[role="button"],div,span';
        const els=[...document.querySelectorAll(selectors)].filter(visible);

        for(const e of els){
          const t=textOf(e);
          if(t && t.length<160 && words.some(w=>t.includes(w))){
            return clickableOf(e);
          }
        }

        const icons=[...document.querySelectorAll('svg')].filter(visible);
        for(const svg of icons){
          const sig=[
            svg.getAttribute('class')||'',
            svg.getAttribute('data-lucide')||'',
            svg.getAttribute('aria-label')||''
          ].join(' ').toLowerCase();
          if(iconWords.some(w=>sig.includes(w))){
            const hit=clickableOf(svg);
            if(hit && visible(hit)) return hit;
          }
        }
        return null;
      }

      function waitAction(words,iconWords,onFound,onMissing,reopen){
        let tries=0;
        const timer=setInterval(()=>{
          tries++;
          const hit=action(words,iconWords);
          if(hit){
            clearInterval(timer);
            onFound(hit);
            return;
          }
          if(reopen && (tries===6||tries===12)){
            try{ clickReal(reopen); }catch(e){}
          }
          if(tries>=20){
            clearInterval(timer);
            onMissing();
          }
        },250);
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
        const ds=[...document.querySelectorAll('[role="dialog"]')].filter(visible);
        const d=ds[ds.length-1];
        if(!d) return false;

        const candidates=[...d.querySelectorAll('button,[role="button"]')].filter(visible);
        const preferred=candidates.find(x=>{
          const t=textOf(x);
          return /confirm|desativ|deactiv|disable|delete|excluir|remove|apagar|sim|yes/.test(t)
            && !/cancel|não|nao|no$/.test(t);
        });
        const fallback=[...candidates].reverse().find(x=>{
          const t=textOf(x);
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
          } else if(n>=24){
            clearInterval(v);
            post('error','DELETE_NOT_CONFIRMED','O painel não confirmou a exclusão do dispositivo.');
          }
        },500);
      }

      function runDeleteAction(del){
        post('progress','DELETING','Removendo dispositivo...');
        clickReal(del);
        setTimeout(()=>{
          confirmDialog();
          setTimeout(()=>verifyDeleted(),1200);
        },900);
      }

      function reopenForDelete(){
        let tries=0;
        const rowTimer=setInterval(()=>{
          tries++;
          const row2=findRow();
          if(row2){
            const menu2=menuButton(row2);
            if(menu2){
              clearInterval(rowTimer);
              clickReal(menu2);
              waitAction(
                ['delete','excluir','deletar','remove','apagar','trash','lixeira'],
                ['trash','delete','x-circle'],
                runDeleteAction,
                ()=>post('error','DELETE_ACTION_NOT_FOUND','Ação Delete não encontrada.'),
                menu2
              );
              return;
            }
          }
          if(tries>=24){
            clearInterval(rowTimer);
            post('error','SECOND_MENU_NOT_FOUND','Não foi possível localizar novamente o dispositivo após desativar.');
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

        waitAction(
          ['deactivate','desativar','disable','inactiv','deactive','turn off'],
          ['power','power-off','circle-off','ban'],
          deact=>{
            post('progress','DEACTIVATING','Desativando no painel...');
            clickReal(deact);
            setTimeout(()=>{
              confirmDialog();
              setTimeout(()=>reopenForDelete(),1800);
            },900);
          },
          ()=>{
            const del0=action(
              ['delete','excluir','deletar','remove','apagar','trash','lixeira'],
              ['trash','delete','x-circle']
            );
            if(del0){
              runDeleteAction(del0);
            } else {
              post('error','DELETE_ACTION_NOT_FOUND','Deactivate/Delete não encontrado.');
            }
          },
          menu
        );
      }

      post('progress','DELETE_SEARCH','Procurando dispositivo...');
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
    await _run_js(page, js, {"DEVICE_DELETED"}, timeout=70000)


async def reset_device(page, device, playlist):
    await delete_device(page, device, playlist)
    await add_device(page, device)
    await add_playlist(page, device, playlist)
