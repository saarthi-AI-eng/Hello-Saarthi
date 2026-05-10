/* ═══════════════════════════════════════════════════
   Saarthi API Test Console — JavaScript
   ═══════════════════════════════════════════════════ */

// ── State ──
let currentThreadId = null;
let chatHistory = []; // [{role, content}]

const API = () => document.getElementById('apiUrl').value.replace(/\/+$/, '');
const $ = id => document.getElementById(id);
const getMode = () => document.querySelector('input[name="mode"]:checked').value;
const isMind = () => $('mindMode').checked;

// ═══════════════════════════════════════════════════
//  API Calls
// ═══════════════════════════════════════════════════

async function api(path, opts = {}) {
  const url = `${API()}${path}`;
  try {
    const res = await fetch(url, { ...opts, headers: { 'Content-Type': 'application/json', ...opts.headers } });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return await res.json();
  } catch (e) {
    throw e;
  }
}

// ── Health ──
async function checkHealth() {
  const box = $('healthStatus');
  box.textContent = 'Checking...';
  box.className = 'status-box';
  try {
    const d = await api('/api/health');
    box.textContent = `✅ ${d.status.toUpperCase()} — Graph: ${d.graph_ready ? 'Ready' : 'Error'}\nAgents: ${d.agents.join(', ')}`;
    box.className = 'status-box ok';
  } catch (e) {
    box.textContent = `❌ ${e.message}`;
    box.className = 'status-box err';
  }
}

// ── Threads ──
async function loadThreads() {
  const list = $('threadList');
  list.innerHTML = '<div style="color:var(--text-muted);font-size:0.7rem">Loading...</div>';
  try {
    const threads = await api('/api/threads');
    if (!threads.length) { list.innerHTML = '<div style="color:var(--text-muted);font-size:0.7rem">No threads yet</div>'; return; }
    list.innerHTML = '';
    threads.forEach(t => {
      const div = document.createElement('div');
      div.className = `thread-item${t.id === currentThreadId ? ' active' : ''}`;
      const title = t.title.length > 30 ? t.title.slice(0, 30) + '...' : t.title;
      const badge = t.dataset_name ? ' 📊' : '';
      div.innerHTML = `<span onclick="switchThread('${t.id}')">${title}${badge}</span><button class="del-btn" onclick="event.stopPropagation();deleteThread('${t.id}')">🗑</button>`;
      list.appendChild(div);
    });
  } catch (e) {
    list.innerHTML = `<div style="color:var(--accent-red);font-size:0.7rem">${e.message}</div>`;
  }
}

function newThread() {
  currentThreadId = null;
  chatHistory = [];
  $('chatContainer').innerHTML = `<div class="welcome-msg" id="welcomeMsg"><div class="welcome-icon">🎓</div><h2>New Chat</h2><p>Ask a question to begin!</p></div>`;
}

async function switchThread(id) {
  currentThreadId = id;
  try {
    const msgs = await api(`/api/threads/${id}/messages`);
    chatHistory = msgs;
    renderFullHistory(msgs);
    loadThreads();
    // Restore dataset
    try { await api(`/api/data/restore/${id}`, { method: 'POST' }); } catch {}
  } catch (e) {
    alert('Failed to load thread: ' + e.message);
  }
}

async function deleteThread(id) {
  if (!confirm('Delete this thread?')) return;
  try {
    await api(`/api/threads/${id}`, { method: 'DELETE' });
    if (currentThreadId === id) newThread();
    loadThreads();
  } catch (e) { alert(e.message); }
}

function renderFullHistory(msgs) {
  const c = $('chatContainer');
  c.innerHTML = '';
  msgs.forEach(m => {
    if (m.role === 'user') appendUserMsg(m.content);
    else appendRawAssistant(m.content);
  });
  c.scrollTop = c.scrollHeight;
}

