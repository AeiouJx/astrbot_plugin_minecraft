const bridge = window.AstrBotPluginPage;
const instances = [];
let selectedInstance = null;
const messages = [];

async function loadStatus() {
  try {
    const data = await bridge.apiGet('status');
    console.log('[mcbridge] status:', data);

    document.getElementById('ws-status').textContent = data.bridge_on ? 'Running' : 'Stopped';
    document.getElementById('listen-addr').textContent = 'ws://' + (data.ws_host || '?') + ':' + (data.ws_port || '?');
    document.getElementById('online-count').textContent = data.online_count != null ? data.online_count : '?';
    document.getElementById('pending-queries').textContent = data.pending_queries != null ? data.pending_queries : '?';

    const sd = await bridge.apiGet('servers');
    console.log('[mcbridge] servers:', sd);
    instances.length = 0;
    if (sd && sd.servers) sd.servers.forEach(function(s) { instances.push(s); });
    renderServerList();
    renderInstanceList();
  } catch (e) {
    console.error('[mcbridge] loadStatus error:', e);
  }
}

function renderServerList() {
  const list = document.getElementById('server-list');
  if (instances.length === 0) {
    list.innerHTML = '<div class="empty-state">暂无已连接服务器</div>';
    return;
  }
  list.innerHTML = instances.map(function(inst) {
    return '<div class="server-item"><div><div class="name">' + inst.server_id + '</div><div class="meta">ZenithProxy</div></div><div class="meta">Mod: ' + (inst.mod_version || '?') + ' | Caps: ' + (inst.capabilities || []).join(', ') + '</div></div>';
  }).join('');
}

function renderInstanceList() {
  const list = document.getElementById('instance-list');
  if (instances.length === 0) {
    list.innerHTML = '<div class="empty-state">暂无实例</div>';
    return;
  }
  list.innerHTML = instances.map(function(inst) {
    const cls = selectedInstance === inst.server_id ? 'instance-item active' : 'instance-item';
    return '<div class="' + cls + '" data-id="' + inst.server_id + '"><div class="name">' + inst.server_id + '</div><div class="detail online">● 已连接</div></div>';
  }).join('');

  list.querySelectorAll('.instance-item').forEach(function(el) {
    el.addEventListener('click', function() {
      selectedInstance = el.getAttribute('data-id');
      renderInstanceList();
    });
  });
}

function renderMessages() {
  const area = document.getElementById('message-area');
  if (messages.length === 0) {
    area.innerHTML = '<div class="empty-state">暂无消息</div>';
    return;
  }
  area.innerHTML = messages.map(function(msg) {
    return '<div class="message-item"><div class="time"><span class="server-tag">' + msg.server_id + '</span> ' + msg.time + '</div><div class="sender">' + msg.sender + '</div><div class="content">' + msg.content + '</div></div>';
  }).join('');
}

function addMessage(msg) {
  messages.unshift(msg);
  if (messages.length > 50) messages.pop();
  renderMessages();
}

document.getElementById('btn-start').addEventListener('click', async function() {
  await bridge.apiPost('start');
  setTimeout(loadStatus, 1000);
});

document.getElementById('btn-stop').addEventListener('click', async function() {
  await bridge.apiPost('stop');
  setTimeout(loadStatus, 1000);
});

document.getElementById('btn-refresh').addEventListener('click', function() {
  loadStatus();
});

document.getElementById('btn-clear').addEventListener('click', function() {
  messages.length = 0;
  renderMessages();
});

document.getElementById('btn-send').addEventListener('click', function() {
  const input = document.getElementById('chat-input');
  const msg = input.value.trim();
  if (!msg || !selectedInstance) return;
  input.value = '';
  addMessage({ server_id: selectedInstance, sender: 'Bot', content: msg, time: new Date().toLocaleTimeString() });
});

document.getElementById('chat-input').addEventListener('keypress', function(e) {
  if (e.key === 'Enter') document.getElementById('btn-send').click();
});

document.getElementById('btn-save-config').addEventListener('click', function() {
  alert('配置已保存（需重载插件生效）');
});

(async function() {
  try {
    const ctx = await bridge.ready();
    console.log('[mcbridge] bridge ready, context:', ctx);
    await loadStatus();
    setInterval(loadStatus, 5000);
  } catch (e) {
    console.error('[mcbridge] init error:', e);
    document.getElementById('ws-status').textContent = 'Error';
  }
})();
