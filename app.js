const API_URL = 'https://api.masterxcloud.shop';
const $ = id => document.getElementById(id);

let token = sessionStorage.getItem('xcloud_token') || '';
let operations = Number(sessionStorage.getItem('xcloud_operations') || 0);
let keepAliveTimer = null;

const operationConfig = {
  activate: {
    path: '/operations/activate',
    label: 'Ativar MAC + DNS',
    button: 'ATIVAR MAC + DNS',
    workingTitle: 'ATIVANDO DISPOSITIVO',
    successTitle: 'ATIVAÇÃO CONCLUÍDA',
    successText: 'Dispositivo configurado com sucesso.',
    errorTitle: 'ATIVAÇÃO NÃO CONCLUÍDA',
    messages: [
      'Conectando ao painel...',
      'Preparando o dispositivo...',
      'Enviando dados de ativação...',
      'Configurando DNS...',
      'Finalizando a ativação...'
    ]
  },
  reset: {
    path: '/operations/reset',
    label: 'Editar (Reset) + DNS',
    button: 'EDITAR (RESET) + DNS',
    workingTitle: 'RESETANDO DISPOSITIVO',
    successTitle: 'RESET CONCLUÍDO',
    successText: 'Dispositivo resetado e configurado novamente com sucesso.',
    errorTitle: 'RESET NÃO CONCLUÍDO',
    messages: [
      'Conectando ao painel...',
      'Removendo configuração atual...',
      'Cadastrando o dispositivo novamente...',
      'Reaplicando M3U / DNS...',
      'Finalizando o reset...'
    ]
  }
};

function selectedOperation() {
  const key = $('operation')?.value || 'activate';
  return operationConfig[key] || operationConfig.activate;
}

function updateOperationUI() {
  const op = selectedOperation();
  if ($('operationLabel')) $('operationLabel').textContent = op.label;
  if ($('executeBtn')) $('executeBtn').textContent = op.button;
}

function showLoginLoader(show) {
  const loader = $('loginLoader');
  loader.hidden = !show;
  loader.style.display = show ? 'grid' : 'none';
}

function setLogged(v) {
  const login = $('loginView');
  const app = $('appView');
  const actions = $('topActions');

  login.hidden = v;
  app.hidden = !v;
  actions.hidden = !v;

  login.style.display = v ? 'none' : 'grid';
  app.style.display = v ? 'grid' : 'none';
  actions.style.display = v ? 'flex' : 'none';

  if (v) {
    $('opsCount').textContent = operations;
    startKeepAlive();
    updateOperationUI();
    window.scrollTo(0, 0);
  } else {
    stopKeepAlive();
  }
}

function row(type, title, text) {
  const d = document.createElement('div');
  d.className = `timeline-row ${type}`;
  d.innerHTML = `<span class="dot"></span><div><strong>${title}</strong><p>${text}</p></div>`;
  $('timeline').prepend(d);
}

async function request(path, opts = {}) {
  const headers = {'Content-Type': 'application/json', ...(opts.headers || {})};
  if (token) headers.Authorization = `Bearer ${token}`;

  let r;
  try {
    r = await fetch(API_URL + path, {...opts, headers});
  } catch {
    throw new Error('Não foi possível conectar ao servidor. Aguarde alguns segundos e tente novamente.');
  }

  let data = {};
  try { data = await r.json(); } catch {}

  if (!r.ok) {
    if (r.status === 401) throw new Error(data.detail || 'Sessão expirada. Entre novamente.');
    throw new Error(data.detail || `Erro HTTP ${r.status}`);
  }
  return data;
}

async function checkHealth() {
  $('loginStatus').textContent = 'Verificando servidor...';
  try {
    const d = await request('/health');
    $('loginStatus').textContent = d.ok ? 'Servidor online. Faça seu login.' : 'Servidor respondeu com erro.';
    if ($('apiState')) $('apiState').textContent = d.ok ? 'Online' : 'Erro';
    return true;
  } catch {
    $('loginStatus').textContent = 'Servidor pode estar iniciando. Aguarde e tente novamente.';
    if ($('apiState')) $('apiState').textContent = 'Aguardando';
    return false;
  }
}

