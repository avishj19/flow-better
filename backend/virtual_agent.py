"""Local virtual desk agent grounded in flight network + overnight hubs (no LLM required)."""
from __future__ import annotations
import re
from .simulator import PLANS, network_snapshot, HUB

AIRPORT_RE = re.compile(r'\b(PIT|BOS|JFK|DCA|ORD|DTW)\b', re.I)

def _time(m):
    if m is None: return '—'
    day = 'D+1 ' if m >= 1440 else ''
    return f'{day}{m // 60 % 24:02d}:{m % 60:02d}'

def scenario_context(run):
    s = run['scenario']
    view = run.get('current') or run.get('baseline')
    net = network_snapshot(s, view)
    scores = (view or {}).get('scores')
    last = (run.get('experiments') or [{}])[-1] if run.get('experiments') else {}
    return {
        'phase': run.get('phase'),
        'revision': run.get('revision'),
        'seed': run.get('seed'),
        'name': run.get('name'),
        'network': net,
        'scores': scores,
        'metrics': (view or {}).get('metrics'),
        'disruptions': [{'id': d['id'], 'kind': d['kind'], 'label': d['label'],
                        'airport': d.get('airport'), 'resource': d.get('resource')} for d in s.get('disruptions', [])],
        'signals': s.get('unstructured_signals', []),
        'feasible_plans': last.get('feasible_plans'),
        'options': [{
            'plan': o.get('plan'), 'title': o.get('title'), 'feasible': o.get('feasible'),
            'scores': o.get('scores'), 'pareto_optimal': o.get('pareto_optimal'),
            'best_for': o.get('best_for'),
        } for o in last.get('options', [])] if last else [],
        'available_plans': {k: {'title': v[0], 'description': v[1]} for k, v in PLANS.items()},
        'scope': 'Synthetic simulation briefing only; not operational advice',
    }

def _pack(topic, title, reply, highlights, facts, suggested):
    return {
        'topic': topic, 'title': title, 'reply': reply,
        'highlights': highlights, 'facts': facts, 'suggested': suggested,
    }

def brief_overnight(ctx):
    hubs = ctx['network']['overnight_hubs']
    primary = hubs.get(HUB, {'tails': [], 'count': 0})
    spare = hubs.get('DTW', {'tails': [], 'count': 0})
    d = ctx['network'].get('overnight_disruption')
    lines = [
        f"{HUB} is the primary overnight hub with {primary['count']} planned overnight tails "
        f"({', '.join(primary['tails'])}).",
        f"DTW is the spare overnight base with {spare['count']} tails ({', '.join(spare['tails']) or 'none'}).",
        f"Network health scores {ctx['network']['network_penalty_unit']:,} points per aircraft missing its overnight hub by cutoff.",
    ]
    if d:
        lines.append(f"Active overnight pressure: {d['id']} — {d['label']}.")
    positions = ctx['network'].get('overnight_positions') or []
    oop = [p for p in positions if p.get('out_of_position')]
    if positions:
        if oop:
            lines.append(
                'In the viewed state, out of position: ' +
                '; '.join(f"{p['tail']} at {p['position']} (needs {p['hub']} by {_time(p['deadline'])})" for p in oop) + '.'
            )
        else:
            lines.append('In the viewed state, every aircraft meets its overnight hub by cutoff.')
    highlights = [HUB] + [h for h in hubs if h != HUB]
    return _pack(
        'overnight_hub', 'Overnight hub briefing', ' '.join(lines), highlights,
        {'overnight_hubs': hubs, 'overnight_disruption': d, 'overnight_positions': positions},
        ['Show me the flight network', 'How does Operations protect overnight?', 'Show me DTW', 'What about T01 overnight?'],
    )

def brief_network(ctx):
    n = ctx['network']
    reply = (
        f"Hub-and-spoke day centered on overnight hub {n['hub']} with spokes {', '.join(n['spokes'])}. "
        f"{n['flights']} flights, {n['connection_groups']} connection groups, "
        f"{n['gates'][HUB]} gates at {HUB} and 2 per spoke. "
        'Recovery choices trade financial cost, passenger impact, overnight network health, and crew buffer — never one blended score.'
    )
    return _pack(
        'network', 'Flight network', reply, [n['hub'], *n['spokes']],
        {'airports': n['airports'], 'gates': n['gates'], 'route_pairs': n['route_pairs'], 'overnight_hubs': n['overnight_hubs']},
        ['Brief the overnight hubs', 'Show me ORD', 'What disruptions hit the network?', 'Compare recovery strategies'],
    )

