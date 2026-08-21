const API_URL = 'https://master-xcloud-web.onrender.com';
const $ = id => document.getElementById(id);

let token = sessionStorage.getItem('xcloud_token') || '';
let operations = Number(sessionStorage.getItem('xcloud_operations') || 0);
let keepAliveTimer = null;

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
    window.scrollTo(0, 0);
  } else {
    stopKeepAlive();
  }
}

function row(type, title, text) {
  const d = document.createElement('div');
  d.className = `timeline-row ${type}`;
  d.innerHTML = `<span class="dot"></span><div><strong>${title}</strong><p>${text}</p></div>`;
  $('timeline').appendChild(d);
}

async function request(path, opts = {}) {
  const headers = {'Content-Type': 'application/json', ...(opts.headers || {})};
  if (token) headers.Authorization = `Bearer ${token}`;

  let r;
  try {
    r = await fetch(API_URL + path, {...opts, headers});
  } catch (e) {
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
    $('loginStatus').textContent = 'Servidor gratuito pode estar acordando. A primeira conexão pode demorar.';
    if ($('apiState')) $('apiState').textContent = 'Acordando';
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


let activationStartedAt = 0;
let activationClock = null;
let activationMessagesTimer = null;

const activationMessages = [
  'Conectando ao painel...',
  'Preparando o dispositivo...',
  'Enviando dados de ativação...',
  'Configurando DNS...',
  'Finalizando a ativação...'
];

function resetActivationOverlay() {
  $('activationWorking').hidden = false;
  $('activationSuccess').hidden = true;
  $('activationError').hidden = true;

  $('activationWorking').style.display = 'block';
  $('activationSuccess').style.display = 'none';
  $('activationError').style.display = 'none';
}

function openActivationOverlay(device) {
  resetActivationOverlay();

  $('activationDevice').textContent = device;
  $('activationMessage').textContent = activationMessages[0];
  $('activationTimer').textContent = '0,0 s';

  $('activationOverlay').hidden = false;
  $('activationOverlay').style.display = 'grid';

  activationStartedAt = performance.now();

  let messageIndex = 0;
  activationMessagesTimer = setInterval(() => {
    messageIndex = Math.min(messageIndex + 1, activationMessages.length - 1);
    $('activationMessage').textContent = activationMessages[messageIndex];

    const dots = document.querySelectorAll('.activation-steps .step-dot');
    dots.forEach((dot, idx) => dot.classList.toggle('active', idx === Math.min(messageIndex, 2)));
  }, 2800);

  activationClock = setInterval(() => {
    const seconds = (performance.now() - activationStartedAt) / 1000;
    $('activationTimer').textContent = `${seconds.toFixed(1).replace('.', ',')} s`;
  }, 100);
}

function stopActivationTimers() {
  if (activationClock) clearInterval(activationClock);
  if (activationMessagesTimer) clearInterval(activationMessagesTimer);
  activationClock = null;
  activationMessagesTimer = null;
}

function showActivationSuccess(device) {
  stopActivationTimers();
  const seconds = (performance.now() - activationStartedAt) / 1000;

  $('activationWorking').hidden = true;
  $('activationWorking').style.display = 'none';

  $('activationSuccess').hidden = false;
  $('activationSuccess').style.display = 'grid';

  $('successDevice').textContent = device;
  $('successTime').textContent = `Concluído em ${seconds.toFixed(1).replace('.', ',')} s`;
}

function showActivationError(message) {
  stopActivationTimers();

  $('activationWorking').hidden = true;
  $('activationWorking').style.display = 'none';

  $('activationError').hidden = false;
  $('activationError').style.display = 'grid';

  $('activationErrorText').textContent = message;
}

function closeActivationOverlay() {
  stopActivationTimers();
  $('activationOverlay').hidden = true;
  $('activationOverlay').style.display = 'none';
}

$('newActivationBtn').onclick = () => {
  closeActivationOverlay();
  $('device').value = '';
  $('playlist').value = '';
  $('device').focus();
};

$('retryActivationBtn').onclick = () => {
  closeActivationOverlay();
  $('device').focus();
};

$('executeBtn').onclick = async () => {
  const device = $('device').value.trim().toUpperCase();
  const playlist = $('playlist').value.trim();

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

  openActivationOverlay(device);

  try {
    const d = await request('/operations/activate', {
      method: 'POST',
      body: JSON.stringify({device, playlist})
    });

    operations++;
    sessionStorage.setItem('xcloud_operations', operations);
    $('opsCount').textContent = operations;

    showActivationSuccess(device);
  } catch (e) {
    showActivationError(e.message);

    if (/sessão expirada|sessão ausente/i.test(e.message)) {
      token = '';
      sessionStorage.removeItem('xcloud_token');
      setTimeout(() => {
        closeActivationOverlay();
        setLogged(false);
      }, 1800);
    }
  } finally {
    b.disabled = false;
  }
};

(async () => {
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
    try {
      await deferredInstallPrompt.userChoice;
    } catch {}
    deferredInstallPrompt = null;
    installBtn.hidden = true;
    installBtn.style.display = 'none';
  });
}
