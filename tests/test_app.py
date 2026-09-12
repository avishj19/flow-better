import concurrent.futures
import pytest
from fastapi.testclient import TestClient
from backend import app as a,store

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(a,'DATA',tmp_path)
    return TestClient(a.app)
def prepared(client):
    r=client.post('/api/scenarios',json={'seed':42}).json();ident=r['id']
    r=client.post(f'/api/scenarios/{ident}/disrupt',json={'revision':0}).json()
    r=client.post(f'/api/scenarios/{ident}/experiments',json={'revision':1}).json()
    return r,{'revision':1,'experiment_id':r['experiments'][0]['id'],'plan':'protect','confirm':True}

def test_full_flow_persistence_stale_and_rejected(client):
    r,b=prepared(client);p=f"/api/scenarios/{r['id']}/approve"
    assert client.post(p,json=dict(b,plan='remote')).status_code==409
    assert client.post(p,json=dict(b,confirm=False)).status_code==422
    assert client.post(p,json=dict(b,revision=0)).status_code==409
    ok=client.post(p,json=b);assert ok.status_code==200
    final=ok.json();assert final['phase']=='recovered' and final['current']['metrics']['missed_pax']==0 and final['revision']==2
    assert client.post(p,json=b).status_code==409
    loaded=client.get('/api/scenarios/'+r['id']).json()
    assert len(loaded['events'])==8 and loaded['current']==final['current']
    assert client.get('/api/scenarios').json()[0]['phase']=='recovered'

def test_desk_isolation_origin_and_validation(client):
    r=client.post('/api/scenarios',json={}).json()
    assert client.get('/api/scenarios/'+r['id'],headers={'X-IROP-Desk':'other'}).status_code==404
    bad_desk=client.get('/api/scenarios',headers={'X-IROP-Desk':'../other'})
    assert bad_desk.status_code==400 and bad_desk.json()['detail']
    blocked=client.post('/api/scenarios',json={},headers={'Origin':'http://evil.test'})
    assert blocked.status_code==403 and blocked.json()['detail']=='Cross-origin writes forbidden'
    assert client.post('/api/scenarios',json={},headers={'Origin':'http://127.0.0.1:8010'}).status_code==200
    assert client.post('/api/scenarios',json={'seed':True}).status_code==422

def test_tamper_revalidation(client):
    r,b=prepared(client);r['scenario']['tails']['R01']['capacity']=1;store.save_run(a.DATA,r)
    assert client.post(f"/api/scenarios/{r['id']}/approve",json=b).status_code==409

def test_duplicate_approval_concurrent(client):
    r,b=prepared(client)
    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        codes=list(pool.map(lambda _:client.post(f"/api/scenarios/{r['id']}/approve",json=b).status_code,range(2)))
    assert sorted(codes)==[200,409]

def test_live_consent_and_phase(client):
    r=client.post('/api/scenarios',json={}).json();path='/api/scenarios/'+r['id']
    assert client.post(path+'/experiments',json={'revision':0}).status_code==409
    client.post(path+'/disrupt',json={'revision':0})
    assert client.post(path+'/disrupt',json={'revision':1}).status_code==409
    assert client.post(path+'/experiments',json={'revision':1,'mode':'live','consent':False}).status_code==422
