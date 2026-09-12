"""FlowBetter ground-ops desk (model v3).

Simple on-ground recovery sandbox backed by the decade stress pack:
- PIT hub ground picture (aircraft, crews, gates, banks)
- user picks 1–4 catalog issues
- 3–5 recovery options with money / people / regulation tradeoffs

Synthetic teaching scenarios only — no live airborne tracking.
"""
from copy import deepcopy
import random
from .issues import MAX_ISSUES, catalog, resolve

MODEL_VERSION = 3
AIRPORTS = ('PIT', 'BOS', 'JFK', 'DCA', 'ORD', 'DTW')
FAA_NOTE = 'Simplified Part 117-inspired duty checks; not an FAA legality determination.'
FAA_SOURCE = 'https://www.faa.gov/about/office_org/headquarters_offices/agc/practice_areas/regulations/part117'


def generate(seed=42, issue_ids=None):
    rng = random.Random(seed)
    aircraft = []
    for i in range(1, 9):
        dest = AIRPORTS[1:][(i - 1) % 5]
        aircraft.append({
            'tail': f'T{i:02}',
            'type': 'RJ',
            'gate': f'A{(i % 6) + 1}',
            'airport': 'PIT',
            'status': 'at_gate',
            'ready_minute': 1080 + i * 3,
            'next_flight': f'FB4{100 + i}',
            'next_dest': dest,
            'pax_booked': rng.randint(78, 128),
            'crew': f'C{i:02}',
            'overnight_hub': 'PIT',
            'overnight_by': 1420,
        })
    aircraft.append({
        'tail': 'R01', 'type': 'RJ', 'gate': 'Remote', 'airport': 'DTW', 'status': 'spare_remote',
        'ready_minute': 1100, 'next_flight': None, 'next_dest': None, 'pax_booked': 0,
        'crew': 'RC01', 'overnight_hub': 'DTW', 'overnight_by': 1400,
    })
    crews = [{
        'id': f'C{i:02}', 'report': 1050 + i * 2, 'max_duty': 690,
        'remaining_buffer': 95 - i * 5, 'status': 'on_duty', 'qualified': 'RJ', 'location': 'PIT',
    } for i in range(1, 9)]
    crews.append({
        'id': 'RC01', 'report': 1100, 'max_duty': 690, 'remaining_buffer': 180,
        'status': 'reserve', 'qualified': 'RJ', 'location': 'DTW',
    })
    ground = {
        'as_of': 'Synthetic evening · PIT hub ground desk',
        'clock_minute': 1100,
        'hub': 'PIT',
        'gates_open': 6,
        'deice_pads': 2,
        'aircraft': aircraft,
        'crews': crews,
        'banks': [
            {'id': 'BANK-EVE', 'label': 'Evening departure bank', 'push_window': '18:00–19:10',
             'flights': [a['next_flight'] for a in aircraft if a['next_flight']]},
            {'id': 'BANK-LATE', 'label': 'Last bank / overnight protect', 'push_window': '20:40–22:00',
             'flights': ['FB4104', 'FB4105', 'FB4108']},
        ],
        'passengers_in_terminal': sum(a['pax_booked'] for a in aircraft if a['airport'] == 'PIT'),
        'notes': [
            'On-ground focus only: gates, turns, crews, overnight metal, bank integrity.',
            'Teaching magnitudes inspired by 2016–2025 BTS/NOAA stress findings — not live ops.',
        ],
    }
    scenario = {
        'model_version': MODEL_VERSION,
        'seed': seed,
        'issue_ids': [],
        'issues': [],
        'ground': ground,
        'situation': None,
        'options': [],
        'max_issues': MAX_ISSUES,
        'scope': 'Synthetic ground-ops desk · decade-backed teaching issues · no live airborne tracking',
        'faa_source': FAA_SOURCE,
    }
    if issue_ids:
        return apply_issues(scenario, issue_ids)
    return scenario


def apply_issues(scenario, issue_ids):
    issues = resolve(issue_ids)
    s = deepcopy(scenario)
    s['issue_ids'] = [i['id'] for i in issues]
    s['issues'] = [{k: i[k] for k in ('id', 'category', 'title', 'blurb', 'decade_basis', 'severity')} for i in issues]
    effects = _merge_effects(issues)
    situation = _build_situation(s['ground'], effects, issues)
    options = _build_options(s['ground'], situation, effects, issues)
    s['situation'] = situation
    s['options'] = options
    return s