// ── Chat ──
async function sendMessage() {
  const input = $('chatInput');
  const query = input.value.trim();
  if (!query) return;
  input.value = '';

  // Hide welcome
  const w = $('welcomeMsg');
  if (w) w.remove();

  appendUserMsg(query);
  chatHistory.push({ role: 'user', content: query });

  const loadingEl = showLoading();

  try {
    const payload = {
      query,
      thread_id: currentThreadId,
      mode: getMode(),
      mind_mode: isMind(),
      messages: chatHistory,
    };

    const data = await api('/api/chat', { method: 'POST', body: JSON.stringify(payload) });

    loadingEl.remove();

    // Update thread
    if (data.thread_id && !currentThreadId) {
      currentThreadId = data.thread_id;
      loadThreads();
    }

    // Render response
    if (data.response_type === 'mind' && data.mind) {
      renderMindResponse(data.mind);
      chatHistory.push({ role: 'assistant', content: data.mind.content });
    } else if (data.agents && data.agents.length) {
      data.agents.forEach(a => renderAgentResponse(a));
      const text = data.agents.map(a => a.content).join('\n\n');
      chatHistory.push({ role: 'assistant', content: text });
    } else {
      appendRawAssistant('No response generated.');
      chatHistory.push({ role: 'assistant', content: 'No response.' });
    }

    scrollBottom();
  } catch (e) {
    loadingEl.remove();
    appendError(e.message);
  }
}

// ── Data ──
async function uploadCSV() {
  const fileInput = $('csvUpload');
  if (!fileInput.files.length) { $('dataStatus').textContent = '⚠️ Select a CSV first'; return; }
  const file = fileInput.files[0];
  const form = new FormData();
  form.append('file', file);
  if (currentThreadId) form.append('thread_id', currentThreadId);

  $('dataStatus').textContent = 'Uploading...';
  try {
    const res = await fetch(`${API()}/api/data/upload`, { method: 'POST', body: form });
    const d = await res.json();
    $('dataStatus').textContent = `✅ ${d.filename} (${(d.size_bytes/1024).toFixed(1)} KB)\nCloud: ${d.cloud_synced ? 'Yes' : 'Local only'}`;
    $('dataStatus').className = 'status-box ok';
  } catch (e) {
    $('dataStatus').textContent = `❌ ${e.message}`;
    $('dataStatus').className = 'status-box err';
  }
}

async function listDatasets() {
  try {
    const d = await api('/api/data/list');
    if (!d.datasets.length) { $('dataStatus').textContent = 'No datasets uploaded'; return; }
    $('dataStatus').textContent = d.datasets.map(f => `📄 ${f.filename} (${f.size_kb} KB)`).join('\n');
    $('dataStatus').className = 'status-box ok';
  } catch (e) { $('dataStatus').textContent = `❌ ${e.message}`; $('dataStatus').className = 'status-box err'; }
}

// ── KB ──
async function updateKB() {
  $('kbStatus').textContent = 'Updating...';
  try {
    const d = await api('/api/kb/update', { method: 'POST' });
    $('kbStatus').textContent = d.map(r => `${r.agent}: ${r.updated ? '✅ Updated' : '⏸ No change'}`).join('\n');
    $('kbStatus').className = 'status-box ok';
  } catch (e) { $('kbStatus').textContent = `❌ ${e.message}`; $('kbStatus').className = 'status-box err'; }
}

async function checkKBStatus() {
  try {
    const d = await api('/api/kb/status');
    $('kbStatus').textContent = Object.entries(d.agents).map(([k, v]) => `${k}: ${v ? '✅ Ready' : '❌ Missing'}`).join('\n');
    $('kbStatus').className = 'status-box ok';
  } catch (e) { $('kbStatus').textContent = `❌ ${e.message}`; $('kbStatus').className = 'status-box err'; }
}


// ═══════════════════════════════════════════════════
//  Rendering Helpers
// ═══════════════════════════════════════════════════

const AGENT_BADGES = {
  notes_agent: { label: '📝 Notes Agent', cls: 'badge-notes' },
  books_agent: { label: '📚 Books Agent', cls: 'badge-books' },
  video_agent: { label: '🎥 Video Agent', cls: 'badge-video' },
  calculator_agent: { label: '🧮 Calculator', cls: 'badge-calc' },
  saarthi_agent: { label: '🤖 Saarthi', cls: 'badge-saarthi' },
  data_analysis_agent: { label: '📊 Data Analysis', cls: 'badge-data' },
  mind_agent: { label: '🧠 Mind Agent', cls: 'badge-mind' },
};

function appendUserMsg(text) {
  const c = $('chatContainer');
  const div = document.createElement('div');
  div.className = 'msg msg-user';
  div.innerHTML = `<div class="msg-bubble">${escapeHtml(text)}</div>`;
  c.appendChild(div);
  scrollBottom();
}

function appendRawAssistant(text) {
  const c = $('chatContainer');
  const div = document.createElement('div');
  div.className = 'msg msg-assistant';
  const card = document.createElement('div');
  card.className = 'agent-card';
  card.innerHTML = `<div class="agent-content">${renderMarkdown(text)}</div>`;
  div.appendChild(card);
  c.appendChild(div);
  renderMath(card);
  scrollBottom();
}

