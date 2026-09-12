(() => {
  const $ = (id) => document.getElementById(id);
  const deskInput = $('desk');
  const message = $('message');
  const issueGrid = $('issueGrid');
  const pickCount = $('pickCount');
  const runBtn = $('runScenario');
  const selected = new Set();
  let issuesMeta = null;
  let currentRun = null;

  function deskHeaders() {
    return { 'X-IROP-Desk': (deskInput.value || 'default').trim().toLowerCase() || 'default' };
  }

  function money(n) {
    return `$${Number(n || 0).toLocaleString()}`;
  }

  function setMsg(text, ok = false) {
    message.textContent = text || '';
    message.style.color = ok ? 'var(--good)' : 'var(--warn)';
  }

  async function api(path, opts = {}) {
    const headers = { ...(opts.headers || {}), ...deskHeaders() };
    if (opts.body && !headers['Content-Type']) headers['Content-Type'] = 'application/json';
    const res = await fetch(path, { ...opts, headers });
    let data = null;
    try { data = await res.json(); } catch (_) { /* empty */ }
    if (!res.ok) {
      const detail = (data && (data.detail || data.message)) || res.statusText;
      throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
    }
    return data;
  }

  function updatePickUi() {
    const n = selected.size;
    pickCount.textContent = `${n} / 4`;
    runBtn.disabled = n < 1 || n > 4;
    issueGrid.querySelectorAll('.issue-card').forEach((btn) => {
      btn.classList.toggle('selected', selected.has(btn.dataset.id));
    });
  }

  function renderIssues(catalog) {
    issuesMeta = catalog;
    issueGrid.innerHTML = '';
    const byCat = {};
    for (const issue of catalog.issues) {
      (byCat[issue.category] ||= []).push(issue);
    }
    for (const [cat, items] of Object.entries(byCat)) {
      for (const issue of items) {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'issue-card';
        btn.dataset.id = issue.id;
        btn.innerHTML = `
          <span class="cat">${issue.category_label || cat}</span>
          <strong>${issue.title}</strong>
          <p class="blurb">${issue.blurb}</p>
          <p class="basis">${issue.decade_basis}</p>
          <span class="sev">severity ${issue.severity}/5</span>`;
        btn.addEventListener('click', () => {
          if (selected.has(issue.id)) selected.delete(issue.id);
          else if (selected.size < 4) selected.add(issue.id);
          else setMsg('Pick at most 4 issues.');
          updatePickUi();
        });
        issueGrid.appendChild(btn);
      }
    }
    updatePickUi();
  }

  function metric(label, value) {
    return `<div class="metric"><b>${value}</b><span>${label}</span></div>`;
  }

  function renderSituation(run) {
    const sit = run.situation;
    const section = $('situation');
    section.hidden = false;
    $('sitHeadline').textContent = sit.headline;
    $('sitMeta').textContent = `${run.ground.as_of} · seed ${run.seed} · ${run.issues.map((i) => i.title).join(' · ')}`;
    const sev = sit.severity_label || '';
    const pill = $('severityPill');
    pill.textContent = `${sev} · score ${sit.severity}`;
    pill.className = `pill ${sev === 'critical' ? 'bad' : sev === 'elevated' ? 'warn' : 'good'}`;
    $('sitMetrics').innerHTML = [
      metric('Pax exposed', sit.passengers_exposed),
      metric('Connection risk', sit.connection_risk_pax),
      metric('Gates open', sit.gates_available),
      metric('De-ice queue', `${sit.deice_queue_minutes}m`),
      metric('Blocked deps', sit.blocked_departures.length || 0),
    ].join('');
    $('sitAlerts').innerHTML = (sit.alerts || []).map((a) => `<li>${a}</li>`).join('') || '<li>No alerts</li>';
    $('sitDecade').innerHTML = (sit.decade_links || []).map((a) => `<li>${a}</li>`).join('');

    const acRows = (sit.aircraft || [])
      .filter((a) => a.airport === 'PIT' || a.status !== 'spare_remote')
      .map((a) => `<tr>
        <td>${a.tail}</td><td>${a.gate || '—'}</td><td>${a.status}</td>
        <td>${a.next_flight || '—'}</td><td>${a.next_dest || '—'}</td>
        <td>${a.pax_booked || 0}</td><td>${a.crew || '—'}</td>
      </tr>`).join('');
    $('sitAircraft').innerHTML = `<table><thead><tr>
      <th>Tail</th><th>Gate</th><th>Status</th><th>Flight</th><th>Dest</th><th>Pax</th><th>Crew</th>
    </tr></thead><tbody>${acRows}</tbody></table>`;

    const crewRows = (sit.crews || []).map((c) => `<tr>
      <td>${c.id}</td><td>${c.status}</td><td>${c.location}</td>
      <td>${c.remaining_buffer}m</td><td>${c.qualified}</td>
    </tr>`).join('');
    $('sitCrews').innerHTML = `<table><thead><tr>
      <th>Crew</th><th>Status</th><th>Loc</th><th>Buffer</th><th>Qual</th>
    </tr></thead><tbody>${crewRows}</tbody></table>`;
  }

  function renderOptions(run) {
    const section = $('options');
    section.hidden = false;
    const list = $('optionList');
    const decision = $('decision');
    decision.hidden = true;
    list.innerHTML = '';

    for (const opt of run.options || []) {
      const card = document.createElement('article');
      card.className = `option-card${opt.feasible ? '' : ' blocked'}`;
      const people = opt.people || {};
      const moneyParts = opt.money_breakdown || {};
      const moneyLine = Object.entries(moneyParts)
        .filter(([, v]) => v)
        .map(([k, v]) => `${k.replace(/_/g, ' ')} ${money(v)}`)
        .join(' · ');
      card.innerHTML = `
        <div class="option-top">
          <div>
            <h3>${opt.title}</h3>
            <p class="summary">${opt.summary}</p>
          </div>
          <span class="pill ${opt.feasible ? 'good' : 'bad'}">${opt.badge || (opt.feasible ? 'feasible' : 'blocked')}</span>
        </div>
        <div class="option-stats">
          ${metric('Cash', money(opt.cost))}
          ${metric('Pax delay-min', Number(opt.passenger_delay_minutes || 0).toLocaleString())}
          ${metric('Missed connects', opt.missed_connecting_passengers || 0)}
          ${metric('Cancels', (opt.flights_cancelled || []).join(', ') || 'none')}
        </div>
        <p class="people"><b>People:</b> ${people.passengers_affected || 0} pax · ${people.crews_on_duty || 0} crews ·
          ${people.ramp_agents_extra || 0} extra ramp · ${people.hotel_rooms || 0} hotel rooms</p>
        <p class="money"><b>Money:</b> ${moneyLine || money(opt.cost)}</p>
        <p class="regs"><b>Regulation / notes:</b> ${(opt.regulation || []).join(' · ')}</p>
        <ul class="tradeoffs">${(opt.tradeoffs || []).map((t) => `<li>${t}</li>`).join('')}</ul>
        ${opt.why_blocked ? `<p class="regs"><b>Blocked:</b> ${opt.why_blocked}</p>` : ''}
        <div class="option-actions"></div>`;
      const actions = card.querySelector('.option-actions');
      if (opt.feasible && run.phase === 'options') {
        const btn = document.createElement('button');
        btn.textContent = 'Approve in simulation →';
        btn.addEventListener('click', () => approve(opt.id));
        actions.appendChild(btn);
      } else if (run.phase === 'done' && run.selected_option_id === opt.id) {
        actions.innerHTML = '<span class="pill good">Selected</span>';
      }
      list.appendChild(card);
    }

    if (run.phase === 'done' && run.decision) {
      decision.hidden = false;
      const d = run.decision;
      decision.innerHTML = `<strong>Approved:</strong> ${d.title} · ${money(d.cost)} ·
        pax delay-min ${Number(d.passenger_delay_minutes || 0).toLocaleString()} ·
        cancels ${(d.flights_cancelled || []).join(', ') || 'none'}`;
    }
  }

  async function approve(optionId) {
    if (!currentRun) return;
    try {
      setMsg('Approving…');
      currentRun = await api(`/api/scenarios/${currentRun.id}/approve`, {
        method: 'POST',
        body: JSON.stringify({ option_id: optionId, confirm: true }),
      });
      renderSituation(currentRun);
      renderOptions(currentRun);
      setMsg('Decision saved in this desk.', true);
      loadHistory();
    } catch (err) {
      setMsg(err.message || String(err));
    }
  }

  async function runScenario() {
    const ids = [...selected];
    if (!ids.length) return;
    try {
      setMsg('Building ground picture…');
      currentRun = await api('/api/scenarios', {
        method: 'POST',
        body: JSON.stringify({
          seed: Number($('seed').value) || 42,
          issue_ids: ids,
        }),
      });
      renderSituation(currentRun);
      renderOptions(currentRun);
      $('situation').scrollIntoView({ behavior: 'smooth', block: 'start' });
      setMsg(`Scenario ready · ${currentRun.options.filter((o) => o.feasible).length} feasible options.`, true);
      loadHistory();
    } catch (err) {
      setMsg(err.message || String(err));
    }
  }

  async function loadHistory() {
    try {
      const rows = await api('/api/scenarios');
      const box = $('historyList');
      if (!rows.length) {
        box.innerHTML = '<p class="muted">No saved scenarios in this desk yet.</p>';
        return;
      }
      box.innerHTML = rows.map((r) => `
        <div class="history-item">
          <div>
            <strong>${r.name || r.id}</strong>
            <div class="muted">seed ${r.seed} · ${r.phase} · rev ${r.revision}</div>
          </div>
          <button type="button" class="quiet" data-id="${r.id}">Open</button>
        </div>`).join('');
      box.querySelectorAll('button[data-id]').forEach((btn) => {
        btn.addEventListener('click', async () => {
          try {
            currentRun = await api(`/api/scenarios/${btn.dataset.id}`);
            renderSituation(currentRun);
            renderOptions(currentRun);
            setMsg(`Loaded ${currentRun.name}`, true);
          } catch (err) {
            setMsg(err.message || String(err));
          }
        });
      });
    } catch (err) {
      setMsg(err.message || String(err));
    }
  }

  $('runScenario').addEventListener('click', runScenario);
  $('refresh').addEventListener('click', loadHistory);
  $('switchDesk').addEventListener('click', () => {
    selected.clear();
    updatePickUi();
    currentRun = null;
    $('situation').hidden = true;
    $('options').hidden = true;
    setMsg(`Desk set to ${(deskInput.value || 'default').trim().toLowerCase()}`, true);
    loadHistory();
  });

  (async () => {
    try {
      const catalog = await api('/api/issues');
      renderIssues(catalog);
      await loadHistory();
    } catch (err) {
      setMsg(err.message || String(err));
    }
  })();
})();
