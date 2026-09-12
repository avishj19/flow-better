from copy import deepcopy
import pytest
from backend.simulator import generate, simulate, validate, rank, PLANS

@pytest.mark.parametrize('seed',[0,1,7,42,111,999999])
def test_reproducible_baseline(seed):
    s=generate(seed)
    assert s==generate(seed)
    r=simulate(s,disrupted=False)
    assert len(r['flights'])==60 and len(s['airports'])==6
    assert r['feasible'] and r['metrics']['delay_minutes']==0
    assert all(not c['missed'] for c in r['connections'])
    assert all(f['pax']>=sum(c['pax'] for c in s['connections'] if f['id'] in (c['inbound'],c['outbound'])) for f in s['flights'])

def test_cascade_and_connections():
    s=generate();r=simulate(s)
    first=next(f for f in r['flights'] if f['id']=='RX100')
    last=next(f for f in r['flights'] if f['id']=='RX105')
    assert first['delay']==165 and last['delay']>0
    assert r['metrics']['delayed_flights']>4 and r['metrics']['missed_pax']>0
    assert any(e['kind']=='crew_duty' and not e['passed'] for e in r['evidence'])
    assert any('Crew C03' in cause for f in r['flights'] for cause in f['causes'])
    assert any('D2' in f['causes'] for f in r['flights'])

@pytest.mark.parametrize('plan,feasible',[('delay',False),('crew',True),('combined',True),('protect',True),('remote',False),('small',False)])
def test_options(plan,feasible):
    r=simulate(generate(),plan)
    assert r['feasible']==feasible

def test_ranking_and_cost():
    s=generate();opts=rank([simulate(s,p) for p in PLANS])
    assert opts[0]['plan']=='protect'
    assert opts[0]['metrics']['missed_pax']==0
    assert [o['rank'] for o in opts]==[1,2,3,None,None,None]
    for o in opts:
        m=o['metrics'];assert m['cost']==sum(m['cost_breakdown'].values())
    assert opts[0]['metrics']['passenger_minutes']>opts[1]['metrics']['passenger_minutes']

@pytest.mark.parametrize('kind',['aircraft_position','aircraft_time','crew_position','crew_time','capacity','qualification','crew_duty','crew_rest','crew_segments','crew_flight_time','gate','weather','schedule','coverage'])
def test_verifier_rejects_tampered_schedule(kind):
    s=generate();fs=simulate(s,'combined')['flights'];f=fs[0]
    if kind=='aircraft_position':s['tails'][f['tail']]['position']='BOS'
    if kind=='aircraft_time':s['tails'][f['tail']]['ready']=f['actual_dep']+1
    if kind=='crew_position':s['crews'][f['crew']]['position']='BOS'
    if kind=='crew_time':s['crews'][f['crew']]['ready']=f['actual_dep']+1
    if kind=='capacity':s['tails'][f['tail']]['capacity']=1
    if kind=='qualification':s['crews'][f['crew']]['type']='WRONG'
    if kind=='crew_duty':s['rules']['duty']=100
    if kind=='crew_rest':s['crews'][f['crew']]['rest']=0
    if kind=='crew_segments':s['rules']['segments']=1
    if kind=='crew_flight_time':s['rules']['flight_time']=1
    if kind=='gate':s['airports']['PIT']['gates']=1
    if kind=='weather':f['actual_dep']=480
    if kind=='schedule':f['pax']=1
    if kind=='coverage':fs.pop()
    assert any(e['kind']==kind and not e['passed'] for e in validate(s,fs))

def test_overlap_and_turnaround():
    s=generate();fs=simulate(s,'combined')['flights'];route=sorted([f for f in fs if f['tail']=='R01'],key=lambda f:f['dep'])
    route[1]['actual_dep']=route[0]['actual_arr']+29
    assert any(e['kind']=='aircraft_time' and not e['passed'] for e in validate(s,fs))
    route[1]['actual_dep']=route[0]['actual_arr']-1
    assert any(e['kind']=='crew_time' and not e['passed'] for e in validate(s,fs))

def test_resource_independence_and_no_mutation():
    s=generate();before=deepcopy(s);simulate(s,'protect');assert s==before
    with pytest.raises(ValueError):simulate(s,'teleport')