def brief_airport(ctx, code):
    code = code.upper()
    n = ctx['network']
    if code not in n['airports']:
        return _pack('airport', f'Unknown airport {code}',
                     f'{code} is outside this sandbox. Available: {", ".join(n["airports"])}.',
                     [HUB], {}, ['Show me the flight network', 'Brief the overnight hubs'])
    flow = n['airport_flow'][code]
    hub_info = n['overnight_hubs'].get(code)
    role = 'primary overnight hub' if code == HUB else ('spare overnight base' if hub_info else 'spoke')
    reply = (
        f"{code} is a {role}. Gates: {n['gates'][code]}. "
        f"Scheduled departures {flow['departures']}, arrivals {flow['arrivals']}."
    )
    if hub_info:
        reply += f" Planned overnight tails: {', '.join(hub_info['tails'])}."
        if hub_info['deadlines']:
            sample = ', '.join(f"{t} by {_time(dl)}" for t, dl in sorted(hub_info['deadlines'].items())[:4])
            reply += f" Cutoffs include {sample}."
    if flow['delayed_departures'] or flow['cancelled']:
        reply += f" Viewed state: {flow['delayed_departures']} delayed departures, {flow['cancelled']} cancellations from {code}."
    if flow['disrupted']:
        hits = [d for d in ctx['disruptions'] if d.get('airport') == code]
        if hits:
            reply += ' Disruption: ' + '; '.join(d['label'] for d in hits) + '.'
    return _pack(
        'airport', f'{code} station view', reply, [code] + ([HUB] if code != HUB else []),
        {'airport': code, 'flow': flow, 'overnight': hub_info},
        ['Brief the overnight hubs', 'Show me the flight network', 'Compare recovery strategies'],
    )

def brief_tail_overnight(ctx, tail='T01'):
    hubs = ctx['network']['overnight_hubs']
    home = next((h for h, info in hubs.items() if tail in info['tails']), None)
    deadline = hubs.get(home, {}).get('deadlines', {}).get(tail) if home else None
    d = ctx['network'].get('overnight_disruption')
    pos = next((p for p in (ctx['network'].get('overnight_positions') or []) if p['tail'] == tail), None)
    reply = f"{tail} planned overnight hub is {home or 'unknown'}"
    if deadline is not None:
        reply += f" by {_time(deadline)}"
    reply += '.'
    if d and d.get('resource') == tail:
        reply += f" Disruption {d['id']} tightens that overnight commitment: {d['label']}."
    if pos:
        reply += (
            f" Viewed position at cutoff: {pos['position']}"
            f"{' · OUT OF POSITION' if pos['out_of_position'] else ' · on hub'}"
            f" ({pos['penalty']:,} network points)."
        )
    highlights = [home or HUB]
    if pos and isinstance(pos.get('position'), str) and len(pos['position']) == 3:
        highlights.append(pos['position'])
    return _pack(
        'overnight_tail', f'{tail} overnight', reply, highlights,
        {'tail': tail, 'hub': home, 'deadline': deadline, 'position': pos, 'disruption': d},
        ['How does Operations protect overnight?', 'Show me the Loyalty ferry path', 'Brief the overnight hubs'],
    )

def brief_disruptions(ctx):
    bits = [f"{d['id']} ({d['kind']}): {d['label']}" for d in ctx['disruptions']]
    reply = f"{len(ctx['disruptions'])} disruption templates. " + ' · '.join(bits)
    if ctx['signals']:
        reply += ' Unstructured ORD ground-ops text is preserved and parsed into +45m turnaround inside its window.'
    if ctx['phase'] == 'baseline':
        reply += ' Inject them to see overnight and crew pressure appear in the four pillars.'
    elif ctx['scores']:
        sc = ctx['scores']
        reply += (
            f" Viewed pillars — financial ${sc['financial_cost']:,}, passenger {sc['passenger_impact']:,}, "
            f"network {sc['network_health']:,}, crew buffer {sc['crew_buffer']['minutes_remaining']}m."
        )
    highlights = [HUB]
    for d in ctx['disruptions']:
        if d.get('airport') and d['airport'] not in highlights:
            highlights.append(d['airport'])
    return _pack(
        'disruptions', 'Disruption pressure', reply, highlights,
        {'disruptions': ctx['disruptions'], 'scores': ctx['scores']},
        ['Brief the overnight hubs', 'Show me ORD', 'Compare recovery strategies'],
    )

def brief_recovery(ctx):
    plans = ', '.join(f"{k} — {v['title']}" for k, v in ctx['available_plans'].items())
    reply = (
        f"Three bounded strategies: {plans}. "
        'CFO waits (cheap, but can fail crew/overnight). Loyalty ferries the DTW spare to protect passengers. '
        'Operations cancels the final ORD round-trip so T01 nights at PIT. '
        'There is no single weighted winner — choose among feasible Pareto trade-offs.'
    )
    if ctx['options']:
        bits = []
        for o in ctx['options']:
            tag = 'feasible' if o['feasible'] else 'blocked'
            best = f", best for {', '.join(o['best_for'] or [])}" if o.get('best_for') else ''
            bits.append(f"{o['title']} ({tag}{best})")
        reply += ' Latest experiment: ' + '; '.join(bits) + '.'
    elif ctx['phase'] == 'disrupted':
        reply += ' Run Compare three recovery strategies to calculate the pillars.'
    elif ctx['phase'] == 'baseline':
        reply += ' Inject disruptions before comparing strategies.'
    return _pack(
        'recovery', 'Recovery strategies', reply, [HUB, 'DTW', 'ORD'],
        {'plans': ctx['available_plans'], 'options': ctx['options'], 'feasible_plans': ctx['feasible_plans']},
        ['How does Operations protect overnight?', 'Show me the Loyalty ferry path', 'Brief the overnight hubs'],
    )

