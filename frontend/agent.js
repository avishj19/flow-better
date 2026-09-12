let agentHighlights = [];
let agentBootstrapped = false;
let agentScenarioId = null;
const hh = m => m == null ? '—' : `${String(Math.floor(m / 60) % 24).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;

function overnightHubsFromState() {
  const hubs = {};
  for (const [tid, meta] of Object.entries(state.scenario.tails)) {
    const hub = meta.overnight_hub;
    hubs[hub] ??= { tails: [], deadlines: {} };
    hubs[hub].tails.push(tid);
    hubs[hub].deadlines[tid] = meta.overnight_by;
  }
  for (const hub of Object.keys(hubs)) hubs[hub].tails.sort();
  return hubs;
}

function renderHubChrome() {
  if (!state || !$('hubStrip')) return;
  const hubs = overnightHubsFromState();
  const pit = hubs.PIT || { tails: [] };
  const dtw = hubs.DTW || { tails: [] };
  const overnight = state.scenario.disruptions.find(d => d.kind === 'overnight');
  $('hubStrip').innerHTML = `
    <div class="hub-chip"><span>Primary overnight</span><strong>PIT · ${pit.tails.length}</strong></div>
    <div class="hub-chip"><span>Spare overnight</span><strong>DTW · ${dtw.tails.join(', ') || '—'}</strong></div>
    <div class="hub-chip"><span>Network penalty</span><strong>20,000 / miss</strong></div>
    <div class="hub-chip"><span>Overnight pressure</span><strong>${overnight ? overnight.id : 'None yet'}</strong></div>`;
  if ($('overnightFacts')) {
    const viewed = state.current?.details?.overnight_positions || [];
    const oop = viewed.filter(p => p.out_of_position);
    $('overnightFacts').innerHTML = `
      <div class="overnight-grid">
        <div><span class="label">PIT overnight tails</span><strong>${pit.tails.length}</strong><small>${pit.tails.join(' · ')}</small></div>
        <div><span class="label">DTW spare base</span><strong>${dtw.tails.join(', ') || '—'}</strong><small>Loyalty ferries from here</small></div>
        <div><span class="label">Viewed out of position</span><strong>${oop.length ? oop.map(p => p.tail).join(', ') : 'None'}</strong><small>${oop.length ? oop.map(p => `${p.tail} @ ${esc(p.position)}`).join(' · ') : 'All hubs covered at cutoff'}</small></div>
        <div><span class="label">Tightened cutoff</span><strong>${overnight ? hh(overnight.deadline) : '—'}</strong><small>${overnight ? esc(overnight.label) : 'Inject disruptions to activate D4'}</small></div>
      </div>`;
  }
}

function paintNetwork() {
  if (!state || !$('network')) return;
  const aps = state.scenario.airports, hub = aps.PIT, hubs = overnightHubsFromState();
  const weather = a => state.phase !== 'baseline' && state.scenario.disruptions.some(d => d.airport === a);
  const focus = a => agentHighlights.includes(a);
  const live = window.liveWeatherOverlay?.();
  const routes = Object.entries(aps).filter(([a]) => a !== 'PIT').map(([a, p]) => {
    const active = focus(a) || focus('PIT');
    return `<path class="route ${active ? 'lit' : ''}" d="M ${hub.x} ${hub.y} Q ${(hub.x + p.x) / 2} ${Math.min(hub.y, p.y) - 35} ${p.x} ${p.y}" fill="none"/>`;
  }).join('');
  const nodes = Object.entries(aps).map(([a, p]) => {
    const isHub = a === 'PIT', hit = focus(a), wx = weather(a);
    const overnightCount = (hubs[a]?.tails || []).length;
    const label = isHub ? 'OVERNIGHT HUB' : overnightCount ? `${overnightCount} overnight` : 'spoke';
    return `<g class="node ${hit ? 'focus' : ''} ${isHub ? 'hub' : ''}" data-airport="${a}">
      ${isHub ? `<circle cx="${p.x}" cy="${p.y}" r="34" class="hub-ring"/>` : ''}
      ${a === 'DTW' ? `<circle cx="${p.x}" cy="${p.y}" r="20" class="spare-ring"/>` : ''}
      <circle cx="${p.x}" cy="${p.y}" r="${isHub ? 23 : 14}" class="pad"/>
      <circle cx="${p.x}" cy="${p.y}" r="${isHub ? 9 : 5}" class="core ${wx ? 'wx' : ''}" ${live?.[a] ? `style="fill:${live[a].color}"` : ''}/>
      <text x="${p.x}" y="${p.y + 36}" text-anchor="middle" font-weight="700">${a}</text>
      <text x="${p.x}" y="${p.y + 52}" text-anchor="middle" class="${isHub ? 'hub-label' : 'park-label'}">${label}${live?.[a] ? ` · ${esc(live[a].category)}` : ''}</text>
    </g>`;
  }).join('');
  $('network').innerHTML = routes + nodes;
  $('network').querySelectorAll('[data-airport]').forEach(g => {
    g.style.cursor = 'pointer';
    g.onclick = () => askAgent('Show me ' + g.dataset.airport);
  });
}

function pushAgentBubble(role, title, body, meta) {
  const el = document.createElement('article');
  el.className = 'agent-bubble ' + role;
  el.innerHTML = `${title ? `<header>${esc(title)}</header>` : ''}<p>${esc(body)}</p>${meta ? `<footer>${esc(meta)}</footer>` : ''}`;
  $('agentLog').appendChild(el);
  $('agentLog').scrollTop = $('agentLog').scrollHeight;
}

function showSuggestions(list) {
  $('agentSuggestions').innerHTML = (list || []).map(t => `<button type="button" class="quiet tip" data-tip="${esc(t)}">${esc(t)}</button>`).join('');
  $('agentSuggestions').querySelectorAll('[data-tip]').forEach(b => b.onclick = () => askAgent(b.dataset.tip));
}

async function askAgent(text) {
  if (!state || !text || busy) return;
  pushAgentBubble('user', '', text);
  await action(async () => {
    const r = await api(`scenarios/${state.id}/agent`, { message: text });
    agentHighlights = r.highlights || [];
    pushAgentBubble('agent', r.title, r.reply, r.scope);
    showSuggestions(r.suggested);
    paintNetwork();
  });
}
window.askAgent = askAgent;

async function bootstrapAgent() {
  if (!state) return;
  renderHubChrome();
  paintNetwork();
  if (!agentBootstrapped || agentScenarioId !== state.id) {
    $('agentLog').innerHTML = '';
    agentBootstrapped = true;
    agentScenarioId = state.id;
    try {
      const starters = await api('agent/starters');
      showSuggestions(starters.prompts);
      const hello = await api(`scenarios/${state.id}/agent`, { message: 'Give me a desk status overview' });
      agentHighlights = hello.highlights || ['PIT'];
      pushAgentBubble('agent', hello.title, hello.reply, hello.scope);
      paintNetwork();
    } catch (e) {
      pushAgentBubble('agent', 'Desk agent', e.message || 'Unable to brief right now.');
    }
  }
}

$('agentForm').onsubmit = e => {
  e.preventDefault();
  const v = $('agentInput').value.trim();
  if (!v) return;
  $('agentInput').value = '';
  askAgent(v);
};

const _render = render;
render = function () {
  _render();
  if (state) bootstrapAgent();
  else {
    agentBootstrapped = false;
    agentHighlights = [];
    if ($('agentLog')) $('agentLog').innerHTML = '';
  }
};

$('switchDesk').addEventListener('click', () => { agentBootstrapped = false; agentHighlights = []; });