async function validateStoredSession() {
  if (!token) return false;
  try {
    await request('/auth/session');
    return true;
  } catch {
    token = '';
    sessionStorage.removeItem('xcloud_token');
    return false;
  }
}

function startKeepAlive() {
  stopKeepAlive();
  keepAliveTimer = setInterval(async () => {
    if (!token) return;
    try {
      await request('/auth/session');
      if ($('apiState')) $('apiState').textContent = 'Online';
    } catch {
      if ($('apiState')) $('apiState').textContent = 'Reconectar';
    }
  }, 10 * 60 * 1000);
}

function stopKeepAlive() {
  if (keepAliveTimer) clearInterval(keepAliveTimer);
  keepAliveTimer = null;
}

$('revealPassword').onclick = () => {
  const f = $('password');
  f.type = f.type === 'password' ? 'text' : 'password';
  $('revealPassword').textContent = f.type === 'password' ? 'Mostrar' : 'Ocultar';
};

$('loginBtn').onclick = async () => {
  const email = $('email').value.trim();
  const password = $('password').value;

  if (!email || !password) {
    $('loginStatus').textContent = 'Preencha e-mail e senha.';
    return;
  }

  const b = $('loginBtn');
  b.disabled = true;
  showLoginLoader(true);
  $('loginStatus').textContent = 'Conectando...';

  try {
    const d = await request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({email, password})
    });

    token = d.token;
    sessionStorage.setItem('xcloud_token', token);
    $('password').value = '';
    $('loginStatus').textContent = 'Conectado.';
    setLogged(true);
  } catch (e) {
    $('loginStatus').textContent = e.message;
  } finally {
    showLoginLoader(false);
    b.disabled = false;
  }
};

$('logoutBtn').onclick = async () => {
  try { await request('/auth/logout', {method: 'POST'}); } catch {}
  token = '';
  operations = 0;
  sessionStorage.removeItem('xcloud_token');
  sessionStorage.removeItem('xcloud_operations');
  setLogged(false);
  $('loginStatus').textContent = 'Sessão encerrada.';
};

let operationStartedAt = 0;
let operationClock = null;
let operationMessagesTimer = null;

function resetOperationOverlay() {
  $('activationWorking').hidden = false;
  $('activationSuccess').hidden = true;
  $('activationError').hidden = true;

  $('activationWorking').style.display = 'block';
  $('activationSuccess').style.display = 'none';
  $('activationError').style.display = 'none';
}

function openOperationOverlay(device, op) {
  resetOperationOverlay();

  $('operationWorkingTitle').textContent = op.workingTitle;
  $('operationSuccessTitle').textContent = op.successTitle;
  $('operationSuccessText').textContent = op.successText;
  $('operationErrorTitle').textContent = op.errorTitle;
  $('activationDevice').textContent = device;
  $('activationMessage').textContent = op.messages[0];
  $('activationTimer').textContent = '0,0 s';

  $('activationOverlay').hidden = false;
  $('activationOverlay').style.display = 'grid';

  operationStartedAt = performance.now();

  let messageIndex = 0;
  operationMessagesTimer = setInterval(() => {
    messageIndex = Math.min(messageIndex + 1, op.messages.length - 1);
    $('activationMessage').textContent = op.messages[messageIndex];

    const dots = document.querySelectorAll('.activation-steps .step-dot');
    dots.forEach((dot, idx) => dot.classList.toggle('active', idx === Math.min(messageIndex, 2)));
  }, 2800);

  operationClock = setInterval(() => {
    const seconds = (performance.now() - operationStartedAt) / 1000;
    $('activationTimer').textContent = `${seconds.toFixed(1).replace('.', ',')} s`;
  }, 100);
}

function stopOperationTimers() {
  if (operationClock) clearInterval(operationClock);
  if (operationMessagesTimer) clearInterval(operationMessagesTimer);
  operationClock = null;
  operationMessagesTimer = null;
}

