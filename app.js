const API_URL = 'https://master-xcloud-web.onrender.com';
const $ = id => document.getElementById(id);
let token = sessionStorage.getItem('xcloud_token') || '';
let operations = Number(sessionStorage.getItem('xcloud_operations') || 0);

function setLogged(v) {
  $('loginView').hidden = v;
  $('appView').hidden = !v;
  $('topActions').hidden = !v;
  if (v) {
    $('opsCount').textContent = operations;
    scrollTo(0, 0);
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
    if (r.status === 401) throw new Error(data.detail || 'Login ou sessão inválida.');
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
  } catch (e) {
    $('loginStatus').textContent = 'Servidor gratuito pode estar acordando. Aguarde 30–60 segundos e tente entrar.';
    if ($('apiState')) $('apiState').textContent = 'Acordando';
    return false;
  }
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
  b.textContent = 'ENTRANDO...';
  $('loginStatus').textContent = 'Entrando no painel XCloud. Se o servidor estava parado, pode levar até 1 minuto...';

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
    b.disabled = false;
    b.textContent = 'ENTRAR';
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

$('flow').onchange = () => {
  $('playlistGroup').hidden = $('flow').value === 'delete';
};

$('executeBtn').onclick = async () => {
  const flow = $('flow').value;
  const device = $('device').value.trim().toUpperCase();
  const playlist = $('playlist').value.trim();

  if (!device) { alert('Informe o Device Key / MAC.'); return; }
  if (flow !== 'delete' && !playlist) { alert('Informe a M3U / DNS.'); return; }
  if (flow === 'delete' && !confirm(`Excluir ${device}?`)) return;
  if (flow === 'reset' && !confirm(`Resetar ${device}? O dispositivo será excluído e cadastrado novamente.`)) return;

  const b = $('executeBtn');
  b.disabled = true;
  b.textContent = 'PROCESSANDO...';
  $('timeline').innerHTML = '';

  row('working', 'INÍCIO',
    flow === 'activate' ? 'Ativando dispositivo e DNS...' :
    flow === 'reset' ? 'Excluindo, recriando e adicionando DNS...' :
    'Excluindo dispositivo...'
  );

  try {
    const d = await request(`/operations/${flow}`, {
      method: 'POST',
      body: JSON.stringify({device, playlist: flow === 'delete' ? null : playlist})
    });
    row('success', 'CONCLUÍDO', d.message || 'Operação concluída.');
    operations++;
    sessionStorage.setItem('xcloud_operations', operations);
    $('opsCount').textContent = operations;
  } catch (e) {
    row('error', 'ERRO', e.message);
    if (/sessão|login/i.test(e.message)) {
      token = '';
      sessionStorage.removeItem('xcloud_token');
      setTimeout(() => setLogged(false), 1200);
    }
  } finally {
    b.disabled = false;
    b.textContent = 'EXECUTAR';
  }
};

(async () => {
  await checkHealth();
  if (token) setLogged(true);
})();
