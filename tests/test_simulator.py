from copy import deepcopy
import pytest
from backend.simulator import generate,simulate,validate,rank,PLANS,parse_signals,calculate_recovery_scores,scope_evidence,discover,desk_brief

@pytest.mark.parametrize('seed',[0,1,7,42,111,999999])
def test_reproducible_valid_baseline(seed):
    s=generate(seed);assert s==generate(seed)
    o=simulate(s,disrupted=False)
    assert len(s['flights'])==60 and len(s['airports'])==6 and len(s['disruptions'])==4
    assert o['feasible'] and o['scores']['financial_cost']==0 and o['scores']['network_health']==0
    assert all(not c['missed'] for c in o['connections'])
    assert all(f['pax']>=sum(c['pax'] for c in s['connections'] if f['id'] in (c['inbound'],c['outbound'])) for f in s['flights'])

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

def test_bounded_search_surfaces_holdback():
    s=generate();named=[simulate(s,p) for p in PLANS]
    options,note=discover(s,named);ranked=rank(options)
    by={o['plan']:o for o in ranked}
    assert note['surfaced']==['holdback'] and 'trim' in note['dominated']
    assert by['holdback']['feasible'] and by['holdback']['discovered'] and by['holdback']['pareto_optimal']
    assert by['loyalty']['feasible'] and not by['loyalty']['pareto_optimal']
    assert by['operations']['pareto_optimal'] and not by['cfo']['feasible']
    assert by['holdback']['scores']['financial_cost']==23500
    assert by['holdback']['scores']['passenger_impact']==by['loyalty']['scores']['passenger_impact']
    assert 'Search Choice' in desk_brief(ranked,42) and 'dominated' in desk_brief(ranked,42).lower()
    assert desk_brief(ranked,42,'holdback').count('Approved in simulation')==1

def test_evidence_scope_and_no_mutation():
    s=generate();before=deepcopy(s);o=scope_evidence(simulate(s,'operations'))
    assert s==before
    assert all(c['id'] in {e['id'] for e in o['evidence']} for c in o['rationale']['citations'])
    assert o['rationale']['context_applied'][0]['text']==s['unstructured_signals'][0]['text']
    with pytest.raises(ValueError):simulate(s,'remote')
    s.pop('model_version')
    with pytest.raises(ValueError):simulate(s)
