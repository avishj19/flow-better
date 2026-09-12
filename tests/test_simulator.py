"""Ground-ops desk simulator tests (model v3)."""
from backend.issues import MAX_ISSUES, catalog, resolve
from backend.simulator import MODEL_VERSION, generate, option_by_id


def test_catalog_has_enough_issues_and_categories():
    c = catalog()
    assert c['max_select'] == MAX_ISSUES == 4
    assert len(c['issues']) >= 10
    cats = {i['category'] for i in c['issues']}
    assert {'weather', 'mechanical', 'human', 'airport', 'network'} <= cats


def test_resolve_limits():
    try:
        resolve([])
        assert False
    except ValueError:
        pass
    try:
        resolve(['wx_pit_snow'] * 2)
        assert False
    except ValueError:
        pass
    try:
        resolve(['wx_pit_snow', 'wx_ne_cascade', 'wx_ord_deice', 'wx_jfk_fog', 'mx_tail_late'])
        assert False
    except ValueError:
        pass
    issues = resolve(['mx_tail_late', 'crew_timeout'])
    assert [i['id'] for i in issues] == ['mx_tail_late', 'crew_timeout']


def test_generate_baseline_without_issues():
    s = generate(42)
    assert s['model_version'] == MODEL_VERSION
    assert s['situation'] is None
    assert len(s['ground']['aircraft']) >= 8
    assert s['ground']['hub'] == 'PIT'


def test_ne_cascade_blocks_absorb_and_ferry():
    s = generate(42, ['wx_ne_cascade', 'crew_timeout'])
    assert s['situation']['severity'] >= 7
    assert 'JFK' in s['situation']['holds']
    by_id = {o['id']: o for o in s['options']}
    assert by_id['cancel_last_bank']['feasible'] is True
    assert by_id['absorb']['feasible'] is False
    assert by_id['ferry_spare']['feasible'] is False
    assert 3 <= len(s['options']) <= 5
    for o in s['options']:
        assert 'cost' in o and 'people' in o and 'regulation' in o and 'tradeoffs' in o


def test_mechanical_local_keeps_absorb_or_swap():
    s = generate(7, ['mx_apu_gate', 'ramp_short'])
    feasible = [o for o in s['options'] if o['feasible']]
    assert feasible
    assert any(o['id'] in ('absorb', 'swap_reserve', 'ferry_spare') for o in feasible)


def test_option_by_id():
    s = generate(1, ['misconnect_wave'])
    opt = option_by_id(s, 'protect_connections')
    assert opt and opt['id'] == 'protect_connections'
    assert option_by_id(s, 'nope') is None


def test_seed_changes_pax_loads():
    a = generate(1, ['gate_conflict'])
    b = generate(99, ['gate_conflict'])
    pax_a = [x['pax_booked'] for x in a['ground']['aircraft'] if x['airport'] == 'PIT']
    pax_b = [x['pax_booked'] for x in b['ground']['aircraft'] if x['airport'] == 'PIT']
    assert pax_a != pax_b
