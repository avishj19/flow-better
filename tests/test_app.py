"""API tests for the ground-ops desk."""
import concurrent.futures

import pytest
from fastapi.testclient import TestClient

from backend import app as a


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(a, 'DATA', tmp_path)
    return TestClient(a.app)


def create_run(client, issue_ids=None, seed=42, headers=None):
    body = {'seed': seed, 'issue_ids': issue_ids or ['mx_tail_late', 'crew_timeout']}
    return client.post('/api/scenarios', json=body, headers=headers or {})


def test_health_and_issues(client):
    h = client.get('/api/health').json()
    assert h['ok'] and h['model_version'] == 3 and h['mode'] == 'ground_ops_desk'
    issues = client.get('/api/issues').json()
    assert issues['max_select'] == 4
    assert len(issues['issues']) >= 10


def test_create_situation_and_approve(client):
    r = create_run(client, ['wx_ne_cascade', 'overnight_squeeze']).json()
    assert r['phase'] == 'options'
    assert r['situation']['holds']
    assert 3 <= len(r['options']) <= 5
    feasible = next(o for o in r['options'] if o['feasible'])
    bad = client.post(
        f"/api/scenarios/{r['id']}/approve",
        json={'option_id': feasible['id'], 'confirm': False},
    )
    assert bad.status_code == 422
    ok = client.post(
        f"/api/scenarios/{r['id']}/approve",
        json={'option_id': feasible['id'], 'confirm': True},
    )
    assert ok.status_code == 200
    final = ok.json()
    assert final['phase'] == 'done'
    assert final['selected_option_id'] == feasible['id']
    assert final['decision']['title'] == feasible['title']
    assert client.post(
        f"/api/scenarios/{r['id']}/approve",
        json={'option_id': feasible['id'], 'confirm': True},
    ).status_code == 409
    listed = client.get('/api/scenarios').json()
    assert listed[0]['phase'] == 'done'
    loaded = client.get(f"/api/scenarios/{r['id']}").json()
    assert loaded['decision']['option_id'] == feasible['id']


def test_validation_and_blocked_option(client):
    assert client.post('/api/scenarios', json={'seed': 1, 'issue_ids': []}).status_code == 422
    assert client.post(
        '/api/scenarios',
        json={'seed': 1, 'issue_ids': ['wx_pit_snow'] * 2},
    ).status_code == 400
    r = create_run(client, ['wx_ne_cascade']).json()
    blocked = next(o for o in r['options'] if not o['feasible'])
    assert client.post(
        f"/api/scenarios/{r['id']}/approve",
        json={'option_id': blocked['id'], 'confirm': True},
    ).status_code == 409


def test_desk_isolation_and_origin(client):
    r = create_run(client).json()
    assert client.get(f"/api/scenarios/{r['id']}", headers={'X-IROP-Desk': 'other'}).status_code == 404
    assert client.get('/api/scenarios', headers={'X-IROP-Desk': '../other'}).status_code == 400
    assert client.post(
        '/api/scenarios',
        json={'seed': 1, 'issue_ids': ['ramp_short']},
        headers={'Origin': 'http://evil.test'},
    ).status_code == 403
    assert client.post(
        '/api/scenarios',
        json={'seed': 1, 'issue_ids': ['ramp_short']},
        headers={'Origin': 'http://127.0.0.1:8010'},
    ).status_code == 200


def test_duplicate_approval_concurrent(client):
    r = create_run(client, ['gate_conflict', 'misconnect_wave']).json()
    opt = next(o for o in r['options'] if o['feasible'])
    body = {'option_id': opt['id'], 'confirm': True}
    path = f"/api/scenarios/{r['id']}/approve"
    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        codes = list(pool.map(lambda _: client.post(path, json=body).status_code, range(2)))
    assert sorted(codes) == [200, 409]


def test_status_alias(client):
    assert client.get('/api/status').json()['model_version'] == 3
