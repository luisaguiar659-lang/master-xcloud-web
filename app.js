const $ = (id) => document.getElementById(id);
const loginView = $("loginView");
const appView = $("appView");
const topActions = $("topActions");
const timeline = $("timeline");
let operations = 0;

function setLoggedIn(value){
  loginView.hidden = value;
  appView.hidden = !value;
  topActions.hidden = !value;
  if(value) window.scrollTo({top:0,behavior:"smooth"});
}

$("revealPassword").addEventListener("click",()=>{
  const field=$("password");
  field.type=field.type==="password"?"text":"password";
  $("revealPassword").textContent=field.type==="password"?"Mostrar":"Ocultar";
});

$("loginBtn").addEventListener("click",()=>{
  const email=$("email").value.trim();
  const password=$("password").value;
  if(!email || !password){$("loginStatus").textContent="Preencha e-mail e senha para abrir a demonstração.";return;}
  $("loginStatus").textContent="Abrindo demonstração…";
  setTimeout(()=>{setLoggedIn(true);$("password").value="";},250);
});

$("logoutBtn").addEventListener("click",()=>{setLoggedIn(false);$("loginStatus").textContent="Sessão de demonstração encerrada.";});
$("flow").addEventListener("change",()=>{$("playlistGroup").hidden=$("flow").value==="delete";});
$("togglePlaylist").addEventListener("click",()=>{
  const t=$("playlist");
  const hidden=t.dataset.hidden!=="false";
  t.dataset.hidden=hidden?"false":"true";
  t.style.webkitTextSecurity=hidden?"none":"disc";
  $("togglePlaylist").textContent=hidden?"Ocultar":"Mostrar";
});

function row(type,title,text){
  const div=document.createElement("div"); div.className=`timeline-row ${type}`;
  div.innerHTML=`<span class="dot"></span><div><strong>${title}</strong><p>${text}</p></div>`;
  timeline.appendChild(div);
}

$("executeBtn").addEventListener("click",async()=>{
  const device=$("device").value.trim(); const flow=$("flow").value; const playlist=$("playlist").value.trim();
  if(!device){alert("Informe o Device Key / MAC.");return;}
  if(flow!=="delete" && !playlist){alert("Informe a M3U / DNS.");return;}
  const btn=$("executeBtn"); btn.disabled=true; btn.textContent="PROCESSANDO…"; timeline.innerHTML="";
  row("working","VALIDANDO","Conferindo os dados informados.");
  await new Promise(r=>setTimeout(r,450));
  row("working","SIMULANDO",flow==="delete"?"Simulando exclusão do dispositivo.":flow==="reset"?"Simulando reset e atualização de DNS.":"Simulando ativação e configuração de DNS.");
  await new Promise(r=>setTimeout(r,650));
  row("success","CONCLUÍDO","Simulação concluída. Nenhuma alteração real foi enviada ao painel.");
  operations++; $("opsCount").textContent=operations; btn.disabled=false; btn.textContent="EXECUTAR SIMULAÇÃO";
});

$("summaryBtn").addEventListener("click",()=>$("summaryDialog").showModal());
$("closeSummary").addEventListener("click",()=>$("summaryDialog").close());
