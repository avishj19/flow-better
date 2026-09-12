"""Selectable disruption catalog for the recovery desk (max 4 of 10 issues).

Each issue builds a disruption dict compatible with simulator.s['disruptions'].
Ground-ops issues also ensure a matching unstructured signal exists.
"""

MAX_ISSUES = 4

# Preset pack(s) the desk can pick; each list is ≤ MAX_ISSUES catalog ids.
ISSUE_PROFILES = {
    'mechanical': {
        'id': 'mechanical',
        'label': 'Mechanical',
        'description': 'Aircraft mechanical holds — maintenance slips on T01/T05 plus a grounded DTW spare.',
        'issue_ids': ['mech_t01', 'mech_t05', 'spare_unavailable'],
    },
}


def _mech_t01(_s):
    return {
        'id': 'D-MECH-T01',
        'kind': 'mechanical',
        'resource': 'T01',
        'flight_id': 'RX104',
        'until': 1245,
        'label': 'Maintenance delay · T01 released at 20:45, 105m after RX104’s planned departure',
    }


def _mech_t05(_s):
    return {
        'id': 'D-MECH-T05',
        'kind': 'mechanical',
        'resource': 'T05',
        'flight_id': 'RX128',
        'until': 1277,
        'label': 'Maintenance delay · T05 released at 21:17, 105m after RX128’s planned departure',
    }


def _wx_ord(_s):
    return {
        'id': 'WX-ORD',
        'kind': 'weather',
        'airport': 'ORD',
        'start': 1120,
        'end': 1360,
        'label': 'ORD weather closure · synthetic 18:40–22:40 movement restriction',
    }


def _wx_jfk(_s):
    return {
        'id': 'WX-JFK',
        'kind': 'weather',
        'airport': 'JFK',
        'start': 1080,
        'end': 1320,
        'label': 'JFK weather closure · synthetic 18:00–22:00 movement restriction',
    }


def _ground_ord(s):
    signal_id = 'SIG-ORD-01'
    if not any(sig['id'] == signal_id for sig in s.get('unstructured_signals', [])):
        s.setdefault('unstructured_signals', []).append({
            'id': signal_id,
            'source': 'Synthetic Slack message · ORD Ground Ops',
            'text': "Unstructured Input: Slack message from ORD Ground Ops: 'De-icing trucks are backed up, add 45 mins to any gate turnaround.'",
            'start': 1140,
            'end': 1320,
        })
    return {
        'id': 'D-GND-ORD',
        'kind': 'ground_ops',
        'airport': 'ORD',
        'signal_id': signal_id,
        'label': 'ORD de-icing backlog · ground-ops text adds 45m to each affected turnaround',
    }


def _ground_dtw(s):
    signal_id = 'SIG-DTW-01'
    if not any(sig['id'] == signal_id for sig in s.get('unstructured_signals', [])):
        s.setdefault('unstructured_signals', []).append({
            'id': signal_id,
            'source': 'Synthetic Slack message · DTW Ground Ops',
            'text': "Unstructured Input: Slack message from DTW Ground Ops: 'De-icing trucks are backed up, add 45 mins to any gate turnaround.'",
            'start': 1140,
            'end': 1320,
        })
    return {
        'id': 'D-GND-DTW',
        'kind': 'ground_ops',
        'airport': 'DTW',
        'signal_id': signal_id,
        'label': 'DTW de-icing backlog · ground-ops text adds 45m to each affected turnaround',
    }


def _crew_c01(_s):
    return {
        'id': 'D-CREW-C01',
        'kind': 'crew_limit',
        'resource': 'C01',
        'max_duty': 650,
        'label': 'Crew availability update · C01 has only 45m buffer beyond its original final release',
    }


def _crew_c05(_s):
    return {
        'id': 'D-CREW-C05',
        'kind': 'crew_limit',
        'resource': 'C05',
        'max_duty': 650,
        'label': 'Crew availability update · C05 has only 45m buffer beyond its original final release',
    }


def _overnight_early(_s):
    return {
        'id': 'D-OVN-T01',
        'kind': 'overnight',
        'resource': 'T01',
        'deadline': 1320,
        'label': 'Overnight slot change · T01 must be at PIT by 22:00 to protect tomorrow’s first rotation',
    }


def _spare_unavailable(s):
    # Mark DTW spare R01 / RC01 unusable for this run (ready after the operating day).
    if 'R01' in s.get('tails', {}):
        s['tails']['R01']['ready'] = 1440
    if 'RC01' in s.get('crews', {}):
        s['crews']['RC01']['ready'] = 1440
    return {
        'id': 'D-SPARE-R01',
        'kind': 'mechanical',
        'resource': 'R01',
        'flight_id': 'FERRY-1',
        'until': 1440,
        'label': 'Spare unavailable · R01 / RC01 grounded at DTW for this run (maintenance hold through midnight)',
    }