def _merge_effects(issues):
    out = {
        'hold_airports': {}, 'turn_penalty_airports': {}, 'tail_ready_delay': {},
        'crew_ready_delay': {}, 'crew_duty_cut': {}, 'overnight_tighten': {},
        'gate_cap_cut': {}, 'gate_blocked': {}, 'deice_queue': 0, 'taxi_out_penalty': 0,
        'pushback_delay': 0, 'gate_queue_penalty': 0, 'inbound_slip': 0,
        'late_aircraft_pressure': 0, 'force_cancel_pressure': 0, 'connection_risk_pax': 0,
        'reserve_needed': False, 'focus_flights': [], 'severity': 0,
    }
    for issue in issues:
        e = issue['effects']
        out['severity'] += issue['severity']
        for k, v in e.get('hold_airports', {}).items():
            out['hold_airports'][k] = max(out['hold_airports'].get(k, 0), v)
        for k, v in e.get('turn_penalty_airports', {}).items():
            out['turn_penalty_airports'][k] = out['turn_penalty_airports'].get(k, 0) + v
        for k, v in e.get('tail_ready_delay', {}).items():
            out['tail_ready_delay'][k] = out['tail_ready_delay'].get(k, 0) + v
        for k, v in e.get('crew_ready_delay', {}).items():
            out['crew_ready_delay'][k] = out['crew_ready_delay'].get(k, 0) + v
        for k, v in e.get('crew_duty_cut', {}).items():
            out['crew_duty_cut'][k] = out['crew_duty_cut'].get(k, 0) + v
        for k, v in e.get('overnight_tighten', {}).items():
            out['overnight_tighten'][k] = out['overnight_tighten'].get(k, 0) + v
        for k, v in e.get('gate_cap_cut', {}).items():
            out['gate_cap_cut'][k] = out['gate_cap_cut'].get(k, 0) + v
        for k, v in e.get('gate_blocked', {}).items():
            out['gate_blocked'][k] = out['gate_blocked'].get(k, 0) + v
        for key in ('deice_queue', 'taxi_out_penalty', 'pushback_delay', 'gate_queue_penalty',
                    'inbound_slip', 'late_aircraft_pressure', 'force_cancel_pressure', 'connection_risk_pax'):
            out[key] += e.get(key, 0)
        out['reserve_needed'] = out['reserve_needed'] or bool(e.get('reserve_needed'))
        out['focus_flights'].extend(e.get('focus_flights', []))
    out['focus_flights'] = sorted(set(out['focus_flights']))
    return out


def _build_situation(ground, effects, issues):
    aircraft = deepcopy(ground['aircraft'])
    crews = {c['id']: deepcopy(c) for c in ground['crews']}
    alerts, blocked = [], []
    for a in aircraft:
        if a['tail'] in effects['tail_ready_delay']:
            delay = effects['tail_ready_delay'][a['tail']]
            a['ready_minute'] += delay
            a['status'] = 'maintenance_hold'
            a['delay_minutes'] = delay
            alerts.append(f"{a['tail']} ground release slipped +{delay}m · next {a['next_flight'] or 'n/a'}")
        if a['airport'] in effects['hold_airports']:
            hold = effects['hold_airports'][a['airport']]
            a['weather_hold_minutes'] = hold
            if a['status'] == 'at_gate':
                a['status'] = 'weather_gated'
            alerts.append(f"{a['airport']} movement hold ~{hold}m affecting {a['tail']}")
        if a['next_dest'] in effects['hold_airports']:
            a['destination_hold_minutes'] = effects['hold_airports'][a['next_dest']]
            a['status'] = 'destination_restricted'
            if a['next_flight']:
                blocked.append(a['next_flight'])
        slip = effects['inbound_slip'] + effects['late_aircraft_pressure'] // 2
        if slip and a['airport'] == 'PIT' and a['next_flight']:
            a['expected_push_slip'] = (
                slip + effects['taxi_out_penalty'] + effects['pushback_delay'] + effects['gate_queue_penalty']
            )
            if a['next_dest'] in effects['turn_penalty_airports']:
                a['expected_push_slip'] += effects['turn_penalty_airports'][a['next_dest']]
        if a['tail'] in effects['overnight_tighten']:
            a['overnight_by'] -= effects['overnight_tighten'][a['tail']]
            alerts.append(f"{a['tail']} overnight PIT deadline tightened to minute {a['overnight_by']}")
    for cid, cut in effects['crew_duty_cut'].items():
        if cid in crews:
            crews[cid]['remaining_buffer'] -= cut
            if crews[cid]['remaining_buffer'] < 30:
                crews[cid]['status'] = 'duty_critical'
            alerts.append(f"Crew {cid} buffer now {crews[cid]['remaining_buffer']}m · {FAA_NOTE}")
    for cid, delay in effects['crew_ready_delay'].items():
        if cid in crews:
            crews[cid]['report'] += delay
            crews[cid]['status'] = 'late_report'
            alerts.append(f"Crew {cid} report slipped +{delay}m")
    gates = ground['gates_open'] - effects['gate_cap_cut'].get('PIT', 0) - effects['gate_blocked'].get('PIT', 0)
    severity = effects['severity']
    cats = sorted({i['category'] for i in issues})
    holds = ', '.join(f'{a} {m}m' for a, m in effects['hold_airports'].items()) or 'none'
    return {
        'headline': f"{len(issues)} ground issues ({', '.join(cats)}) · airfield holds: {holds}",
        'severity': severity,
        'severity_label': 'critical' if severity >= 12 else 'elevated' if severity >= 7 else 'manageable',
        'alerts': alerts[:12],
        'aircraft': aircraft,
        'crews': list(crews.values()),
        'gates_available': max(1, gates),
        'deice_queue_minutes': effects['deice_queue'],
        'passengers_exposed': sum(
            a['pax_booked'] for a in aircraft if a['airport'] == 'PIT' and a['status'] != 'spare_remote'
        ),
        'connection_risk_pax': effects['connection_risk_pax'],
        'blocked_departures': sorted(set(blocked)),
        'holds': effects['hold_airports'],
        'decade_links': [i['decade_basis'] for i in issues],
        'regulation_watch': [
            FAA_NOTE,
            'Cancellations assume hotel/voucher passenger care cost only — not a real rebooking engine.',
            'Overnight position misses are next-day network damage in this model, not an FAR citation.',
        ],
    }


