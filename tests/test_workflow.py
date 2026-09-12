import copy
import json
import pytest
from backend import agent_workflow as w
from backend.simulator import generate

def fn(name,args,ident='call'):
    return {'type':'function_call','name':name,'arguments':json.dumps(args),'call_id':ident}
def message(text):return {'type':'message','content':[{'type':'output_text','text':text}]}
def caller(outputs,captured=None):
    it=iter(outputs)
    def call(items):
        if captured is not None:captured.append(copy.deepcopy(items))
        return {'output':next(it)}
    return call

def test_local():
    saved=[];r=w.run(generate(),1,persist=lambda x:saved.append(copy.deepcopy(x)))
    assert r['status']=='completed' and r['recommendation']=='protect'
    assert len(r['options'])==6 and len(saved)>6
    assert 'No language model ran' in r['explanation']

def test_live_scripted_aggregate_only_and_encrypted_context():
    seen=[]
    encrypted={'type':'reasoning','id':'opaque','encrypted_content':'opaque-ciphertext'}
    r=w.run(generate(),1,'live',True,caller([[encrypted,fn('inspect_scenario',{})],[fn('simulate_recovery',{'plan':'remote'})],[fn('simulate_recovery',{'plan':'combined'})],[message('Location failure [remote:E0302]. Coverage passed [combined:E0001].')]],seen))
    # Exact IDs must be among observed outputs; use actual returned position sample.
    if r['status']=='failed':
        outputs=[json.loads(x['output']) for x in seen[-1] if x.get('type')=='function_call_output']
        eid=next(c['evidence_ids'][0] for o in outputs if o.get('plan')=='remote' for c in o['checks'] if not c['passed'])
        seen=[]
        r=w.run(generate(),1,'live',True,caller([[encrypted,fn('inspect_scenario',{})],[fn('simulate_recovery',{'plan':'remote'})],[fn('simulate_recovery',{'plan':'combined'})],[message(f'Location failure [{eid}]. Coverage passed [combined:E0001].')]],seen))
    assert r['status']=='completed' and r['recommendation']=='combined'
    assert encrypted in seen[1]
    for items in seen:
        for x in items:
            if x.get('type')=='function_call_output':
                output=json.loads(x['output']);assert not isinstance(output.get('flights'),list)
                assert 'RX100' not in x['output'] and 'C01' not in x['output'] and 'passenger_records' not in output

@pytest.mark.parametrize('text',['No citation.','Invented [combined:E9999].','Unobserved [small:E0001].'])
def test_bad_citations_stop(text):
    r=w.run(generate(),1,'live',True,caller([[fn('inspect_scenario',{})],[fn('simulate_recovery',{'plan':'combined'}),fn('simulate_recovery',{'plan':'remote'})],[message(text)]]))
    assert r['status']=='failed' and r['recommendation'] is None

def test_invalid_tool_order_args_duplicate_and_no_model_authority():
    seen=[]
    r=w.run(generate(),1,'live',True,caller([[fn('simulate_recovery',{'plan':'combined'}),fn('shell',{})],[fn('inspect_scenario',{})],[fn('simulate_recovery',{'plan':[]}),fn('simulate_recovery',{'plan':'remote'})],[fn('simulate_recovery',{'plan':'remote'}),fn('simulate_recovery',{'plan':'combined'})],[message('I approve the remote plan. [combined:E0001]')]],seen))
    assert r['status']=='completed' and r['recommendation']=='combined'
    errors=[json.loads(x['output']) for x in seen[-1] if x.get('type')=='function_call_output' and 'error' in json.loads(x['output'])]
    assert len(errors)==4

def test_budget_and_failure_persist():
    saved=[]
    r=w.run(generate(),1,'live',True,caller([[fn('inspect_scenario',{})]*9]),persist=lambda x:saved.append(copy.deepcopy(x)))
    assert r['status']=='failed' and 'budget' in r['error'] and saved[-1]['status']=='failed'
    r=w.run(generate(),1,'live',True,caller([[fn('inspect_scenario',{})]]*6))
    assert r['status']=='failed' and 'turn' in r['error']
    r=w.run(generate(),1,'live',True,lambda _:1/0)
    assert r['status']=='failed' and 'Provider' in r['error']

def test_consent_and_config(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False);monkeypatch.delenv('TRADEOPS_AI_MODEL',raising=False)
    assert not w.config()['live_available']
    with pytest.raises(ValueError):w.run(generate(),1,'live')
    with pytest.raises(ValueError):w.run(generate(),1,'live',True)

def test_provider_contract(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','test-key');monkeypatch.setenv('TRADEOPS_AI_MODEL','configured-model')
    def post(url,headers,json,timeout):
        assert url=='https://api.openai.com/v1/responses'
        assert json['store'] is False and json['parallel_tool_calls'] is False
        assert json['include']==['reasoning.encrypted_content']
        assert len(json['tools'])==2 and timeout==45
        class Response:
            def raise_for_status(self):pass
            def json(self):return {'output':[]}
        return Response()
    monkeypatch.setattr(w.httpx,'post',post)
    assert w.provider([])=={'output':[]}
