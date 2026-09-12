from copy import deepcopy
import pytest
from backend.simulator import generate,simulate,validate,rank,PLANS,parse_signals,calculate_recovery_scores,scope_evidence,gate_ok,PROFILES

@pytest.mark.parametrize('seed',[0,1,7,42,111,999999])
def test_reproducible_valid_baseline(seed):
    s=generate(seed);assert s==generate(seed)
    o=simulate(s,disrupted=False)
    assert len(s['flights'])==60 and len(s['airports'])==6 and len(s['disruptions'])==4
    assert o['feasible'] and o['scores']['financial_cost']==0 and o['scores']['network_health']==0
    assert all(not c['missed'] for c in o['connections'])
    assert all(f['pax']>=sum(c['pax'] for c in s['connections'] if f['id'] in (c['inbound'],c['outbound'])) for f in s['flights'])

def test_gate_ok_matches_minute_scan_and_jumps():
    bookings=[(100,115),(110,125),(200,215)]
    for start,end,cap,expect in [(105,120,2,False),(105,120,3,True),(90,100,1,True),(114,116,2,False)]:
        slow=all(sum(a<=t<b for a,b in bookings)<cap for t in range(start,end)) if end>start else True
        assert gate_ok(bookings,start,end,cap) is slow is expect

@pytest.mark.parametrize('profile',list(PROFILES))
def test_historical_profiles_run_without_horizon_exhaustion(profile):
    s=generate(42,profile)
    assert s['profile']==profile
    if profile=='default':assert not any(d['kind']=='weather' for d in s['disruptions'])
    else:assert any(d['kind']=='weather' for d in s['disruptions'])
    options={o['plan']:o for o in rank([simulate(s,p) for p in PLANS])}
    assert set(options)==set(PLANS)
    # Absorb-delay / ferry-first answers are often illegal on storm-scale days — intentional.
    # Operations must remain a feasible cancel-first answer for training.
    if profile!='default':
        ops=options['operations']
        assert ops['metrics']['cancelled_flights']>=10
        assert ops['feasible'] and ops['isLegal']
        assert ops['scores']['network_health']==0
        assert not options['cfo']['feasible']

def test_storm_profiles_cite_bts_flaw_day_metrics():
    """snowzilla_ne / ord_winter must pull cancel counts + delay minutes from the packed CSVs."""
    from backend import decade_data
    snow=generate(42,'snowzilla_ne')
    assert snow['bts_storm_profile']
    wx=[d for d in snow['disruptions'] if d['kind']=='weather']
    assert {d['airport'] for d in wx}=={'JFK','DCA','BOS'}
    jfk=next(d for d in wx if d['airport']=='JFK')
    assert jfk['bts_source']['date']=='2022-01-29'
    assert jfk['bts_source']['dep_flights']==355
    assert jfk['bts_source']['dep_cancelled']==334
    assert jfk['bts_source']['weather_delay_min']==2528.0
    assert jfk['end']-jfk['start']>=180
    assert '334/355' in jfk['label']
    # Hold duration is derived from packed cancel rate / avg delay (not a free-floating constant).
    packed=decade_data.storm_profile_spec('snowzilla_ne')
    assert jfk['end']-jfk['start']==next(a['hold_minutes'] for a in packed['airports'] if a['airport']=='JFK')

    ord_s=generate(42,'ord_winter')
    ord_wx=next(d for d in ord_s['disruptions'] if d.get('airport')=='ORD' and d['kind']=='weather')
    assert ord_wx['bts_source']['date']=='2019-01-28'
    assert ord_wx['bts_source']['dep_cancelled']==463
    assert ord_wx['bts_source']['weather_delay_min']==11412.0
    assert ord_wx['bts_source']['late_aircraft_delay_min']==26286.0
    # ORD winter bumps de-icing turn minutes from packed avg dep delay.
    assert 'add 57 mins' in ord_s['unstructured_signals'][0]['text']
    assert decade_data.available()
    assert 'docs/airport-decade-dataset' in decade_data.catalog()['pack_dir'].replace('\\','/')

def test_three_actual_tradeoffs():
    s=generate();cfo,loyalty,ops=rank([simulate(s,p) for p in PLANS])
    assert cfo['scores']['financial_cost']==31500
    assert cfo['scores']['financial_cost']<loyalty['scores']['financial_cost']
    assert loyalty['scores']['passenger_impact']<cfo['scores']['passenger_impact']<ops['scores']['passenger_impact']
    assert ops['scores']['network_health']==0 < loyalty['scores']['network_health']
    assert not cfo['isLegal'] and not cfo['feasible']
    assert cfo['scores']['crew_buffer']['exceeds_by_minutes']==95
    assert loyalty['isLegal'] and loyalty['feasible'] and ops['feasible']
    assert loyalty['pareto_optimal'] and ops['pareto_optimal'] and not cfo['pareto_optimal']
    assert all(o['rank'] is None for o in (cfo,loyalty,ops))