def _build_options(ground, situation, effects, issues):
    pax = situation['passengers_exposed']
    conn = situation['connection_risk_pax']
    storm = max(effects['hold_airports'].values()) if effects['hold_airports'] else 0
    mx = sum(effects['tail_ready_delay'].values())
    duty_pressure = effects['reserve_needed'] or any(c['remaining_buffer'] < 30 for c in situation['crews'])
    late_bank = ['FB4104', 'FB4105', 'FB4108']
    evening = [a['next_flight'] for a in ground['aircraft'] if a.get('next_flight')]
    issue_ids = {i['id'] for i in issues}
    options = []

    absorb_delay = storm + mx + effects['inbound_slip'] + effects['taxi_out_penalty'] + effects['pushback_delay']
    absorb_legal = not (storm >= 180 or (duty_pressure and absorb_delay > 50))
    options.append(_option(
        'absorb', 'Hold the bank — absorb the delay',
        'Keep original metal and crews. Push when releases and holds clear.',
        absorb_legal, round(absorb_delay * 120 + pax * max(absorb_delay, 15) * 0.35, -1),
        pax * max(absorb_delay, 20), conn if absorb_delay > 40 else conn // 3,
        evening, [],
        {'passengers_affected': pax, 'crews_on_duty': 8, 'ramp_agents_extra': 0, 'hotel_rooms': 0},
        {'delay_ops': round(absorb_delay * 120, -1), 'cancellations': 0, 'ferry': 0, 'hotels_vouchers': 0, 'reserve_crew': 0},
        ['Likely crew-illegal if multi-hour weather or thin duty buffers persist.', FAA_NOTE] if not absorb_legal else [FAA_NOTE, 'Works only when disruption is short and local.'],
        [f'Lowest immediate cash if the slip stays near {absorb_delay}m.',
         'Highest risk of cascading late aircraft into the overnight.',
         'Decade lesson: absorb fails on Snowzilla-scale multi-airport days.'],
        None if absorb_legal else 'Crew duty / multi-hour weather make waiting through the event illegal in this model.',
    ))

    cancel_flights = late_bank[:]
    cancel_pax = sum(a['pax_booked'] for a in ground['aircraft'] if a.get('next_flight') in cancel_flights) or 220
    options.append(_option(
        'cancel_last_bank', 'Cancel the last bank — protect overnight metal',
        'Scrap FB4104/05/08, rebook passengers, keep T01–T08 at PIT for tomorrow’s first wave.',
        True, round(len(cancel_flights) * 15000 + cancel_pax * 40, -1),
        cancel_pax * 1440, conn,
        [f for f in evening if f not in cancel_flights], cancel_flights,
        {'passengers_affected': cancel_pax, 'crews_on_duty': 6, 'ramp_agents_extra': 4, 'hotel_rooms': max(40, cancel_pax // 3)},
        {'delay_ops': 4000, 'cancellations': len(cancel_flights) * 15000, 'ferry': 0, 'hotels_vouchers': cancel_pax * 40, 'reserve_crew': 0},
        ['Passenger care modeled as hotel+voucher cost only.', 'Best match to decade cancel-first winters.'],
        ['Feasible even under Northeast cascade or ORD de-ice meltdown.',
         'Brutal passenger score (modeled 24h delay on cancelled seats).',
         'Network health stays green — tomorrow’s bank has metal.'],
    ))

    swap_ok = not (storm >= 200 and 'wx_ne_cascade' in issue_ids) and storm < 220
    options.append(_option(
        'swap_reserve', 'Swap in hub reserve crew — keep the metal',
        'Replace thin-duty crew with a PIT-ready reserve pattern and push a thinned bank.',
        swap_ok, round(11000 + mx * 40 + pax * 12, -1),
        pax * max(35, mx // 2 or 35), max(0, conn // 2 - 10),
        evening[:6], late_bank[1:] if storm >= 120 else [],
        {'passengers_affected': pax, 'crews_on_duty': 8, 'ramp_agents_extra': 2, 'hotel_rooms': 10 if storm else 0},
        {'delay_ops': 6000, 'cancellations': 15000 if storm >= 120 else 0, 'ferry': 0, 'hotels_vouchers': 800, 'reserve_crew': 3000},
        [FAA_NOTE, 'Reserve must be in position; remote reserves need a ferry.'],
        ['Fixes human/crew-timeout issues cleanly.',
         'Does not melt a three-airport winter shutdown by itself.',
         'Good middle path for mechanical + duty without full cancel.'],
        None if swap_ok else 'Destination holds are too deep for a crew swap to create a legal path.',
    ))

    ferry_ok = storm < 180 and any(a['tail'] == 'R01' for a in ground['aircraft'])
    options.append(_option(
        'ferry_spare', 'Ferry spare R01 PIT←DTW — protect the product',
        'Position spare metal and reserve crew, operate the evening product, ferry home later.',
        ferry_ok, round(23000 + pax * 8, -1),
        pax * 25, max(0, conn // 4),
        evening, [],
        {'passengers_affected': pax, 'crews_on_duty': 9, 'ramp_agents_extra': 3, 'hotel_rooms': 0},
        {'delay_ops': 3500, 'cancellations': 0, 'ferry': 20000, 'hotels_vouchers': 0, 'reserve_crew': 3000},
        [FAA_NOTE, 'Ferry burns cash and still needs open origin/destination windows.'],
        ['Best passenger continuity when the airfield is still workable.',
         'Cash-heavy; fails when JFK/DCA/BOS are all shut.',
         'Decade lesson: ferry/loyalty loses to cancel-first on cascade winters.'],
        None if ferry_ok else 'Spare ferry cannot outrun multi-hour destination holds on the Northeast cascade.',
    ))

    if conn >= 20 or effects['late_aircraft_pressure'] or storm:
        prot_cancel = ['FB4108']
        options.append(_option(
            'protect_connections', 'Hold connections — cancel one thin turn',
            'Pad PIT banks for misconnects, cancel one low-load late turn, keep high-value flows.',
            storm < 240, 20000 + conn * 25,
            95 * 1440 + max(0, pax - 95) * 40, 0,
            [f for f in evening if f not in prot_cancel], prot_cancel,
            {'passengers_affected': pax, 'crews_on_duty': 7, 'ramp_agents_extra': 5, 'hotel_rooms': 25},
            {'delay_ops': 5000, 'cancellations': 15000, 'ferry': 0, 'hotels_vouchers': conn * 25, 'reserve_crew': 0},
            ['Connection hold is a passenger-service choice, not an ATC program.', FAA_NOTE],
            ['Minimizes missed connections in the model.',
             'Still may be unwise if weather holds exceed ~4 hours everywhere.',
             'Useful when misconnect_wave is selected with milder weather.'],
            None if storm < 240 else 'Cascade weather is too deep for connection holding to remain operationally honest.',
        ))

    feasible = [o for o in options if o['feasible']]
    blocked = [o for o in options if not o['feasible']]
    feasible.sort(key=lambda o: (o['cost'], o['passenger_delay_minutes']))
    best_pax = min((o['passenger_delay_minutes'] for o in feasible), default=None)
    for i, o in enumerate(feasible):
        o['rank'] = i + 1
        o['badge'] = 'lowest cash' if i == 0 else ('best passengers' if o['passenger_delay_minutes'] == best_pax else 'feasible')
    for o in blocked:
        o['rank'] = None
        o['badge'] = 'blocked'
    return (feasible + blocked)[:5]


def _option(oid, title, summary, feasible, cost, pax_delay, missed, held, cancelled, people, money, regulation, tradeoffs, why_blocked=None):
    return {
        'id': oid,
        'title': title,
        'summary': summary,
        'feasible': bool(feasible),
        'cost': int(cost),
        'passenger_delay_minutes': int(pax_delay),
        'missed_connecting_passengers': int(missed),
        'flights_held': held,
        'flights_cancelled': cancelled,
        'people': people,
        'money_breakdown': money,
        'regulation': regulation,
        'tradeoffs': tradeoffs,
        'why_blocked': why_blocked,
    }


def option_by_id(scenario, option_id):
    return next((o for o in scenario.get('options', []) if o['id'] == option_id), None)


def evaluate(seed=42, issue_ids=None):
    return generate(seed, issue_ids)
