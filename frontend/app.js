const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num = n => Number(n).toLocaleString('en-US');
const money = n => '$' + num(n);
const time = n => n == null ? '—' : `${n >= 1440 ? 'D+1 ' : ''}${String(Math.floor(n / 60) % 24).padStart(2,'0')}:${String(n % 60).padStart(2,'0')}`;
let state = null, selected = null, exp = null, busy = false;
let desk = localStorage.getItem('irop-desk') || 'default';
$('desk').value = desk;
const modern = () => state?.scenario.model_version === 2;
async function api(path, body) {
  const response = await fetch('/api/' + path, {method: body === undefined ? 'GET' : 'POST', headers: {'Content-Type':'application/json','X-IROP-Desk':desk}, body: body === undefined ? undefined : JSON.stringify(body)});
  const result = await response.json().catch(() => ({detail:'Request rejected'}));
  if (!response.ok) throw Error(typeof result.detail === 'string' ? result.detail : JSON.stringify(result.detail));
  return result;
}
function message(text,error=false) { $('message').textContent=text; $('message').className=error?'error':''; }
async function action(fn) {
  if (busy) return;
  busy=true; document.querySelectorAll('button:not(#optionList button)').forEach(b=>b.disabled=true); if(state)renderOptions();
  try { await fn(); } catch(error) { message(error.message,true); }
  finally { busy=false; document.querySelectorAll('button:not(#optionList button)').forEach(b=>b.disabled=false); if(state)render(); else $('scenario').hidden=true; window.refreshLiveControls?.(); }
}
function accept(result) {
  state=result; exp=state.experiments.at(-1);
  selected=exp?.options.find(o=>o.plan===selected?.plan)||exp?.options.find(o=>o.feasible)||exp?.options[0]||null;
  render();
}
function currentView() { return $('view').value==='preview'?selected:state[$('view').value]; }
function render() {
  if(!state)return;
  $('empty').hidden=true; $('scenario').hidden=false;
  $('scenarioName').textContent=state.name+(modern()?' · four-pillar model':' · archived model')+(state.live_weather?' · observed weather applied':'');
  $('phase').textContent=state.phase.toUpperCase();$('revision').textContent=`Revision ${state.revision} · ${state.id.slice(0,8)}`;
  const option=state.current,m=option.metrics, scores=option.scores;
  const metrics=scores ? [
    ['Financial cost',money(scores.financial_cost),'delay + ferries + cancellations + reserve crew'],
    ['Passenger impact',num(scores.passenger_impact),'passenger minutes + missed-connection points'],
    ['Network penalty',num(scores.network_health),'20,000 points per aircraft out of position at cutoff'],
    ['Crew buffer',`${scores.crew_buffer.minutes_remaining}m`,scores.crew_buffer.minutes_remaining<0?'Hard constraint failed · modeled duty':'Minimum remaining across operating crews']
  ] : [['Financial cost',money(m.cost),'Archived cost formula'],['Passenger delay',num(m.passenger_minutes),'Archived passenger minutes'],['Missed connections',m.missed_pax,'Archived result'],['Model version','1','Generate a new scenario to use four pillars']];
  $('metrics').innerHTML=metrics.map(([label,value,note])=>`<div class="metric"><span class="label">${label}</span><strong>${value}</strong><small>${note}</small></div>`).join('');
  const aps=state.scenario.airports, hub=aps.PIT;
  $('network').innerHTML=Object.entries(aps).filter(([a])=>a!=='PIT').map(([a,p])=>`<path d="M ${hub.x} ${hub.y} Q ${(hub.x+p.x)/2} ${Math.min(hub.y,p.y)-35} ${p.x} ${p.y}" stroke="#436b88" stroke-width="1.5" fill="none" stroke-dasharray="4 4"/>`).join('')+Object.entries(aps).map(([a,p])=>`<circle cx="${p.x}" cy="${p.y}" r="${a==='PIT'?23:14}" fill="#1b3146"/><circle cx="${p.x}" cy="${p.y}" r="${a==='PIT'?9:5}" fill="${state.phase!=='baseline'&&state.scenario.disruptions.some(d=>d.airport===a)?'#efad58':'#6ecdc0'}"/><text x="${p.x}" y="${p.y+36}" text-anchor="middle" font-weight="700">${a}</text>${a==='PIT'?`<text x="${p.x}" y="${p.y+52}" text-anchor="middle" style="font-size:9px">OVERNIGHT HUB</text>`:''}`).join('');
  $('disruptions').innerHTML=state.scenario.disruptions.map(d=>`<div class="disruption"><b>${esc(d.id)}</b><div>${esc(d.label)}<small>${esc(d.kind.replaceAll('_',' ').toUpperCase())} · ${state.phase==='baseline'?'Ready to inject':'Applied'}</small></div></div>`).join('');
  $('signals').innerHTML=(state.scenario.unstructured_signals||[]).map(s=>`<div class="signal-box"><span class="eyebrow">UNSTRUCTURED INPUT · ${esc(s.id)}</span><blockquote>${esc(s.text)}</blockquote><p>Bounded parser extracts airport and added turnaround minutes. Source window: ${time(s.start)}–${time(s.end)}. Original text is preserved as evidence.</p></div>`).join('');
  $('disrupt').disabled=busy||!modern()||state.phase!=='baseline'; $('disrupt').textContent=state.phase==='baseline'?'Inject four disruptions →':'Disruptions applied ✓';
  $('evaluate').disabled=busy||!modern()||state.phase!=='disrupted';
  const d=state.disrupted;
  $('cascade').textContent=d?`Without recovery: ${d.metrics.delayed_flights} delayed flights · ${d.metrics.missed_pax} missed connecting passengers · ${d.evidence.filter(e=>e.hard!==false&&!e.passed).length} failed hard checks.`:'';
  renderOptions();renderTimeline();renderEvents();window.refreshLiveControls?.();
}
function selectPlan(plan) { selected=exp.options.find(o=>o.plan===plan);$('view').value='preview';renderOptions();renderTimeline(); }
async function approvePlan(plan) {
  await action(async()=>{
    $('view').value='current';accept(await api(`scenarios/${state.id}/approve`,{revision:state.revision,experiment_id:exp.id,plan,confirm:true}));
    message('Approved in simulation. The chosen schedule, four scores and evidence are saved.');await loadHistory();
  });
}
function renderOptions() {
  const current=!!(modern()&&state.phase==='disrupted'&&exp?.status==='completed'&&exp.revision===state.revision&&!busy);
  const options=modern()&&exp?.options.every(o=>o.scores)?exp.options:[];
  const placeholder=!modern()?'Archived scenario: generate a new schedule to use the three recovery strategies.':state.phase==='baseline'?'Inject the four disruptions, then compare the three recovery strategies.':'Compare plans to calculate financial, passenger, network and crew outcomes.';
  window.renderRecoveryCards?.({options,selectedPlan:selected?.plan,onSelect:selectPlan,onApprove:approvePlan,current,placeholder});
  $('optionStatus').textContent=exp&&exp.revision!==state.revision ? (state.phase==='recovered'?'Decision saved. These are the evaluated options for the approved revision.':'Earlier-revision experiment: review only. Compare again before approval.') : exp?.status==='failed' ? 'Planner failed. No option from this experiment can be approved.' : 'Three independent impact measures, plus crew as a hard constraint. Relative bars include rejected candidates. No hidden weighted score.';
  if(!options.length||!selected?.scores) { $('selection').innerHTML='';$('workflow').innerHTML='';return; }
  const failures=selected.evidence.filter(e=>e.hard!==false&&!e.passed);
  $('selection').innerHTML=`<div class="selection"><div class="section-head"><div><span class="eyebrow">SELECTED PLAN EVIDENCE</span><h3>${esc(selected.title)} <span class="pill">${selected.feasible?'PASSES MODELED CONSTRAINTS':'BLOCKED'}</span></h3><p>${esc(selected.rationale.rejection||'Inspect the schedule, overnight positions and exact check results before choosing a trade-off.')}</p></div></div><details ${failures.length?'open':''}><summary>Constraint evidence · ${failures.length} failed hard checks</summary><label><input id="allChecks" type="checkbox"> Show all checks and score evidence</label><div class="checks" id="checks"></div></details><details><summary>Overnight aircraft positions and crew buffers</summary><div class="checks"><table><thead><tr><th>Aircraft</th><th>At cutoff</th><th>Required hub</th><th>Cutoff</th><th>Penalty</th></tr></thead><tbody>${selected.details.overnight_positions.map(p=>`<tr><td>${p.tail}</td><td>${esc(p.position)}</td><td>${p.hub}</td><td>${time(p.deadline)}</td><td>${num(p.penalty)}</td></tr>`).join('')}</tbody></table><table><thead><tr><th>Crew</th><th>Report</th><th>Release</th><th>Deadline</th><th>Buffer</th></tr></thead><tbody>${selected.details.crew_buffers.map(c=>`<tr><td>${c.crew}</td><td>${time(c.report)}</td><td>${time(c.release)}</td><td>${time(c.deadline)}</td><td class="${c.minutes_remaining<0?'fail':'pass'}">${c.minutes_remaining}m</td></tr>`).join('')}</tbody></table></div></details></div>`;
  renderChecks();$('allChecks').onchange=renderChecks;
  $('workflow').innerHTML=`<details><summary>${exp.mode==='local'?'Deterministic planner · no LLM':'OpenAI planner · advisory'} / ${exp.status} · ${exp.trace.length} trace events</summary><p>${esc(exp.error||exp.explanation)}</p>${exp.trace.map(t=>`<div class="trace"><b>${esc(t.role)}</b> / ${esc(t.action)}<details><summary>Execution record</summary><pre>${esc(JSON.stringify(t.data,null,2))}</pre></details></div>`).join('')}</details>`;
}
function renderChecks() {
  const checks=selected.evidence.filter(e=>$('allChecks')?.checked||(e.hard!==false&&!e.passed));
  $('checks').innerHTML=checks.length?`<table><thead><tr><th>Evidence ID</th><th>Constraint</th><th>Subject</th><th>Result</th><th>Observed math</th></tr></thead><tbody>${checks.map(e=>`<tr><td><code>${esc(e.id)}</code></td><td>${esc(e.kind)}</td><td>${esc(e.subject)}</td><td class="${e.passed?'pass':'fail'}">${e.hard===false?'SCORE':e.passed?'PASS':'FAIL'}</td><td>${esc(e.detail)}</td></tr>`).join('')}</tbody></table>`:'<p>All hard constraints pass. Show all evidence to inspect the formulas and source context.</p>';
}
function renderTimeline() {
  const view=currentView();if(!view){$('flightTable').innerHTML='<p class="placeholder">Select an available state or a recovery plan.</p>';$('connectionTable').innerHTML='';return;}
  const rotation=$('rotation').value,fs=view.flights.filter(f=>rotation==='all'||f.rotation===Number(rotation));
  const lo=Math.min(...state.scenario.flights.map(f=>f.dep))-30,hi=Math.max(1440,...view.flights.filter(f=>f.actual_arr!=null).map(f=>f.actual_arr))+30;
  const width=n=>100*n/(hi-lo),left=n=>width(n-lo);
  $('flightTable').innerHTML=`<div class="table-wrap"><table><thead><tr><th>Flight / route</th><th>Aircraft · crew</th><th>Departure</th><th>Outcome</th><th><div class="time-axis"><span>${time(lo)}</span><span>${time(Math.round((lo+hi)/2))}</span><span>${time(hi)}</span></div></th><th>Why it changed</th></tr></thead><tbody>${fs.map(f=>`<tr><td><b>${f.id}</b>${f.ferry?' <span class="pill">FERRY</span>':''}<br>${f.origin} → ${f.destination}</td><td>${f.tail} · ${f.crew}</td><td>${time(f.actual_dep)}</td><td class="${f.cancelled||f.delay?'fail':'pass'}">${f.cancelled?'CANCELLED · pax +24h':f.delay?'+'+f.delay+'m':'On time'}</td><td><div class="flight-line" title="Planned ${time(f.dep)}–${time(f.arr)}${f.cancelled?'; cancelled':`; actual ${time(f.actual_dep)}–${time(f.actual_arr)}`}"><span class="bar ${f.cancelled?'cancelled':''}" style="left:${left(f.dep)}%;width:${width(f.arr-f.dep)}%"></span>${f.cancelled?'':`<span class="bar actual ${f.delay?'delayed':''}" style="left:${left(f.actual_dep)}%;width:${width(f.actual_arr-f.actual_dep)}%"></span>`}</div></td><td class="cause">${esc(f.causes.join(' · ')||'As scheduled')}</td></tr>`).join('')}</tbody></table></div>`;
  $('connectionTable').innerHTML=`<div class="table-wrap"><table><thead><tr><th>Group</th><th>Inbound → outbound</th><th>Passengers</th><th>Transfer time</th><th>Outcome in viewed state</th></tr></thead><tbody>${view.connections.map(c=>`<tr><td>${c.id}</td><td>${c.inbound} → ${c.outbound}</td><td>${c.pax}</td><td>${c.gap==null?'Cancelled itinerary':c.gap+'m / 35m'}</td><td class="${c.missed?'fail':'pass'}">${c.missed?'Connection missed':'Connection available'}</td></tr>`).join('')}</tbody></table></div>`;
}
function renderEvents() {
  $('events').innerHTML=state?`<details><summary>Current audit · ${state.events.length} events · ${state.experiments.length} experiments</summary>${state.events.map(e=>`<details><summary>${esc(e.action)} · ${esc(new Date(e.created).toLocaleTimeString())}</summary><pre>${esc(JSON.stringify(e.data,null,2))}</pre></details>`).join('')}${state.experiments.map(e=>`<details><summary>Experiment ${esc(e.id.slice(0,8))} · ${esc(e.mode)} · ${esc(e.status)} · revision ${e.revision}</summary><pre>${esc(JSON.stringify({options:e.options.map(o=>({plan:o.plan,feasible:o.feasible,scores:o.scores||o.metrics})),trace:e.trace},null,2))}</pre></details>`).join('')}</details>`:'';
}
async function loadHistory() {
  const history=await api('scenarios');
  $('historyList').innerHTML=history.length?history.map(h=>`<div class="history-row"><div>${esc(h.name)} <small>${esc(h.phase)} · revision ${h.revision} · ${esc(new Date(h.created).toLocaleString())}</small></div><button class="quiet" data-load="${h.id}">Open →</button></div>`).join(''):'<p class="muted">Saved scenarios, experiments and decisions appear here.</p>';
  $('historyList').querySelectorAll('[data-load]').forEach(b=>b.onclick=()=>action(async()=>{selected=null;$('view').value='current';accept(await api('scenarios/'+b.dataset.load));message(modern()?'Saved scenario loaded.':'Archived scenario loaded for review. Generate a new scenario to evaluate the new model.');}));
}
$('generate').onclick=()=>action(async()=>{selected=null;$('view').value='current';accept(await api('scenarios',{seed:Number($('seed').value)}));message('60-flight baseline validated. Inject four disruptions to start the recovery comparison.');await loadHistory();});
$('disrupt').onclick=()=>action(async()=>{accept(await api(`scenarios/${state.id}/disrupt`,{revision:state.revision}));message('Four disruptions applied. ORD’s ground-ops message now changes turnaround math.');await loadHistory();});
$('evaluate').onclick=()=>action(async()=>{message($('live').checked?'OpenAI is requesting bounded simulations…':'Calculating three strategies across four pillars…');accept(await api(`scenarios/${state.id}/experiments`,{revision:state.revision,mode:$('live').checked?'live':'local',consent:$('consent').checked}));message(exp?.status==='failed'?'Workflow failed: '+exp.error:'Three strategies calculated. Inspect the math, compare the trade-offs, and choose a feasible plan.',exp?.status==='failed');await loadHistory();});
$('live').onchange=()=>{$('consentLabel').hidden=!$('live').checked;$('aiStatus').textContent=$('live').checked?'OpenAI planner · aggregate evidence only':'Deterministic planner · no LLM';};
$('view').onchange=renderTimeline;$('rotation').onchange=renderTimeline;
for(let i=1;i<=10;i++)$('rotation').insertAdjacentHTML('beforeend',`<option value="${i}">Rotation ${i}</option>`);
$('refresh').onclick=()=>action(loadHistory);
$('switchDesk').onclick=()=>action(async()=>{const next=$('desk').value.trim().toLowerCase();if(!/^[a-z0-9][a-z0-9_-]{0,63}$/.test(next))throw Error('Use a valid desk ID.');desk=next;localStorage.setItem('irop-desk',desk);state=null;selected=null;exp=null;$('scenario').hidden=true;$('empty').hidden=false;$('events').innerHTML='';await loadHistory();await window.reloadObservations?.();message('Switched to desk '+desk);});
window.addEventListener('recovery-cards-ready',()=>{if(state)renderOptions();});
(async()=>{try{const status=await api('status');if(!status.live_available){$('live').disabled=true;$('aiStatus').textContent='Deterministic planner · live AI requires server credentials';}await loadHistory();}catch(error){message(error.message,true);}})();
