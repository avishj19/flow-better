"""Selectable ground-ops issue catalog.

Synthetic teaching issues sized from BTS/NOAA decade stress findings for
PIT, BOS, JFK, DCA, ORD, DTW — not live airline events or official closures.
"""

CATEGORIES = {
    'weather': 'Weather & airfield',
    'mechanical': 'Aircraft / equipment',
    'human': 'Crew & human factors',
    'airport': 'Airport / ramp operations',
    'network': 'Network & passenger flow',
}

# Users pick up to MAX_ISSUES from this catalog.
MAX_ISSUES = 4

ISSUES = {
    'wx_pit_snow': {
        'id': 'wx_pit_snow',
        'category': 'weather',
        'title': 'PIT snow / ice hold',
        'blurb': 'Pittsburgh ramp slowing under snow; de-ice and pushback queues build.',
        'decade_basis': 'PIT winters regularly produce snow days; BTS delay shares spike on weather + late aircraft in Jan samples.',
        'severity': 3,
        'effects': {'hold_airports': {'PIT': 90}, 'deice_queue': 25, 'taxi_out_penalty': 20},
    },
    'wx_ne_cascade': {
        'id': 'wx_ne_cascade',
        'category': 'weather',
        'title': 'Northeast winter cascade',
        'blurb': 'JFK, DCA, and BOS all under winter movement limits — classic multi-airport shutdown pattern.',
        'decade_basis': 'BTS PREZIP flaw days: 2016-01-23/24 and 2022-01-29 showed 67–100% cancel rates at JFK/DCA/BOS.',
        'severity': 5,
        'effects': {'hold_airports': {'JFK': 240, 'DCA': 240, 'BOS': 220}, 'force_cancel_pressure': 80},
    },
    'wx_ord_deice': {
        'id': 'wx_ord_deice',
        'category': 'weather',
        'title': 'ORD de-icing backlog',
        'blurb': 'O’Hare de-ice pads backed up; every ORD turn eats extra ground time.',
        'decade_basis': 'ORD 2019-01-28/30 and 2024-01-12: high cancel + huge weather and late-aircraft delay minutes.',
        'severity': 4,
        'effects': {'hold_airports': {'ORD': 180}, 'turn_penalty_airports': {'ORD': 45}, 'late_aircraft_pressure': 40},
    },
    'wx_jfk_fog': {
        'id': 'wx_jfk_fog',
        'category': 'weather',
        'title': 'JFK low visibility',
        'blurb': 'Fog/low ceiling at JFK cuts arrival rates; PIT outbound metal waits for return legs.',
        'decade_basis': 'JFK leads several years in heavy-fog (WT02) proxies in NOAA GHCND; OTP among weakest in the six-airport set.',
        'severity': 3,
        'effects': {'hold_airports': {'JFK': 120}, 'inbound_slip': 35},
    },
    'mx_tail_late': {
        'id': 'mx_tail_late',
        'category': 'mechanical',
        'title': 'Maintenance release late',
        'blurb': 'Tail T01 still in the hangar — release slipped past the bank push.',
        'decade_basis': 'Carrier/maintenance delay is a standing BTS cause share; ground release slips drive first-wave departure fails.',
        'severity': 3,
        'effects': {'tail_ready_delay': {'T01': 105}, 'focus_flights': ['FB4104']},
    },
    'mx_apu_gate': {
        'id': 'mx_apu_gate',
        'category': 'mechanical',
        'title': 'APU failed at gate',
        'blurb': 'T03 APU dead on stand — needs ground power / swap before boarding finishes.',
        'decade_basis': 'Gate-bound mechanicals show up as departure delays before any airborne minute accrues.',
        'severity': 2,
        'effects': {'tail_ready_delay': {'T03': 60}, 'gate_blocked': {'PIT': 1}},
    },
    'mx_tow_outage': {
        'id': 'mx_tow_outage',
        'category': 'mechanical',
        'title': 'Pushback tractor outage',
        'blurb': 'One PIT pushback unit down; narrow-body pushes serialize on the remaining tractor.',
        'decade_basis': 'Ground equipment limits create taxi-out and gate-occupancy pressure without weather.',
        'severity': 2,
        'effects': {'pushback_delay': 25, 'gate_queue_penalty': 15},
    },
    'crew_timeout': {
        'id': 'crew_timeout',
        'category': 'human',
        'title': 'Crew duty almost cooked',
        'blurb': 'Crew C01 is inside a thin buffer — another slip risks an illegal duty day.',
        'decade_basis': 'Decade stress tests showed absorb-delay plans going crew-illegal on multi-hour disruption days.',
        'severity': 4,
        'effects': {'crew_duty_cut': {'C01': 40}, 'reserve_needed': True},
    },
    'crew_no_show': {
        'id': 'crew_no_show',
        'category': 'human',
        'title': 'Reserve crew late to report',
        'blurb': 'Standby crew RC01 reported late; coverage for swaps is soft for 45 minutes.',
        'decade_basis': 'Human-induced coverage gaps compound mechanical swaps — reserve timing matters on ground.',
        'severity': 2,
        'effects': {'crew_ready_delay': {'RC01': 45}},
    },
    'gate_conflict': {
        'id': 'gate_conflict',
        'category': 'airport',
        'title': 'PIT gate conflict',
        'blurb': 'Two banks want the same preferential gates; ramp control is metering pushes.',
        'decade_basis': 'Hub gate pressure shows up in taxi-out and departure delay even when airborne weather is fine.',
        'severity': 2,
        'effects': {'gate_cap_cut': {'PIT': 1}, 'gate_queue_penalty': 20},
    },
    'ramp_short': {
        'id': 'ramp_short',
        'category': 'airport',
        'title': 'Ramp staffing short',
        'blurb': 'Bag agents stretched — bag loading and single-engine starts running long.',
        'decade_basis': 'Airport staffing shocks lengthen turns; similar to ORD ground-ops text delays in teaching scenarios.',
        'severity': 2,
        'effects': {'turn_penalty_airports': {'PIT': 20}, 'taxi_out_penalty': 10},
    },
    'misconnect_wave': {
        'id': 'misconnect_wave',
        'category': 'network',
        'title': 'Misconnect wave at PIT',
        'blurb': 'Late inbounds threaten a bank of protected connections through the hub.',
        'decade_basis': 'Late-aircraft is often the largest BTS delay-cause share; connections are the passenger face of that cascade.',
        'severity': 3,
        'effects': {'connection_risk_pax': 86, 'inbound_slip': 25, 'late_aircraft_pressure': 30},
    },
    'overnight_squeeze': {
        'id': 'overnight_squeeze',
        'category': 'network',
        'title': 'Overnight parking squeeze',
        'blurb': 'T01’s overnight PIT slot moved earlier — tomorrow’s first turn is unprotected if metal is late.',
        'decade_basis': 'Network-health pillar: aircraft out of overnight position wrecks next-day banks (decade training lesson).',
        'severity': 4,
        'effects': {'overnight_tighten': {'T01': 40}, 'focus_flights': ['FB4104', 'FB4105']},
    },
}


def catalog():
    return {
        'max_select': MAX_ISSUES,
        'categories': CATEGORIES,
        'issues': [
            {
                'id': i['id'],
                'category': i['category'],
                'category_label': CATEGORIES[i['category']],
                'title': i['title'],
                'blurb': i['blurb'],
                'decade_basis': i['decade_basis'],
                'severity': i['severity'],
            }
            for i in ISSUES.values()
        ],
    }


def resolve(issue_ids):
    if not issue_ids:
        raise ValueError('Select at least one ground issue')
    if len(issue_ids) > MAX_ISSUES:
        raise ValueError(f'Select at most {MAX_ISSUES} issues')
    if len(set(issue_ids)) != len(issue_ids):
        raise ValueError('Duplicate issues are not allowed')
    missing = [i for i in issue_ids if i not in ISSUES]
    if missing:
        raise ValueError(f'Unknown issue id(s): {", ".join(missing)}')
    return [ISSUES[i] for i in issue_ids]
