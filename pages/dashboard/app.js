const bridge = window.AstrBotPluginPage;
const instances = [];
let selectedInstance = null;
const messages = [];
let sseSubscriptionId = null;
let instancePushConfig = {};

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
    renderPushConfig();
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
  const defaultServer = document.getElementById('cfg-default-server').value;
  list.innerHTML = instances.map(function(inst) {
    const isDefault = inst.server_id === defaultServer;
    const defaultBtn = isDefault
      ? '<span class="default-badge">默认</span>'
      : '<button class="btn btn-outline btn-sm btn-set-default" data-id="' + inst.server_id + '">设为默认</button>';
    return '<div class="server-item"><div class="info"><div class="name">' + inst.server_id + '</div><div class="meta">ZenithProxy</div></div><div style="display:flex;align-items:center;gap:12px;"><div class="meta">Mod: ' + (inst.mod_version || '?') + ' | Caps: ' + (inst.capabilities || []).join(', ') + '</div>' + defaultBtn + '</div></div>';
  }).join('');

  list.querySelectorAll('.btn-set-default').forEach(function(btn) {
    btn.addEventListener('click', function() {
      document.getElementById('cfg-default-server').value = btn.getAttribute('data-id');
      renderServerList();
    });
  });
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

function renderPushConfig() {
  const container = document.getElementById('push-config-list');
  if (instances.length === 0) {
    container.innerHTML = '<div class="empty-state" style="padding:16px;">连接实例后可配置推送</div>';
    return;
  }
  container.innerHTML = instances.map(function(inst) {
    const sid = inst.server_id;
    const cfg = instancePushConfig[sid] || {};
    const chatChecked = cfg.chat_push ? 'checked' : '';
    const eventChecked = cfg.event_push ? 'checked' : '';
    return '<div class="push-instance-row"><span class="inst-name">' + sid + '</span><div class="toggles"><label class="toggle-item"><input type="checkbox" class="push-chat" data-sid="' + sid + '" ' + chatChecked + '> 聊天推送</label><label class="toggle-item"><input type="checkbox" class="push-event" data-sid="' + sid + '" ' + eventChecked + '> 事件推送</label></div></div>';
  }).join('');

  container.querySelectorAll('.push-chat').forEach(function(cb) {
    cb.addEventListener('change', function() {
      const sid = cb.getAttribute('data-sid');
      if (!instancePushConfig[sid]) instancePushConfig[sid] = {};
      instancePushConfig[sid].chat_push = cb.checked;
    });
  });
  container.querySelectorAll('.push-event').forEach(function(cb) {
    cb.addEventListener('change', function() {
      const sid = cb.getAttribute('data-sid');
      if (!instancePushConfig[sid]) instancePushConfig[sid] = {};
      instancePushConfig[sid].event_push = cb.checked;
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
    return '<div class="message-item"><div class="time"><span class="server-tag">' + msg.server_id + '</span> ' + msg.time + '</div><div class="sender">' + msg.sender + '</div><div class="content">' + msg.content + '</div></div>';
  }).join('');
}

function addMessage(msg) {
  messages.unshift(msg);
  if (messages.length > 200) messages.pop();
  renderMessages();
}

function startSSE() {
  if (sseSubscriptionId) {
    bridge.unsubscribeSSE(sseSubscriptionId);
  }
  bridge.subscribeSSE('events', {
    onOpen: function() {
      console.log('[mcbridge] SSE connected');
    },
    onMessage: function(event) {
      try {
        const msg = typeof event.parsed === 'object' ? event.parsed : JSON.parse(event.raw);
        addMessage(msg);
      } catch (err) {
        console.warn('[mcbridge] SSE parse error:', err);
      }
    },
    onError: function() {
      console.warn('[mcbridge] SSE error');
    }
  }).then(function(id) {
    sseSubscriptionId = id;
    console.log('[mcbridge] SSE subscription:', id);
  }).catch(function(e) {
    console.error('[mcbridge] SSE subscribe failed:', e);
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

document.getElementById('btn-refresh').addEventListener('click', function() {
  loadStatus();
});

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

async function loadConfig() {
  try {
    const cfg = await bridge.apiGet('config');
    document.getElementById('cfg-ws-host').value = cfg.ws_host || '0.0.0.0';
    document.getElementById('cfg-ws-port').value = cfg.ws_port || 8765;
    document.getElementById('cfg-token').value = cfg.shared_token || '';
    document.getElementById('cfg-default-server').value = cfg.default_server_id || 'default';
    document.getElementById('cfg-event-group').value = cfg.minecraft_event_group || '';
    instancePushConfig = cfg.instance_push_config || {};
    console.log('[mcbridge] config loaded');
  } catch (e) {
    console.error('[mcbridge] loadConfig error:', e);
  }
}

document.getElementById('btn-save-config').addEventListener('click', async function() {
  const btn = this;
  btn.disabled = true;
  btn.textContent = '保存中...';
  try {
    await bridge.apiPost('config/save', {
      ws_host: document.getElementById('cfg-ws-host').value,
      ws_port: parseInt(document.getElementById('cfg-ws-port').value) || 8765,
      shared_token: document.getElementById('cfg-token').value,
      default_server_id: document.getElementById('cfg-default-server').value,
      minecraft_event_group: document.getElementById('cfg-event-group').value,
      instance_push_config: instancePushConfig,
    });
    btn.textContent = '已保存';
    setTimeout(function() { btn.textContent = '保存配置'; btn.disabled = false; }, 2000);
  } catch (e) {
    console.error('[mcbridge] saveConfig error:', e);
    btn.textContent = '保存失败';
    setTimeout(function() { btn.textContent = '保存配置'; btn.disabled = false; }, 2000);
  }
});

(async function() {
  try {
    const ctx = await bridge.ready();
    console.log('[mcbridge] bridge ready, context:', ctx);
    await loadConfig();
    await loadStatus();
    setInterval(loadStatus, 5000);
    startSSE();
  } catch (e) {
    console.error('[mcbridge] init error:', e);
    document.getElementById('ws-status').textContent = 'Error';
  }
})();
