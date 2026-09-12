import hashlib
import pytest
from fastapi.testclient import TestClient
from backend import app as a, auth, store

CLAIMS = {
    'viewer': {'sub': 'auth0|viewer', 'org_name': 'pit-hub', 'scope': 'openid profile email read:scenarios'},
    'analyst': {
        'sub': 'auth0|analyst',
        'org_name': 'pit-hub',
        'scope': 'openid profile email read:scenarios write:scenarios fetch:observations',
    },
    'approver': {
        'sub': 'auth0|approver',
        'org_name': 'pit-hub',
        'scope': 'openid profile email read:scenarios write:scenarios approve:recovery fetch:observations',
    },
    'ord': {
        'sub': 'auth0|ord',
        'org_name': 'ord-hub',
        'scope': 'openid profile email read:scenarios write:scenarios approve:recovery fetch:observations',
    },
    'rbac': {
        'sub': 'auth0|rbac',
        'org_id': 'org_RBAC1',
        'permissions': ['read:scenarios', 'write:scenarios'],
    },
    'solo': {'sub': 'auth0|solo-user', 'scope': 'openid read:scenarios write:scenarios'},
}


async def fake_verify(request):
    header = request.headers.get('authorization', '')
    if not header.startswith('Bearer '):
        raise auth.AuthError(400, {'error': 'invalid_request', 'error_description': 'Missing Authorization header'})
    claims = CLAIMS.get(header.split(' ', 1)[1])
    if not claims:
        raise auth.AuthError(401, {'error': 'invalid_token', 'error_description': 'Unknown test token'})
    return dict(claims)


@pytest.fixture
def auth_on(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTH0_DOMAIN', 'flowbetter-test.us.auth0.com')
    monkeypatch.setenv('AUTH0_AUDIENCE', 'https://flowbetter.local/api')
    monkeypatch.setenv('AUTH0_CLIENT_ID', 'test-spa-client')
    monkeypatch.setattr(a, 'DATA', tmp_path)
    monkeypatch.setattr(auth, '_verify', fake_verify)
    auth.reset()
    return TestClient(a.app)


def headers(token, **extra):
    return {'Authorization': f'Bearer {token}', **extra}


def test_public_config_and_unauthenticated_api(auth_on):
    cfg = auth_on.get('/api/auth/config').json()
    assert cfg['enabled'] is True
    assert cfg['domain'] == 'flowbetter-test.us.auth0.com'
    assert cfg['audience'] == 'https://flowbetter.local/api'
    assert 'client_secret' not in cfg
    status = auth_on.get('/api/status').json()
    assert status['auth']['enabled'] is True
    assert status['desk'] in (None, False)
    denied = auth_on.get('/api/scenarios')
    assert denied.status_code == 400
    assert denied.json()['detail']['error'] == 'invalid_request'


def test_roles_and_org_isolation(auth_on):
    created = auth_on.post('/api/scenarios', json={'seed': 42}, headers=headers('analyst'))
    assert created.status_code == 200
    ident = created.json()['id']
    assert auth_on.get('/api/scenarios/' + ident, headers=headers('viewer')).status_code == 200
    assert auth_on.post('/api/scenarios', json={}, headers=headers('viewer')).status_code == 403
    assert auth_on.get('/api/scenarios/' + ident, headers=headers('ord')).status_code == 404
    assert auth_on.get('/api/scenarios/' + ident, headers=headers('analyst', **{'X-IROP-Desk': 'ord-hub'})).status_code == 200


def test_approval_requires_scope_and_records_actor(auth_on):
    ident = auth_on.post('/api/scenarios', json={'seed': 42}, headers=headers('analyst')).json()['id']
    auth_on.post(f'/api/scenarios/{ident}/disrupt', json={'revision': 0}, headers=headers('analyst'))
    report = auth_on.post(f'/api/scenarios/{ident}/experiments', json={'revision': 1}, headers=headers('analyst')).json()
    body = {'revision': 1, 'experiment_id': report['experiments'][0]['id'], 'plan': 'loyalty', 'confirm': True}
    forbidden = auth_on.post(f'/api/scenarios/{ident}/approve', json=body, headers=headers('analyst'))
    assert forbidden.status_code == 403
    assert forbidden.json()['detail']['error'] == 'insufficient_scope'
    approved = auth_on.post(f'/api/scenarios/{ident}/approve', json=body, headers=headers('approver'))
    assert approved.status_code == 200
    events = approved.json()['events']
    actor = next(e['data']['actor'] for e in events if e['action'] == 'simulation_approved')
    assert actor['sub'] == 'auth0|approver' and actor['org_name'] == 'pit-hub'


def test_permissions_claim_and_personal_desk(auth_on):
    assert auth_on.post('/api/scenarios', json={}, headers=headers('rbac')).status_code == 200
    me = auth_on.get('/api/auth/me', headers=headers('solo')).json()
    digest = hashlib.sha256(b'auth0|solo-user').hexdigest()[:12]
    assert me['desk'] == f'u-{digest}'
    assert me['identity']['sub'] == 'auth0|solo-user'


def test_desk_from_org_and_custom_claim():
    assert auth.desk_for({'org_name': 'PIT Hub'}) == 'pit-hub'
    assert auth.desk_for({auth.DESK_CLAIM: 'ord-occ'}) == 'ord-occ'
    assert auth.desk_for({'sub': 'auth0|solo-user'}).startswith('u-')
