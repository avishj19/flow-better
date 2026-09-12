import {content} from './content.js';

const $ = s => document.querySelector(s);

$('#hero-title').textContent = content.hero.heading;
$('#hero-description').textContent = content.hero.description;

const money = n => new Intl.NumberFormat('en-US', {style: 'currency', currency: 'USD', maximumFractionDigits: 0}).format(n);
const number = n => new Intl.NumberFormat('en-US').format(n);
const tabs = $('#strategy-tabs');

content.strategies.forEach((s, i) => {
  const b = document.createElement('button');
  b.className = 'strategy-tab';
  b.id = `tab-${s.id}`;
  b.role = 'tab';
  b.setAttribute('aria-controls', 'strategy-detail');
  b.setAttribute('aria-selected', String(i === 1));
  b.tabIndex = i === 1 ? 0 : -1;
  b.innerHTML = `<span>${s.theme}</span><b>${s.name}</b>`;
  b.addEventListener('click', () => select(i));
  b.addEventListener('keydown', e => {
    let next;
    if (e.key === 'ArrowRight') next = (i + 1) % 3;
    if (e.key === 'ArrowLeft') next = (i + 2) % 3;
    if (e.key === 'Home') next = 0;
    if (e.key === 'End') next = 2;
    if (next !== undefined) {
      e.preventDefault();
      select(next);
      tabs.children[next].focus();
    }
  });
  tabs.append(b);
});

function select(index) {
  const s = content.strategies[index];
  [...tabs.children].forEach((t, i) => {
    t.setAttribute('aria-selected', String(i === index));
    t.tabIndex = i === index ? 0 : -1;
  });
  const metrics = [
    ['Financial cost', money(s.cost), 'Modeled operating and recovery cost', s.cost / 37000 * 100],
    ['Passenger impact', number(s.passengers), 'Model points · lower is better', s.passengers / 305015 * 100],
    ['Network penalty', number(s.network), 'Model points · missed overnight positions', s.network / 20000 * 100],
    ['Crew buffer', `${s.crew > 0 ? '+' : ''}${s.crew} min`, 'Minimum remaining modeled duty time', Math.min(100, Math.abs(s.crew) / 95 * 100)]
  ];
  const panel = $('#strategy-detail');
  panel.setAttribute('aria-labelledby', `tab-${s.id}`);
  panel.style.animation = 'none';
  void panel.offsetWidth;
  panel.style.animation = '';
  panel.innerHTML = `<div class="strategy-summary"><span class="status ${s.feasible ? '' : 'blocked'}">${s.feasible ? 'FEASIBLE IN THE MODEL' : 'BLOCKED · CREW CONSTRAINT'}</span><h3>${s.delays}</h3><p>${s.detail}</p><ul>${s.actions.map(x => `<li>${x}</li>`).join('')}</ul></div><div class="strategy-metrics">${metrics.map(([label, value, hint, width], i) => `<div class="measure ${i === 3 && s.crew < 0 ? 'negative' : ''}"><label>${label}</label><strong>${value}</strong><div class="meter" aria-hidden="true"><span style="width:${width}%"></span></div><small>${hint}</small></div>`).join('')}</div>`;
}

select(1);

$('#scenario-toggle').addEventListener('click', () => {
  const b = $('#scenario-toggle');
  const open = b.getAttribute('aria-expanded') === 'true';
  b.setAttribute('aria-expanded', String(!open));
  $('#scenario-details').hidden = open;
  b.querySelector('span').textContent = open ? '+' : '−';
});


const insightForm = $('#insight-form');
if (insightForm) {
  insightForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const status = $('#insight-status');
    const box = $('#insight-results');
    const btn = $('#insight-submit');
    const origin = $('#insight-origin').value;
    const destination = $('#insight-destination').value;
    const month = Number($('#insight-month').value);
    const year = Number($('#insight-year').value);
    if (origin === destination) {
      status.textContent = 'Pick two different airports.';
      box.hidden = true;
      return;
    }
    btn.disabled = true;
    status.textContent = 'Reading decade logs…';
    box.hidden = true;
    try {
      const res = await fetch('/api/flight-insight', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({origin, destination, month, year})
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw Error(typeof data.detail === 'string' ? data.detail : 'Insight request failed');
      const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
      const cards = data.airports.map(a => {
        const flaws = (a.flaw_days || []).slice(0, 2).map(f =>
          `<div class="flaw"><b>${esc(f.date)}</b> · ${esc(f.pattern || 'disruption')}<br>${esc(f.desk_read || '')}</div>`
        ).join('');
        return `<article class="insight-card"><h3>${esc(a.airport)}</h3><span class="role">${esc(a.role)}</span><ul>${(a.bullets||[]).map(b=>`<li>${esc(b)}</li>`).join('')}</ul>${flaws}</article>`;
      }).join('');
      box.innerHTML = `<div class="insight-takeaways"><h3>What the logs say</h3><ul>${(data.takeaways||[]).map(t=>`<li>${esc(t)}</li>`).join('')}</ul></div><div class="insight-cards">${cards}</div><p class="insight-note">${esc(data.scope)}</p>`;
      box.hidden = false;
      status.textContent = `${origin} → ${destination} · ${month}/${year}`;
    } catch (err) {
      status.textContent = err.message || 'Could not load insights';
      box.hidden = true;
    } finally {
      btn.disabled = false;
    }
  });
}