ISSUES = {
    'mech_t01': {
        'id': 'mech_t01',
        'label': 'Mechanical hold — T01',
        'description': 'T01 maintenance release slips 105m past RX104’s planned departure.',
        'build': _mech_t01,
    },
    'mech_t05': {
        'id': 'mech_t05',
        'label': 'Mechanical hold — T05',
        'description': 'T05 maintenance release slips 105m past RX128’s planned departure.',
        'build': _mech_t05,
    },
    'wx_ord': {
        'id': 'wx_ord',
        'label': 'Weather closure — ORD',
        'description': 'ORD closed for a multi-hour winter movement restriction (18:40–22:40).',
        'build': _wx_ord,
    },
    'wx_jfk': {
        'id': 'wx_jfk',
        'label': 'Weather closure — JFK',
        'description': 'JFK closed for a multi-hour winter movement restriction (18:00–22:00).',
        'build': _wx_jfk,
    },
    'ground_ord': {
        'id': 'ground_ord',
        'label': 'Ground-ops delay — ORD',
        'description': 'ORD de-icing backlog adds 45 minutes to each affected gate turnaround.',
        'build': _ground_ord,
    },
    'ground_dtw': {
        'id': 'ground_dtw',
        'label': 'Ground-ops delay — DTW',
        'description': 'DTW de-icing backlog adds 45 minutes to each affected gate turnaround.',
        'build': _ground_dtw,
    },
    'crew_c01': {
        'id': 'crew_c01',
        'label': 'Crew duty reduction — C01',
        'description': 'C01 max duty cut to 650m, leaving a thin buffer on the final bank.',
        'build': _crew_c01,
    },
    'crew_c05': {
        'id': 'crew_c05',
        'label': 'Crew duty reduction — C05',
        'description': 'C05 max duty cut to 650m, leaving a thin buffer on the final bank.',
        'build': _crew_c05,
    },
    'overnight_early': {
        'id': 'overnight_early',
        'label': 'Overnight repositioning deadline moved up',
        'description': 'T01 overnight cutoff at PIT moved earlier to 22:00.',
        'build': _overnight_early,
    },
    'spare_unavailable': {
        'id': 'spare_unavailable',
        'label': 'Spare aircraft/crew unavailable',
        'description': 'DTW spare R01 and reserve crew RC01 are unusable for this run.',
        'build': _spare_unavailable,
    },
}


def catalog():
    return {
        'max_select': MAX_ISSUES,
        'issues': [
            {'id': i['id'], 'label': i['label'], 'description': i['description']}
            for i in ISSUES.values()
        ],
        'profiles': [
            {
                'id': p['id'],
                'label': p['label'],
                'description': p['description'],
                'issue_ids': list(p['issue_ids']),
            }
            for p in ISSUE_PROFILES.values()
        ],
    }


def resolve_profile(profile_id):
    if profile_id not in ISSUE_PROFILES:
        raise ValueError(f'Unknown issue profile: {profile_id}')
    return list(ISSUE_PROFILES[profile_id]['issue_ids'])


def resolve(issue_ids):
    if issue_ids is None:
        raise ValueError('issue_ids is required')
    if len(issue_ids) > MAX_ISSUES:
        raise ValueError(f'Select at most {MAX_ISSUES} issues')
    if len(set(issue_ids)) != len(issue_ids):
        raise ValueError('Duplicate issue ids are not allowed')
    missing = [i for i in issue_ids if i not in ISSUES]
    if missing:
        raise ValueError(f'Unknown issue id(s): {", ".join(missing)}')
    return [ISSUES[i] for i in issue_ids]


def apply_issues(scenario, issue_ids, profile_id=None):
    """Replace hard-coded disruptions with those built from the selected catalog ids."""
    selected = resolve(issue_ids)
    scenario['disruptions'] = []
    scenario['unstructured_signals'] = []
    for issue in selected:
        scenario['disruptions'].append(issue['build'](scenario))
    scenario['issue_ids'] = list(issue_ids)
    if profile_id and profile_id in ISSUE_PROFILES:
        pack = ISSUE_PROFILES[profile_id]
        scenario['profile'] = profile_id
        scenario['profile_note'] = f"{pack['label']} pack · {len(issue_ids)} of {MAX_ISSUES} max issues"
    else:
        scenario['profile'] = 'custom'
        scenario['profile_note'] = f'Custom desk selection · {len(issue_ids)} of {MAX_ISSUES} max issues'
    return scenario
