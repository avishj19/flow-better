let weatherSnapshot=null, aircraftSnapshot=null, liveConfig=null;
const HOLD={VFR:0,MVFR:15,IFR:30,LIFR:60};
const CAT_COLOR={VFR:'#54d1ae',MVFR:'#eab76f',IFR:'#efad58',LIFR:'#f18088',UNKNOWN:'#9baec2'};
const CAT_BG={VFR:'#12353a',MVFR:'#3a2f1c',IFR:'#3a2a1c',LIFR:'#3a1f28',UNKNOWN:'#1a2433'};

function freshWeather(s){return s?.source==='weather'&&s.environment==='production'&&s.rows.length===6&&s.rows.every(r=>{const age=Date.now()/1000-r.observed_epoch;return age>=-300&&age<=5400})}
function holdMinutes(r){let m=HOLD[r.category];if(m===undefined)return null;const gust=r.gust_kt;if(typeof gust==='number'&&gust>=30)m=Math.max(m,45);if(String(r.weather||'').includes('TS'))m=Math.max(m,60);return m}
window.liveWeatherOverlay=()=>{
  if(!freshWeather(weatherSnapshot))return null;
  const out={};
  weatherSnapshot.rows.forEach(r=>{out[r.airport]={category:r.category,color:CAT_COLOR[r.category]||CAT_COLOR.UNKNOWN,hold:holdMinutes(r)}});
  return out;
};

window.refreshLiveControls=()=>{
  if($('weatherFreshness'))$('weatherFreshness').textContent=freshWeather(weatherSnapshot)?'current enough to project':'missing or stale data; projection blocked';
  $('applyWeather').disabled=busy||!state||!modern()||!freshWeather(weatherSnapshot);
  $('fetchAircraft').disabled=busy||!liveConfig?.fr24_configured;
  if(typeof renderNetwork==='function'&&state)renderNetwork();
};

function renderHoldPreview(s){
  const box=$('holdPreview');
  if(!box)return;
  if(!s||!freshWeather(s)){box.hidden=true;box.innerHTML='';return}
  const rows=s.rows.map(r=>{const hold=holdMinutes(r);return {airport:r.airport,category:r.category,hold,color:CAT_COLOR[r.category]||CAT_COLOR.UNKNOWN}});
  const max=Math.max(60,...rows.map(r=>r.hold||0));
  const active=rows.filter(r=>r.hold>0).length;
  box.hidden=false;
  box.innerHTML=`<div class="hold-head"><span class="eyebrow">DEMO HOLD PREVIEW · SYNTHETIC 19:00</span><strong>${active?active+' airport'+(active===1?'':'s')+' would take a modeled hold':'Clear enough — zero holds under demo policy'}</strong></div><div class="hold-bars">${rows.map(r=>`<div class="hold-row"><span class="hold-code">${esc(r.airport)}</span><span class="hold-cat" style="--cat:${r.color}">${esc(r.category)}</span><div class="hold-track" aria-hidden="true"><i style="width:${100*(r.hold||0)/max}%;background:${r.color}"></i></div><span class="hold-min">${r.hold===null?'?':r.hold+'m'}</span></div>`).join('')}</div><p class="muted">Preview only. Apply to rewrite weather disruptions and bump the scenario revision.</p>`;
}

function showWeather(s){
  weatherSnapshot=s;
  const isFresh=freshWeather(s);
  const viz=$('weatherViz');
  if(viz){
    viz.classList.add('pulse');
    setTimeout(()=>viz.classList.remove('pulse'),700);
    viz.innerHTML=`<div class="weather-grid">${s.rows.map(r=>{
      const hold=holdMinutes(r);
      const color=CAT_COLOR[r.category]||CAT_COLOR.UNKNOWN;
      const bg=CAT_BG[r.category]||CAT_BG.UNKNOWN;
      const ageMin=Math.round((Date.now()/1000-r.observed_epoch)/60);
      return `<article class="wx-card" style="--cat:${color};--bg:${bg}"><header><b>${esc(r.airport)}</b><span class="wx-cat">${esc(r.category)}</span></header><div class="wx-stats"><span><small>Wind</small>${esc(r.wind_kt??'?')} kt${r.gust_kt!=null?' · G'+esc(r.gust_kt):''}</span><span><small>Vis</small>${esc(r.visibility_sm??'?')} SM</span><span><small>Hold</small>${hold===null?'?':hold+'m'}</span></div><footer>Obs ${esc(r.observed_at)} · ${ageMin<0?'future':ageMin+'m ago'}</footer></article>`;
    }).join('')}</div>`;
  }
  $('weatherLive').innerHTML=`<p><b>${esc(s.provider)} · ${esc(s.environment)} observation snapshot</b> · fetched ${esc(new Date(s.fetched_at).toLocaleString())}${s.cached?' · cached':''} · <span id="weatherFreshness">${isFresh?'current enough to project':'missing or stale data; projection blocked'}</span></p><details><summary>Original METAR reports / provenance</summary>${s.rows.map(r=>`<p><code>${esc(r.raw)}</code></p>`).join('')}<p>Snapshot ${esc(s.id)} · NOAA Aviation Weather Center</p></details>`;
  renderHoldPreview(s);
  const pill=$('networkPill');
  if(pill&&isFresh){
    const order=['LIFR','IFR','MVFR','VFR'];
    const worst=s.rows.reduce((w,r)=>order.indexOf(r.category)<order.indexOf(w)?r.category:w,'VFR');
    pill.textContent='LIVE WX · '+worst;
    pill.classList.add('live-pill');
  }
  const key=$('mapKey');
  if(key&&isFresh)key.innerHTML=`<span><i style="background:${CAT_COLOR.VFR}"></i> VFR</span><span><i style="background:${CAT_COLOR.MVFR}"></i> MVFR</span><span><i style="background:${CAT_COLOR.IFR}"></i> IFR</span><span><i style="background:${CAT_COLOR.LIFR}"></i> LIFR</span><span>Live NOAA categories · schematic</span>`;
  window.refreshLiveControls();
}