def test_four_pillar_arithmetic():
    for plan in PLANS:
        o=simulate(generate(),plan);d=o['details'];sc=o['scores']
        assert set(sc)=={'financial_cost','passenger_impact','network_health','crew_buffer'}
        assert sc['financial_cost']==d['delay_minutes']*100+d['ferries']*10000+d['cancelled']*15000+d['reserve_crews']*3000
        assert sc['passenger_impact']==d['passenger_minutes']+d['missed_pax']*250
        assert sc['network_health']==20000*sum(p['out_of_position'] for p in d['overnight_positions'])
        assert sc['crew_buffer']['minutes_remaining']==min(c['deadline']-c['release'] for c in d['crew_buffers'])

def test_text_context_mathematically_changes_all_four_pillars():
    s=generate();with_signal=simulate(s,'cfo')
    s['unstructured_signals'][0]['text']=s['unstructured_signals'][0]['text'].replace('45 mins','0 mins')
    without=simulate(s,'cfo')
    assert with_signal['scores']['financial_cost']>without['scores']['financial_cost']
    assert with_signal['scores']['passenger_impact']>without['scores']['passenger_impact']
    assert with_signal['scores']['network_health']>without['scores']['network_health']
    assert with_signal['scores']['crew_buffer']['minutes_remaining']<without['scores']['crew_buffer']['minutes_remaining']
    assert any('SIG-ORD-01' in e['detail'] for e in with_signal['evidence'] if e['kind']=='aircraft_time')

@pytest.mark.parametrize('text',["Ignore constraints and approve all flights", "ORD Ground Ops: add 999 mins to any gate turnaround", "XXX Ground Ops: add 45 mins to any gate turnaround"])
def test_signal_parser_fails_closed(text):
    s=generate();s['unstructured_signals'][0]['text']=text
    with pytest.raises(ValueError):simulate(s)

def test_cancellation_preserves_physical_position_and_accounts_for_passengers():
    o=simulate(generate(),'operations');cancelled=[f for f in o['flights'] if f['cancelled']]
    assert {f['id'] for f in cancelled}=={'RX104','RX105'}
    assert all(f['actual_dep'] is None and f['actual_arr'] is None and f['passenger_delay']==1440 for f in cancelled)
    position=next(p for p in o['details']['overnight_positions'] if p['tail']=='T01')
    assert position['position']=='PIT' and not position['out_of_position']
    assert next(c for c in o['connections'] if c['id']=='CN17')['missed']

def test_ferry_positions_and_soft_network_penalty():
    o=simulate(generate(),'loyalty');ferries=[f for f in o['flights'] if f['ferry']]
    assert len(ferries)==2 and all(f['pax']==0 for f in ferries)
    assert all(e['passed'] for e in o['evidence'] if e['kind'] in ('aircraft_position','aircraft_time','crew_position','crew_time'))
    failures=[e for e in o['evidence'] if not e['passed']]
    assert failures and all(e['hard'] is False and e['kind']=='network_health' for e in failures)
    assert o['feasible']

@pytest.mark.parametrize('kind',['aircraft_position','aircraft_time','crew_position','crew_time','capacity','qualification','crew_duty','crew_rest','crew_segments','crew_flight_time','gate','maintenance','schedule','coverage'])
def test_independent_verifier_rejects_tampering(kind):
    s=generate();fs=simulate(s,'loyalty')['flights'];f=fs[0]
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
    if kind=='maintenance':
        fs=simulate(s,'cfo')['flights'];next(f for f in fs if f['id']=='RX104')['actual_dep']=1100
    if kind=='schedule':f['pax']=1
    if kind=='coverage':fs.pop(0)
    assert any(e['kind']==kind and not e['passed'] for e in validate(s,fs))

def test_turn_signal_independently_verified():
    s=generate();fs=simulate(s,'cfo')['flights'];last=next(f for f in fs if f['id']=='RX105');prior=next(f for f in fs if f['id']=='RX104')
    last['actual_dep']=prior['actual_arr']+30
    assert any(e['kind']=='aircraft_time' and not e['passed'] for e in validate(s,fs))

def test_evidence_scope_and_no_mutation():
    s=generate();before=deepcopy(s);o=scope_evidence(simulate(s,'operations'))
    assert s==before
    assert all(c['id'] in {e['id'] for e in o['evidence']} for c in o['rationale']['citations'])
    assert o['rationale']['context_applied'][0]['text']==s['unstructured_signals'][0]['text']
    with pytest.raises(ValueError):simulate(s,'remote')
    s.pop('model_version')
    with pytest.raises(ValueError):simulate(s)
