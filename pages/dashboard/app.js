const bridge = window.AstrBotPluginPage;
const instances = [];
let selectedInstance = null;
const messages = [];
let sseSubscriptionId = null;

async function loadStatus() {
  try {
    const data = await bridge.apiGet('status');
    document.getElementById('ws-status').textContent = data.bridge_on ? 'Running' : 'Stopped';
    document.getElementById('ws-status').className = 'value ' + (data.bridge_on ? 'running' : 'stopped');
    document.getElementById('listen-addr').textContent = 'ws://' + (data.ws_host || '?') + ':' + (data.ws_port || '?');
    document.getElementById('online-count').textContent = data.online_count != null ? data.online_count : '?';
    document.getElementById('pending-queries').textContent = data.pending_queries != null ? data.pending_queries : '?';

    const sd = await bridge.apiGet('servers');
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
    return '<div class="server-item"><div class="info"><div class="name">' + inst.server_id + '</div><div class="meta">ZenithProxy</div></div><div class="meta">Mod: ' + (inst.mod_version || '?') + ' | Caps: ' + (inst.capabilities || []).join(', ') + '</div></div>';
  }).join('');
}

function renderInstanceList() {
  const list = document.getElementById('instance-list');
  if (instances.length === 0) {
    list.innerHTML = '<div class="empty-state">暂无实例</div>';
    selectedInstance = null;
    return;
  }
  if (!selectedInstance || !instances.some(function(i) { return i.server_id === selectedInstance; })) {
    selectedInstance = instances[0].server_id;
  }
  list.innerHTML = instances.map(function(inst) {
    const cls = selectedInstance === inst.server_id ? 'instance-item active' : 'instance-item';
    return '<div class="' + cls + '" data-id="' + inst.server_id + '"><div class="name">' + inst.server_id + '</div><div class="detail online">● 已连接</div></div>';
  }).join('');

  list.querySelectorAll('.instance-item').forEach(function(el) {
    el.addEventListener('click', function() {
      selectedInstance = el.getAttribute('data-id');
      renderInstanceList();
      renderMessages();
    });
  });
}

function renderMessages() {
  const area = document.getElementById('message-area');
  const filtered = selectedInstance ? messages.filter(function(m) { return m.server_id === selectedInstance; }) : messages;
  if (filtered.length === 0) {
    area.innerHTML = '<div class="empty-state">暂无消息</div>';
    return;
  }
  area.innerHTML = filtered.map(function(msg) {
    const ts = msg.timestamp ? formatTime(msg.timestamp) : msg.time;
    return '<div class="message-item"><div class="header"><span class="server-tag">' + msg.server_id + '</span><span class="sender">' + msg.sender + '</span><span class="time">' + ts + '</span></div><div class="content">' + msg.content + '</div></div>';
  }).join('');
}

function formatTime(ts) {
  const d = new Date(typeof ts === 'number' ? ts * 1000 : ts);
  const pad = function(n) { return n < 10 ? '0' + n : n; };
  return pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds());
}

function addMessage(msg) {
  messages.unshift(msg);
  if (messages.length > 200) messages.pop();
  renderMessages();
}

function startSSE() {
  if (sseSubscriptionId) bridge.unsubscribeSSE(sseSubscriptionId);
  bridge.subscribeSSE('events', {
    onMessage: function(event) {
      try {
        const msg = typeof event.parsed === 'object' ? event.parsed : JSON.parse(event.raw);
        addMessage(msg);
      } catch (err) {}
    }
  }).then(function(id) {
    sseSubscriptionId = id;
  }).catch(function(e) {
    setTimeout(startSSE, 3000);
  });
}

document.getElementById('btn-start').addEventListener('click', async function() {
  await bridge.apiPost('start');
  setTimeout(loadStatus, 1000);
});

document.getElementById('btn-stop').addEventListener('click', async function() {
  await bridge.apiPost('stop');
  setTimeout(loadStatus, 1000);
});

document.getElementById('btn-refresh').addEventListener('click', function() { loadStatus(); });

document.getElementById('btn-clear').addEventListener('click', function() {
  messages.length = 0;
  renderMessages();
});

document.getElementById('btn-send').addEventListener('click', async function() {
  const input = document.getElementById('chat-input');
  const msg = input.value.trim();
  if (!msg || !selectedInstance) return;
  input.value = '';
  try {
    await bridge.apiPost('send', { server_id: selectedInstance, message: msg });
  } catch (e) {
    console.error('[mcbridge] send error:', e);
  }
});

document.getElementById('chat-input').addEventListener('keypress', function(e) {
  if (e.key === 'Enter') document.getElementById('btn-send').click();
});

(async function() {
  try {
    await bridge.ready();
    await loadStatus();
    setInterval(loadStatus, 5000);
    startSSE();
  } catch (e) {
    document.getElementById('ws-status').textContent = 'Error';
  }
})();
