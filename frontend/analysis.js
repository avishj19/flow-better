/** On-demand decade analysis agent (local by default; optional live OpenAI). */
(() => {
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let bootstrapped = false;
  let asking = false;

  function deskHeader() {
    return {'Content-Type': 'application/json', 'X-IROP-Desk': localStorage.getItem('irop-desk') || 'default'};
  }

  async function askApi(message) {
    const mode = $('analysisLive')?.checked ? 'live' : 'local';
    const consent = !!$('analysisConsent')?.checked;
    const body = {message, mode, consent};
    const scenarioId = window.state?.id;
    const path = scenarioId ? `scenarios/${scenarioId}/analysis` : 'analysis/ask';
    const response = await fetch('/api/' + path, {method: 'POST', headers: deskHeader(), body: JSON.stringify(body)});
    const result = await response.json().catch(() => ({detail: 'Request rejected'}));
    if (!response.ok) throw Error(typeof result.detail === 'string' ? result.detail : JSON.stringify(result.detail));
    return result;
  }

  function appendBubble(role, title, text, footer) {
    const log = $('analysisLog');
    if (!log) return;
    const div = document.createElement('div');
    div.className = `agent-bubble ${role}`;
    div.innerHTML = `${title ? `<header>${esc(title)}</header>` : ''}<p>${esc(text)}</p>${footer ? `<footer>${esc(footer)}</footer>` : ''}`;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
  }

  function renderSuggestions(prompts) {
    const box = $('analysisSuggestions');
    if (!box) return;
    box.innerHTML = (prompts || []).map(p => `<button type="button" class="quiet tip" data-tip="${esc(p)}">${esc(p)}</button>`).join('');
    box.querySelectorAll('[data-tip]').forEach(btn => {
      btn.onclick = () => {
        $('analysisInput').value = btn.dataset.tip;
        ask(btn.dataset.tip);
      };
    });
  }

  function paintHighlights(codes) {
    window.analysisHighlights = Array.isArray(codes) ? codes : [];
    // Soft cue on the network map when a scenario is loaded.
    if (window.state && typeof window.render === 'function') {
      // Re-paint network nodes with analysis focus if the host exposes paint hooks later.
    }
    const strip = $('analysisFocus');
    if (strip) {
      strip.textContent = window.analysisHighlights.length
        ? `Focus · ${window.analysisHighlights.join(' · ')}`
        : 'Focus · ask about an airport';
    }
  }

  async function ask(message) {
    if (asking) return;
    const text = (message || $('analysisInput')?.value || '').trim();
    if (!text) return;
    asking = true;
    $('analysisAsk').disabled = true;
    appendBubble('user', '', text);
    $('analysisInput').value = '';
    try {
      const result = await askApi(text);
      if (result.status === 'failed') {
        appendBubble('agent', 'Analysis failed', result.error || 'Unknown failure', result.mode);
      } else {
        appendBubble('agent', result.title || 'Decade analysis', result.reply, `${result.mode} · ${result.topic || 'analysis'}`);
        paintHighlights(result.highlights);
        renderSuggestions(result.suggested);
      }
    } catch (error) {
      appendBubble('agent', 'Request error', error.message, 'local');
    } finally {
      asking = false;
      $('analysisAsk').disabled = false;
      $('analysisInput')?.focus();
    }
  }

  async function bootstrap() {
    if (bootstrapped || !$('analysisPanel')) return;
    bootstrapped = true;
    try {
      const status = await fetch('/api/analysis/status', {headers: deskHeader()}).then(r => r.json());
      $('analysisStatus').textContent = status.available
        ? `Pack ready · ${status.airports.join(', ')} · ${status.years[0]}–${status.years[1]}`
        : 'Decade pack missing on server';
      if (!status.live_available && $('analysisLive')) {
        $('analysisLive').disabled = true;
        $('analysisLiveLabel').textContent = 'Live AI unavailable (set server credentials)';
      }
      const starters = await fetch('/api/analysis/starters', {headers: deskHeader()}).then(r => r.json());
      renderSuggestions(starters.prompts);
      appendBubble('agent', 'Decade analyst', 'Ask about OTP, weather risk, storm days, COVID traffic, or map this scenario’s airports to the four pillars. Local answers use the bundled BTS/FAA/NOAA pack — no LLM required.', 'local · on demand');
    } catch (error) {
      $('analysisStatus').textContent = error.message;
    }
    $('analysisForm').onsubmit = event => {
      event.preventDefault();
      ask();
    };
    $('analysisLive')?.addEventListener('change', () => {
      $('analysisConsentLabel').hidden = !$('analysisLive').checked;
    });
  }

  window.refreshAnalysisAgent = bootstrap;
  document.addEventListener('DOMContentLoaded', bootstrap);
  bootstrap();
})();