function renderAgentResponse(agent) {
  const c = $('chatContainer');
  const div = document.createElement('div');
  div.className = 'msg msg-assistant';

  const badge = AGENT_BADGES[agent.agent_name] || { label: agent.agent_name, cls: 'badge-saarthi' };
  const confPct = Math.round(agent.confidence_score * 100);
  const confColor = confPct >= 70 ? 'var(--accent-green)' : confPct >= 40 ? 'var(--accent-orange)' : 'var(--accent-red)';

  let html = `<div class="agent-card">`;
  html += `<span class="agent-badge ${badge.cls}">${badge.label}</span>`;
  html += `<div class="agent-content">${renderMarkdown(agent.content)}</div>`;
  html += `<div class="confidence-bar">Confidence: ${confPct}%<div class="conf-track"><div class="conf-fill" style="width:${confPct}%;background:${confColor}"></div></div></div>`;

  // Sources
  if (agent.sources && agent.sources.length) {
    html += `<div class="collapsible"><button class="collapsible-toggle" onclick="this.nextElementSibling.classList.toggle('open')">📎 Sources (${agent.sources.length})</button><div class="collapsible-body">`;
    agent.sources.forEach(s => {
      html += `<div>📄 ${escapeHtml(s.source_file)}${s.page_number ? ` — Page ${s.page_number}` : ''}</div>`;
    });
    html += '</div></div>';
  }

  // ReAct Trace
  if (agent.react_trace && agent.react_trace.length) {
    html += `<div class="collapsible"><button class="collapsible-toggle" onclick="this.nextElementSibling.classList.toggle('open')">🧠 Reasoning (${agent.react_trace.length} steps)</button><div class="collapsible-body">`;
    agent.react_trace.forEach(step => {
      html += `<div style="margin-bottom:8px"><strong>Step ${step.step}</strong>`;
      if (step.thought) html += `<br>💭 ${escapeHtml(step.thought.slice(0, 300))}`;
      if (step.tools_called) step.tools_called.forEach(tc => { html += `<br>🔧 <code>${tc.name}</code>`; });
      if (step.observations) step.observations.forEach(o => { html += `<br><span style="color:var(--text-muted)">👁 ${escapeHtml(o.slice(0, 200))}</span>`; });
      html += '</div>';
    });
    html += '</div></div>';
  }

  html += '</div>';
  div.innerHTML = html;
  c.appendChild(div);
  renderMath(div);
  scrollBottom();
}

function renderMindResponse(mind) {
  const c = $('chatContainer');
  const div = document.createElement('div');
  div.className = 'msg msg-assistant';

  let html = `<div class="agent-card" style="border-color:var(--primary)">`;
  html += `<span class="agent-badge badge-mind">🧠 MIND AGENT — SYNTHESIZED ANSWER</span>`;
  html += `<div class="agent-content">${renderMarkdown(mind.content)}</div>`;

  if (mind.references && mind.references.length) {
    html += `<div style="margin-top:12px"><strong>📎 References</strong><table class="ref-table"><thead><tr><th>#</th><th>Source</th><th>Agent</th><th>Snippet</th></tr></thead><tbody>`;
    mind.references.forEach(r => {
      html += `<tr><td><span class="ref-num">${r.number}</span></td><td>${escapeHtml(r.source_file)}</td><td>${escapeHtml(r.source_agent)}</td><td><em>${escapeHtml(r.snippet.slice(0, 80))}...</em></td></tr>`;
    });
    html += '</tbody></table></div>';
  }

  const confPct = Math.round(mind.confidence_score * 100);
  html += `<div class="confidence-bar">Confidence: ${confPct}%<div class="conf-track"><div class="conf-fill" style="width:${confPct}%;background:var(--accent-green)"></div></div></div>`;
  html += '</div>';

  div.innerHTML = html;
  c.appendChild(div);
  renderMath(div);
  scrollBottom();
}

function showLoading() {
  const c = $('chatContainer');
  const div = document.createElement('div');
  div.className = 'loading';
  div.innerHTML = `<div class="loading-dots"><span></span><span></span><span></span></div> Thinking...`;
  c.appendChild(div);
  scrollBottom();
  return div;
}

