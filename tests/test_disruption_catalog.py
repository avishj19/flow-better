"""Tests for the selectable disruption catalog and from-issues API."""
from copy import deepcopy
import pytest
from fastapi.testclient import TestClient
from backend import app as a
from backend.disruption_catalog import (
    MAX_ISSUES, catalog, apply_issues, resolve, resolve_profile, ISSUES, ISSUE_PROFILES,
)
from backend.simulator import generate, simulate, rank, PLANS


def test_catalog_has_exactly_ten_issues():
    payload = catalog()
    assert payload['max_select'] == MAX_ISSUES == 4
    assert len(payload['issues']) == 10 == len(ISSUES)
    assert {i['id'] for i in payload['issues']} == set(ISSUES)


def test_catalog_exposes_mechanical_profile_only():
    payload = catalog()
    assert list(ISSUE_PROFILES) == ['mechanical']
    assert {p['id'] for p in payload['profiles']} == {'mechanical'}
    assert resolve_profile('mechanical') == ISSUE_PROFILES['mechanical']['issue_ids']
    assert set(resolve_profile('mechanical')) <= set(ISSUES)
    s = apply_issues(generate(42), resolve_profile('mechanical'), profile_id='mechanical')
    assert s['profile'] == 'mechanical'
    assert {d['kind'] for d in s['disruptions']} == {'mechanical'}


def test_resolve_rejects_more_than_four():
    with pytest.raises(ValueError, match='at most'):
        resolve(['mech_t01', 'mech_t05', 'wx_ord', 'wx_jfk', 'ground_ord'])


def test_apply_issues_replaces_hardcoded_disruptions():
    s = generate(42)
    assert len(s['disruptions']) == 4
    apply_issues(s, ['mech_t01', 'wx_jfk', 'crew_c05', 'overnight_early'])
    assert len(s['disruptions']) == 4
    assert {d['kind'] for d in s['disruptions']} == {'mechanical', 'weather', 'crew_limit', 'overnight'}
    assert s['issue_ids'] == ['mech_t01', 'wx_jfk', 'crew_c05', 'overnight_early']
    assert s['profile'] == 'custom'


def test_ground_dtw_injects_signal():
    s = generate(42)
    apply_issues(s, ['ground_dtw'])
    assert any(d['kind'] == 'ground_ops' and d['airport'] == 'DTW' for d in s['disruptions'])
    assert any(sig['id'] == 'SIG-DTW-01' for sig in s['unstructured_signals'])
    assert simulate(s, 'cfo')  # parse_signals must succeed


def test_spare_pool_scaled_to_two_spokes():
    s = generate(42)
    assert sorted(t for t in s['tails'] if t.startswith('R')) == ['R01', 'R02', 'R03']
    assert sorted(c for c in s['crews'] if c.startswith('RC')) == ['RC01', 'RC02', 'RC03']
    assert s['tails']['R01']['overnight_hub'] == 'DTW'
    assert s['tails']['R02']['overnight_hub'] == 'DTW'
    assert s['tails']['R03']['overnight_hub'] == 'ORD'
    assert s['airports']['DTW']['overnight_role'] == 'spare_base'
    assert s['airports']['ORD']['overnight_role'] == 'spare_base'


def test_same_issue_set_is_deterministic():
    ids = ['mech_t01', 'ground_ord', 'crew_c01', 'overnight_early']
    a_run = apply_issues(generate(42), ids)
    b_run = apply_issues(generate(42), ids)
    assert a_run == b_run
    scores_a = {o['plan']: o['scores'] for o in rank([simulate(deepcopy(a_run), p) for p in PLANS])}
    scores_b = {o['plan']: o['scores'] for o in rank([simulate(deepcopy(b_run), p) for p in PLANS])}
    assert scores_a == scores_b


def test_different_issue_sets_change_scores():
    set_a = ['mech_t01', 'ground_ord', 'crew_c01', 'overnight_early']
    set_b = ['mech_t05', 'wx_jfk', 'crew_c05', 'spare_unavailable']
    sa = apply_issues(generate(42), set_a)
    sb = apply_issues(generate(42), set_b)
    scores_a = {o['plan']: o['scores'] for o in rank([simulate(sa, p) for p in PLANS])}
    scores_b = {o['plan']: o['scores'] for o in rank([simulate(sb, p) for p in PLANS])}
    assert scores_a != scores_b
    # At least one plan differs on financial or passenger impact across the two selections.
    diffs = [
        (plan, scores_a[plan]['financial_cost'], scores_b[plan]['financial_cost'],
         scores_a[plan]['passenger_impact'], scores_b[plan]['passenger_impact'])
        for plan in PLANS
        if scores_a[plan] != scores_b[plan]
    ]
    assert diffs


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(a, 'DATA', tmp_path)
    return TestClient(a.app)


def test_from_issues_endpoint_rejects_more_than_four(client):
    r = client.post('/api/scenarios/from-issues', json={
        'seed': 42,
        'issue_ids': ['mech_t01', 'mech_t05', 'wx_ord', 'wx_jfk', 'ground_ord'],
    })
    assert r.status_code == 400


def test_from_issues_endpoint_creates_scenario(client):
    catalog_r = client.get('/api/disruption-issues')
    assert catalog_r.status_code == 200
    assert len(catalog_r.json()['issues']) == 10
    assert {p['id'] for p in catalog_r.json()['profiles']} == {'mechanical'}
    r = client.post('/api/scenarios/from-issues', json={
        'seed': 42,
        'issue_ids': ['mech_t01', 'wx_ord', 'crew_c01', 'overnight_early'],
    })
    assert r.status_code == 200
    body = r.json()
    assert body['profile'] == 'custom'
    assert body['issue_ids'] == ['mech_t01', 'wx_ord', 'crew_c01', 'overnight_early']
    assert len(body['scenario']['disruptions']) == 4
    disrupted = client.post(f"/api/scenarios/{body['id']}/disrupt", json={'revision': 0})
    assert disrupted.status_code == 200


def test_from_issues_mechanical_profile(client):
    r = client.post('/api/scenarios/from-issues', json={'seed': 42, 'profile': 'mechanical'})
    assert r.status_code == 200
    body = r.json()
    assert body['profile'] == 'mechanical'
    assert body['issue_ids'] == ISSUE_PROFILES['mechanical']['issue_ids']
    assert {d['kind'] for d in body['scenario']['disruptions']} == {'mechanical'}