def brief_operations(ctx):
    reply = (
        'The Operations Choice cancels RX104/RX105 (final ORD round trip) so T01 stays at its PIT overnight hub by the tightened cutoff. '
        'Network health drops to zero penalty when that works, but cancelled passengers take an assumed 1,440-minute delay — '
        'so passenger impact spikes while tomorrow’s first rotation is protected.'
    )
    return _pack(
        'strategy_operations', 'Operations & overnight', reply, [HUB, 'ORD'],
        {'plan': 'operations'},
        ['Brief the overnight hubs', 'What about T01 overnight?', 'Compare recovery strategies'],
    )

def brief_loyalty(ctx):
    reply = (
        'The Loyalty Choice ferries spare R01 DTW→PIT with reserve crew RC01, covers the late T01 work, then ferries home PIT→DTW. '
        'Passenger impact usually improves; financial cost buys two ferries and a reserve crew. '
        'Check whether overnight hubs and crew buffer still clear after the ferry path.'
    )
    return _pack(
        'strategy_loyalty', 'Loyalty ferry path', reply, ['DTW', HUB],
        {'plan': 'loyalty', 'ferries': [('FERRY-1', 'DTW', 'PIT'), ('FERRY-2', 'PIT', 'DTW')]},
        ['Brief the overnight hubs', 'Compare recovery strategies', 'Show me DTW'],
    )

def brief_status(ctx):
    hub_bits = ', '.join(f"{h} ({info['count']})" for h, info in ctx['network']['overnight_hubs'].items())
    reply = (
        f"Scenario “{ctx['name']}” · phase {ctx['phase']} · revision {ctx['revision']} · seed {ctx['seed']}. "
        f"Overnight hubs: {hub_bits}. "
        'Ask about the network map, overnight cutoffs, ORD pressure, T01, or the three recovery strategies.'
    )
    if ctx['scores']:
        sc = ctx['scores']
        reply += (
            f" Viewed pillars — ${sc['financial_cost']:,} / pax {sc['passenger_impact']:,} / "
            f"network {sc['network_health']:,} / crew {sc['crew_buffer']['minutes_remaining']}m."
        )
    return _pack(
        'status', 'Desk status', reply, [HUB, 'DTW', 'ORD'],
        {'phase': ctx['phase'], 'revision': ctx['revision'], 'scores': ctx['scores']},
        ['Brief the overnight hubs', 'Show me the flight network', 'Compare recovery strategies'],
    )

INTENTS = (
    (('operations', 'cancel', 'ord round'), brief_operations),
    (('loyalty', 'ferry', 'spare', 'dtw→', 'dtw to'), brief_loyalty),
    (('overnight', 'parking', 'cutoff', 'tomorrow', 'network health', 'network penalty'), brief_overnight),
    (('network', 'spoke', 'route', 'map', 'schematic'), brief_network),
    (('disrupt', 'weather', 'mechanical', 'ground', 'slack', 'stress', 'signal'), brief_disruptions),
    (('recover', 'strateg', 'cfo', 'pillar', 'option', 'pareto', 'trade'), brief_recovery),
    (('status', 'hello', 'hi', 'help', 'brief', 'overview', 'summary'), brief_status),
)

def respond(run, message: str):
    ctx = scenario_context(run)
    text = (message or '').strip()
    lowered = text.lower()
    # Tail overnight questions
    if re.search(r'\bT0?1\b', text, re.I) and re.search(r'overnight|hub|cutoff|position', lowered):
        result = brief_tail_overnight(ctx, 'T01')
    elif re.search(r'\bT\d{2}\b', text) and 'overnight' in lowered:
        tail = re.search(r'\bT\d{2}\b', text).group(0)
        result = brief_tail_overnight(ctx, tail)
    else:
        airports = [m.upper() for m in AIRPORT_RE.findall(text)]
        handler = brief_status
        for keys, fn in INTENTS:
            if any(k in lowered for k in keys):
                handler = fn
                break
        if handler is brief_status and airports and not re.search(r'\b(network|overnight|plan|strateg|recover)\b', lowered):
            result = brief_airport(ctx, airports[0])
        else:
            result = handler(ctx)
            if airports:
                merged = []
                for code in airports + result['highlights']:
                    if code not in merged:
                        merged.append(code)
                result['highlights'] = merged
    result.update({
        'agent': 'FlowBetter desk agent',
        'mode': 'local_virtual',
        'phase': ctx['phase'],
        'revision': ctx['revision'],
        'scope': ctx['scope'],
        'user_message': text,
    })
    return result

def starter_prompts():
    return [
        'Brief the overnight hubs',
        'Show me the flight network',
        'What about T01 overnight?',
        'How does Operations protect overnight?',
        'Show me the Loyalty ferry path',
        'What disruptions hit the network?',
        'Compare recovery strategies',
        'Show me ORD',
    ]