function appendError(msg) {
  const c = $('chatContainer');
  const div = document.createElement('div');
  div.className = 'msg msg-assistant';
  div.innerHTML = `<div class="agent-card" style="border-color:var(--accent-red)"><span class="agent-badge" style="background:var(--accent-red);color:#fff">❌ Error</span><div class="agent-content">${escapeHtml(msg)}</div></div>`;
  c.appendChild(div);
  scrollBottom();
}

function scrollBottom() {
  const c = $('chatContainer');
  setTimeout(() => c.scrollTop = c.scrollHeight, 50);
}


// ═══════════════════════════════════════════════════
//  Markdown + Math Rendering
// ═══════════════════════════════════════════════════

function escapeHtml(str) {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}

function renderMarkdown(text) {
  if (!text) return '';
  let html = text;

  // Protect LaTeX blocks from markdown processing
  const latexBlocks = [];
  html = html.replace(/\$\$([\s\S]*?)\$\$/g, (_, eq) => { latexBlocks.push({ display: true, eq }); return `%%LATEX${latexBlocks.length - 1}%%`; });
  html = html.replace(/\$([^\$\n]+?)\$/g, (_, eq) => { latexBlocks.push({ display: false, eq }); return `%%LATEX${latexBlocks.length - 1}%%`; });

  // Protect code blocks
  const codeBlocks = [];
  html = html.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => { codeBlocks.push({ lang, code }); return `%%CODE${codeBlocks.length - 1}%%`; });

  // Headers
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
  html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
  html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');

  // Bold, italic, inline code
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

  // Tables
  html = html.replace(/^(\|.+\|)\n(\|[-:| ]+\|)\n((?:\|.+\|\n?)*)/gm, (_, hdr, sep, body) => {
    const headers = hdr.split('|').filter(c => c.trim()).map(c => `<th>${c.trim()}</th>`).join('');
    const rows = body.trim().split('\n').map(row => {
      const cells = row.split('|').filter(c => c.trim()).map(c => `<td>${c.trim()}</td>`).join('');
      return `<tr>${cells}</tr>`;
    }).join('');
    return `<table><thead><tr>${headers}</tr></thead><tbody>${rows}</tbody></table>`;
  });

  // Lists
  html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
  html = html.replace(/^(\d+)\. (.+)$/gm, '<li>$2</li>');
  html = html.replace(/((?:<li>.*<\/li>\n?)+)/g, '<ul>$1</ul>');

  // Blockquotes
  html = html.replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>');

  // Paragraphs
  html = html.replace(/\n\n/g, '</p><p>');
  html = '<p>' + html + '</p>';
  html = html.replace(/<p><\/p>/g, '');
  html = html.replace(/<p>(<h[1-3]>)/g, '$1');
  html = html.replace(/(<\/h[1-3]>)<\/p>/g, '$1');
  html = html.replace(/<p>(<ul>)/g, '$1');
  html = html.replace(/(<\/ul>)<\/p>/g, '$1');
  html = html.replace(/<p>(<table>)/g, '$1');
  html = html.replace(/(<\/table>)<\/p>/g, '$1');
  html = html.replace(/<p>(<blockquote>)/g, '$1');
  html = html.replace(/(<\/blockquote>)<\/p>/g, '$1');

  // Restore code blocks
  codeBlocks.forEach((cb, i) => {
    html = html.replace(`%%CODE${i}%%`, `<pre><code>${escapeHtml(cb.code.trim())}</code></pre>`);
  });

  // Restore LaTeX
  latexBlocks.forEach((lb, i) => {
    if (lb.display) {
      html = html.replace(`%%LATEX${i}%%`, `<span class="katex-display" data-latex="${escapeHtml(lb.eq.trim())}"></span>`);
    } else {
      html = html.replace(`%%LATEX${i}%%`, `<span class="katex-inline" data-latex="${escapeHtml(lb.eq.trim())}"></span>`);
    }
  });

  return html;
}

function renderMath(container) {
  if (typeof katex === 'undefined') {
    setTimeout(() => renderMath(container), 200);
    return;
  }

  container.querySelectorAll('.katex-display').forEach(el => {
    try {
      katex.render(el.dataset.latex, el, { displayMode: true, throwOnError: false });
    } catch {}
  });
  container.querySelectorAll('.katex-inline').forEach(el => {
    try {
      katex.render(el.dataset.latex, el, { displayMode: false, throwOnError: false });
    } catch {}
  });
}


// ── Init ──
document.addEventListener('DOMContentLoaded', () => {
  checkHealth();
  loadThreads();
});
