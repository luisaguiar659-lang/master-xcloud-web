import json

from xcloud import HELPERS, _goto_devices, _run_js, add_device, add_playlist


async def delete_device(page, device):
    """Remove o dispositivo usando exatamente a etapa de exclusão do fluxo Reset funcional.

    A diferença principal para a tentativa anterior é que, após Desativar, o código
    NÃO recarrega a página. Ele permanece no mesmo estado React/DOM, aguarda o painel
    atualizar a linha, reabre o menu e então executa Delete + confirmação.
    """
    device = device.strip().upper()
    await _goto_devices(page)

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
        return icon ? icon.closest('button') : null;
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

      function confirmDialog(){
        const ds=[...document.querySelectorAll('[role="dialog"]')];
        const d=ds[ds.length-1];
        if(!d) return false;

        const b=[...d.querySelectorAll('button')].find(x=>{
          const t=(x.textContent||'').trim().toLowerCase();
          return t &&
            !t.includes('cancel') &&
            !t.includes('não') &&
            !t.includes('nao') &&
            t!=='no';
        });

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
          } else if(n>=12){
            clearInterval(v);
            post('error','DELETE_NOT_CONFIRMED','O painel não confirmou a exclusão do dispositivo.');
          }
        },500);
      }

      post('progress','DELETE_SEARCH','Procurando dispositivo...');

      const sb=[...document.querySelectorAll('button')].find(b=>{
        const t=(b.textContent||'').trim().toLowerCase();
        return t==='search' || t==='pesquisar';
      });
      if(sb) clickReal(sb);

      let attempts=0;
      const timer=setInterval(()=>{
        attempts++;

        const inputs=[...document.querySelectorAll('input')];
        const search=inputs.find(i=>i.type==='search')
          || inputs.find(i=>/search|busca|filtr/i.test(i.placeholder||''))
          || inputs.find(i=>i.offsetParent!==null&&(i.type==='text'||!i.type));

        if(!search){
          if(attempts>=20){
            clearInterval(timer);
            post('error','SEARCH_INPUT_NOT_FOUND','Campo de pesquisa não encontrado.');
          }
          return;
        }

        clearInterval(timer);
        setReactInput(search,MAC);

        setTimeout(()=>{
          const row=findRow();
          if(!row){
            post('error','DEVICE_NOT_FOUND','Dispositivo não encontrado.');
            return;
          }

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
        },800);
      },500);
    })()
    '''

    js = js.replace('__MAC__', json.dumps(device)).replace('__HELPERS__', HELPERS)
    await _run_js(page, js, {"DEVICE_DELETED"}, timeout=45000)


async def reset_device(page, device, playlist):
    # Reset e Excluir compartilham literalmente a mesma etapa de remoção.
    # A única diferença é que o Reset continua com recriação + M3U depois do delete.
    await delete_device(page, device)
    await add_device(page, device)
    await add_playlist(page, device, playlist)
