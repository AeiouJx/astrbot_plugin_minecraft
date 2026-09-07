const bridge = window.AstrBotPluginPage;
let selectedInstance = null;
const messages = [];
let sseSubscriptionId = null;
let instances = [];
let userScrolledUp = false;

function ts() {
  const d = new Date();
  const p = function(n) { return n < 10 ? '0' + n : n; };
  return p(d.getHours()) + ':' + p(d.getMinutes()) + ':' + p(d.getSeconds());
}

async function loadStatus() {
  try {
    const data = await bridge.apiGet('status');
    const dot = document.getElementById('ws-dot');
    dot.className = 'status-dot ' + (data.bridge_on ? 'running' : 'stopped');
    document.getElementById('ws-addr').textContent = 'ws://' + (data.ws_host || '?') + ':' + (data.ws_port || '?');
    document.getElementById('online-count').textContent = data.online_count != null ? data.online_count : '?';

    const sd = await bridge.apiGet('servers');
    instances = (sd && sd.servers) ? sd.servers : [];
    renderTabs();
  } catch (e) {}
}

function renderTabs() {
  const tabs = document.getElementById('instance-tabs');
  if (instances.length === 0) {
    tabs.innerHTML = '<span class="tab active">全部</span>';
    return;
  }
  if (selectedInstance && !instances.some(function(i) { return i.server_id === selectedInstance; })) {
    selectedInstance = null;
  }
  let html = '<button class="tab' + (!selectedInstance ? ' active' : '') + '" data-id="">全部</button>';
  instances.forEach(function(inst) {
    html += '<button class="tab' + (selectedInstance === inst.server_id ? ' active' : '') + '" data-id="' + inst.server_id + '">' + esc(inst.server_id) + '</button>';
  });
  tabs.innerHTML = html;
  tabs.querySelectorAll('.tab').forEach(function(btn) {
    btn.addEventListener('click', function() {
      selectedInstance = btn.getAttribute('data-id') || null;
      renderTabs();
      renderChat();
    });
  });
}

function renderChat() {
  const area = document.getElementById('chat-area');
  const filtered = selectedInstance
    ? messages.filter(function(m) { return m.server_id === selectedInstance; })
    : messages;
  if (filtered.length === 0) {
    area.innerHTML = '<div class="empty-state">暂无消息</div>';
    return;
  }
  // 检测是否在底部附近（50px 容差）
  const atBottom = area.scrollHeight - area.scrollTop - area.clientHeight < 50;
  area.innerHTML = filtered.map(function(msg) {
    const time = msg.timestamp ? formatTs(msg.timestamp) : msg.time;
    const type = msg.type || 'chat';
    if (type === 'chat') {
      return '<div class="msg-card chat"><div class="msg-header"><span class="server-tag">' + esc(msg.server_id) + '</span><span class="msg-time">' + time + '</span></div><div class="msg-sender">' + esc(msg.sender) + '</div><div class="msg-content">' + esc(msg.content) + '</div></div>';
    } else {
      return '<div class="msg-card ' + type + '"><div class="msg-header"><span class="server-tag">' + esc(msg.server_id) + '</span><span class="msg-time">' + time + '</span></div><div class="msg-content">' + esc(msg.content) + '</div></div>';
    }
  }).join('');
  // 只有用户在底部时才自动滚到底部
  if (atBottom || !userScrolledUp) {
    area.scrollTop = area.scrollHeight;
  }
}

function formatTs(ts) {
  const d = new Date(typeof ts === 'number' ? ts * 1000 : ts);
  const p = function(n) { return n < 10 ? '0' + n : n; };
  return p(d.getHours()) + ':' + p(d.getMinutes()) + ':' + p(d.getSeconds());
}

function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function addMessage(msg) {
  if (!msg.time) msg.time = ts();
  messages.push(msg);
  if (messages.length > 200) messages.shift();
  renderChat();
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
  }).catch(function() {
    setTimeout(startSSE, 3000);
  });
}

async function loadPlayers() {
  try {
    const data = await bridge.apiGet('players');
    if (!data) return;
    let totalPlaying = 0;
    let allPlayers = [];
    Object.keys(data).forEach(function(sid) {
      const info = data[sid];
      const players = info.players || [];
      totalPlaying += players.length;
      players.forEach(function(p) { allPlayers.push({ name: p, server: sid }); });
    });
    document.getElementById('stat-total').textContent = totalPlaying;
    document.getElementById('stat-playing').textContent = totalPlaying;
    document.getElementById('stat-queue').textContent = '0';

    const list = document.getElementById('player-list');
    if (allPlayers.length === 0) {
      list.innerHTML = '<div class="empty-state">暂无在线玩家</div>';
      return;
    }
    allPlayers.sort(function(a, b) { return a.name.localeCompare(b.name); });
    list.innerHTML = allPlayers.map(function(p) {
      return '<div class="player-item"><div class="player-avatar">' + p.name.charAt(0).toUpperCase() + '</div><span class="player-name">' + esc(p.name) + '</span><span class="server-tag">' + p.server + '</span></div>';
    }).join('');
  } catch (e) {}
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
  loadPlayers();
});

document.getElementById('btn-clear').addEventListener('click', function() {
  messages.length = 0;
  renderChat();
});

document.getElementById('btn-send').addEventListener('click', async function() {
  const input = document.getElementById('chat-input');
  const msg = input.value.trim();
  if (!msg) return;
  input.value = '';
  const target = selectedInstance || (instances.length > 0 ? instances[0].server_id : null);
  if (!target) return;
  try { await bridge.apiPost('send', { server_id: target, message: msg }); } catch (e) {}
});

document.getElementById('chat-input').addEventListener('keypress', function(e) {
  if (e.key === 'Enter') document.getElementById('btn-send').click();
});

(async function() {
  try {
    await bridge.ready();
    // 监听滚动位置，判断用户是否手动滚到上方
    var chatArea = document.getElementById('chat-area');
    chatArea.addEventListener('scroll', function() {
      var distFromBottom = chatArea.scrollHeight - chatArea.scrollTop - chatArea.clientHeight;
      userScrolledUp = distFromBottom > 50;
    });
    await loadStatus();
    loadPlayers();
    setInterval(loadStatus, 5000);
    setInterval(loadPlayers, 10000);
    startSSE();
  } catch (e) {}
})();