function showOperationSuccess(device, op) {
  stopOperationTimers();
  const seconds = (performance.now() - operationStartedAt) / 1000;

  $('activationWorking').hidden = true;
  $('activationWorking').style.display = 'none';
  $('activationSuccess').hidden = false;
  $('activationSuccess').style.display = 'grid';
  $('operationSuccessTitle').textContent = op.successTitle;
  $('operationSuccessText').textContent = op.successText;
  $('successDevice').textContent = device;
  $('successTime').textContent = `Concluído em ${seconds.toFixed(1).replace('.', ',')} s`;
}

function showOperationError(message, op) {
  stopOperationTimers();

  $('activationWorking').hidden = true;
  $('activationWorking').style.display = 'none';
  $('activationError').hidden = false;
  $('activationError').style.display = 'grid';
  $('operationErrorTitle').textContent = op.errorTitle;
  $('activationErrorText').textContent = message;
}

function closeOperationOverlay() {
  stopOperationTimers();
  $('activationOverlay').hidden = true;
  $('activationOverlay').style.display = 'none';
}

$('newActivationBtn').onclick = () => {
  closeOperationOverlay();
  $('device').value = '';
  $('playlist').value = '';
  $('device').focus();
};

$('retryActivationBtn').onclick = () => {
  closeOperationOverlay();
  $('device').focus();
};

$('operation').addEventListener('change', updateOperationUI);

$('executeBtn').onclick = async () => {
  const device = $('device').value.trim().toUpperCase();
  const playlist = $('playlist').value.trim();
  const op = selectedOperation();

  if (!device) {
    alert('Informe o Device Key / MAC.');
    return;
  }

  if (!playlist) {
    alert('Informe a M3U / DNS.');
    return;
  }

  const b = $('executeBtn');
  b.disabled = true;
  openOperationOverlay(device, op);
  row('working', op.label, `Executando para ${device}...`);

  try {
    const d = await request(op.path, {
      method: 'POST',
      body: JSON.stringify({device, playlist})
    });

    operations++;
    sessionStorage.setItem('xcloud_operations', operations);
    $('opsCount').textContent = operations;
    showOperationSuccess(device, op);
    row('success', op.label, d.message || 'Operação concluída.');
  } catch (e) {
    showOperationError(e.message, op);
    row('error', op.label, e.message);

    if (/sessão expirada|sessão ausente/i.test(e.message)) {
      token = '';
      sessionStorage.removeItem('xcloud_token');
      setTimeout(() => {
        closeOperationOverlay();
        setLogged(false);
      }, 1800);
    }
  } finally {
    b.disabled = false;
  }
};

(async () => {
  updateOperationUI();
  await checkHealth();

  if (token) {
    const valid = await validateStoredSession();
    setLogged(valid);
  }
})();

let deferredInstallPrompt = null;

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('./service-worker.js').catch(() => {});
  });
}

window.addEventListener('beforeinstallprompt', event => {
  event.preventDefault();
  deferredInstallPrompt = event;
  const btn = $('installAppBtn');
  if (btn) {
    btn.hidden = false;
    btn.style.display = 'inline-flex';
  }
});

window.addEventListener('appinstalled', () => {
  deferredInstallPrompt = null;
  const btn = $('installAppBtn');
  if (btn) {
    btn.hidden = true;
    btn.style.display = 'none';
  }
});

const installBtn = $('installAppBtn');
if (installBtn) {
  installBtn.addEventListener('click', async () => {
    if (!deferredInstallPrompt) {
      alert('No Android, abra o menu do navegador e escolha "Adicionar à tela inicial". No iPhone, use Compartilhar → Adicionar à Tela de Início.');
      return;
    }

    deferredInstallPrompt.prompt();
    try { await deferredInstallPrompt.userChoice; } catch {}
    deferredInstallPrompt = null;
    installBtn.hidden = true;
    installBtn.style.display = 'none';
  });
}
