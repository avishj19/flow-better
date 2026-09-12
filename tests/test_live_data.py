from copy import deepcopy
import time
import pytest
from fastapi.testclient import TestClient
from backend import live_data as live, app as a

def weather(at):
    return [{'icaoId':'K'+airport,'obsTime':at,'fltCat':'VFR','wspd':5,'visib':'10+','rawOb':'Synthetic test METAR'} for airport in live.BOUNDS]

def test_weather_cache_normalization_and_policy(tmp_path):
    at=time.time();calls=[];raw=weather(at)
    raw[0]['fltCat']='IFR';raw[1]['wgst']=35;raw[2]['wxString']='TSRA'
    def provider(*args):calls.append(args);return raw
    s=live.fetch(tmp_path,'weather',request=provider,at=at)
    assert len(s['rows'])==6 and not s['missing_airports']
    cached=live.fetch(tmp_path,'weather',request=provider,at=at+2)
    assert cached['id']==s['id'] and cached['cached'] and len(calls)==1
    ds,decisions=live.projected_weather(s,at=at)
    assert [d['end']-d['start'] for d in ds]==[30,45,60]
    assert all(d['rule']=='demo-weather-v2' for d in decisions)
    assert all('not an official closure' in d['basis'] for d in decisions)
    # Three-airport IFR/LIFR cascade adds a teaching bonus on top of each non-zero hold.
    hard=[{**row,'fltCat':'IFR'} for row in weather(at)]
    hard[0]['fltCat']='LIFR';hard[1]['fltCat']='IFR';hard[2]['fltCat']='IFR'
    s2=live.fetch(tmp_path/'cascade','weather',request=lambda *args:hard,at=at)
    ds2,dec2=live.projected_weather(s2,at=at)
    assert all(d['hold_minutes']>=30+30 for d in dec2 if d['hold_minutes'])
    assert live.read(tmp_path,s['id'])['rows']==s['rows']
@pytest.mark.parametrize('change',['stale','missing','unknown','future','sandbox'])
def test_projection_fails_closed(tmp_path,change):
    at=time.time();s=live.fetch(tmp_path,'weather',request=lambda *args:weather(at),at=at)
    if change=='stale':s['rows'][0]['observed_epoch']=at-5401
    if change=='missing':s['rows'].pop()
    if change=='unknown':s['rows'][0]['category']='UNKNOWN'
    if change=='future':s['rows'][0]['observed_epoch']=at+301
    if change=='sandbox':s['environment']='sandbox'
    with pytest.raises(ValueError):live.projected_weather(s,at=at)

def test_fr24_token_consent_request_contract_and_ground_uncertainty(tmp_path,monkeypatch):
    at=time.time();monkeypatch.delenv('FR24_API_TOKEN',raising=False)
    with pytest.raises(ValueError):live.fetch(tmp_path,'fr24',consent=True)
    monkeypatch.setenv('FR24_API_TOKEN','test-only-token')
    with pytest.raises(ValueError):live.fetch(tmp_path,'fr24')
    def provider(url,params,headers):
        assert url==live.FR24 and params=={'bounds':live.BOUNDS['PIT'],'limit':50}
        assert headers['Authorization']=='Bearer test-only-token' and headers['Accept-Version']=='v1'
        return {'data':[{'fr24_id':'a','lat':40.48,'lon':-80.22,'timestamp':live.stamp(at),'reg':'TEST','gspeed':0,'alt':1200},{'fr24_id':'b','lat':0,'lon':0,'timestamp':live.stamp(at)}]}
    s=live.fetch(tmp_path,'fr24',consent=True,request=provider,at=at)
    assert len(s['rows'])==1 and s['rows'][0]['available_for_swap'] is False
    assert 'unconfirmed' in s['rows'][0]['ground_status']
    assert 'test-only-token' not in str(s)

def test_provider_failure_does_not_fabricate_or_save(tmp_path):
    with pytest.raises(ValueError):live.fetch(tmp_path,'weather',request=lambda *args:{'error':'bad'})
    assert live.snapshots(tmp_path)==[]

def test_projection_invalidates_and_expired_observations_block_approval(tmp_path,monkeypatch):
    monkeypatch.setattr(a,'DATA',tmp_path)
    at=time.time();s=live.fetch(tmp_path,'weather',request=lambda *args:weather(at),at=at)
    c=TestClient(a.app);r=c.post('/api/scenarios',json={}).json();path='/api/scenarios/'+r['id']
    c.post(path+'/disrupt',json={'revision':0})
    r=c.post(path+'/experiments',json={'revision':1}).json();old=r['experiments'][0]['id']
    r=c.post(path+'/weather-projection',json={'revision':1,'snapshot_id':s['id']}).json()
    assert r['revision']==2 and r['phase']=='disrupted' and len(r['state_versions'])==1
    assert not any(d['kind']=='weather' for d in r['scenario']['disruptions'])
    assert c.post(path+'/approve',json={'revision':2,'experiment_id':old,'plan':'loyalty','confirm':True}).status_code==409
    r=c.post(path+'/experiments',json={'revision':2}).json();new=r['experiments'][-1]['id']
    monkeypatch.setattr(live,'now',lambda:at+6000)
    response=c.post(path+'/approve',json={'revision':2,'experiment_id':new,'plan':'loyalty','confirm':True})
    assert response.status_code==409 and 'stale' in response.text
    assert c.post(path+'/weather-projection',json={'revision':2,'snapshot_id':s['id']},headers={'X-IROP-Desk':'other'}).status_code==404