function showAircraft(s){
  aircraftSnapshot=s;
  const slow=s.rows.filter(r=>String(r.ground_status||'').toLowerCase().includes('low speed')).length;
  $('aircraftLive').innerHTML=`<div class="aircraft-summary"><span><b>${s.rows.length}</b> tracked</span><span><b>${slow}</b> low speed (unconfirmed)</span><span>${esc(s.environment)}</span>${s.potentially_truncated?'<span class="warn">50-object cap · incomplete</span>':''}</div><p class="muted"><b>${esc(s.provider)}</b> · fetched ${esc(s.fetched_at)}. Not a complete ground inventory.</p><div class="table-wrap"><table><thead><tr><th>Flight / registration</th><th>Type</th><th>Altitude ft</th><th>Speed kt</th><th>Observed</th><th>Ground status</th></tr></thead><tbody>${s.rows.map(r=>`<tr><td>${esc(r.flight)} / ${esc(r.registration)}</td><td>${esc(r.aircraft_type)}</td><td>${esc(r.altitude_ft)}</td><td>${esc(r.groundspeed_kt)}</td><td>${esc(r.observed_at||'Unknown')} ${Date.now()/1000-r.observed_epoch>300?'STALE':''}</td><td>${esc(r.ground_status)}</td></tr>`).join('')}</tbody></table></div>`;
}

$('fetchWeather').onclick=()=>action(async()=>{
  $('liveMessage').textContent='Requesting six airport observations from NOAA…';
  $('weatherViz')?.classList.add('loading');
  try{
    showWeather(await api('observations',{source:'weather'}));
    $('liveMessage').textContent='Weather snapshot saved. Category cards and hold preview updated from live METARs.';
  }finally{$('weatherViz')?.classList.remove('loading')}
});
$('fetchAircraft').onclick=()=>action(async()=>{
  $('liveMessage').textContent='Requesting a bounded Flightradar24 snapshot…';
  showAircraft(await api('observations',{source:'fr24',airport:$('liveAirport').value,consent:$('fr24Consent').checked}));
  $('liveMessage').textContent='Aircraft observations saved; no aircraft assignment was changed.';
});
$('applyWeather').onclick=()=>action(async()=>{
  const r=await api(`scenarios/${state.id}/weather-projection`,{revision:state.revision,snapshot_id:weatherSnapshot.id});
  selected=null;$('view').value='current';accept(r);
  $('liveMessage').textContent='Observation-based scenario revision saved. Earlier experiments are historical; compare plans again before approval.';
  message('Observed weather projected using the demo policy. No official closure is implied.');
  await loadHistory();
});

window.reloadObservations=async()=>{
  weatherSnapshot=null;aircraftSnapshot=null;
  if($('weatherViz'))$('weatherViz').innerHTML='<div class="weather-empty"><strong>No live weather yet</strong><span>Fetch public NOAA METARs for KPIT, KBOS, KJFK, KDCA, KORD, and KDTW. No API key required.</span></div>';
  $('weatherLive').textContent='Public NOAA airport observations · no API key required · manual refresh only.';
  if($('holdPreview')){$('holdPreview').hidden=true;$('holdPreview').innerHTML=''}
  $('aircraftLive').innerHTML='';
  const pill=$('networkPill');if(pill){pill.textContent='6 AIRPORTS';pill.classList.remove('live-pill')}
  const key=$('mapKey');if(key)key.innerHTML='<span><i class="green"></i> Hub network</span><span><i class="orange"></i> Airport disruption applied</span><span>Schematic · not geographic scale</span>';
  try{
    liveConfig=await api('observations/status');
    $('fr24Status').textContent=liveConfig.fr24_configured?`Server token configured · ${liveConfig.fr24_environment} · FR24 API credits may apply.`:'FR24 is not connected. Configure FR24_API_TOKEN on the server with a separate FR24 API subscription; never paste the token into this page or chat.';
    const list=await api('observations');
    const w=list.find(s=>s.source==='weather'),a=list.find(s=>s.source==='fr24');
    if(w)showWeather(w);if(a)showAircraft(a);
    window.refreshLiveControls();
  }catch(e){$('liveMessage').textContent=e.message}
};
window.reloadObservations();
setInterval(()=>{window.refreshLiveControls();if(weatherSnapshot)renderHoldPreview(weatherSnapshot)},30000);
