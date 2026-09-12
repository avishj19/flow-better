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

def steps(text):
    return [[fn('inspect_scenario',{})],[fn('simulate_recovery',{'plan':p},p) for p in ('cfo','loyalty','operations')],[message(text)]]

def test_local():
    saved=[];r=w.run(generate(),1,persist=lambda x:saved.append(copy.deepcopy(x)))
    assert r['status']=='completed' and r['recommendation'] is None
    assert r['feasible_plans']==['loyalty','operations','holdback']
    assert [o['plan'] for o in r['options']]==['cfo','loyalty','operations','holdback']
    assert r['search']['surfaced']==['holdback'] and 'trim' in r['search']['dominated']
    assert r['brief'] and 'no hidden score' in r['brief'].lower()
    assert 'No language model ran' in r['explanation'] and saved[-1]['status']=='completed'

def test_live_scripted_aggregate_only_and_encrypted_context():
    seen=[];encrypted={'type':'reasoning','id':'opaque','encrypted_content':'opaque-ciphertext'}
    outputs=steps('Coverage checked [loyalty:E0001]. Human selects the trade-off.');outputs[0].insert(0,encrypted)
    r=w.run(generate(),1,'live',True,caller(outputs,seen))
    assert r['status']=='completed' and r['recommendation'] is None
    assert encrypted in seen[1]
    for items in seen:
        for x in items:
            if x.get('type')=='function_call_output':
                output=json.loads(x['output']);assert not isinstance(output.get('flights'),list)
                assert 'RX100' not in x['output'] and 'C01' not in x['output']
                if 'plan' in output:assert set(output['scores'])=={'financial_cost','passenger_impact','network_health','crew_buffer'}

@pytest.mark.parametrize('text',['No citation.','Invented [loyalty:E9999].','Unobserved [remote:E0001].'])
def test_bad_citations_stop(text):
    r=w.run(generate(),1,'live',True,caller(steps(text)))
    assert r['status']=='failed' and r['recommendation'] is None

def test_invalid_tools_do_not_give_model_authority():
    outputs=[[fn('simulate_recovery',{'plan':'cfo'}),fn('shell',{})],[fn('inspect_scenario',{})],[fn('simulate_recovery',{'plan':[]})],[fn('simulate_recovery',{'plan':p},p) for p in ('cfo','loyalty','operations')],[fn('simulate_recovery',{'plan':'loyalty'})],[message('I approve CFO. [loyalty:E0001]')]]
    seen=[];r=w.run(generate(),1,'live',True,caller(outputs,seen))
    assert r['status']=='completed' and not r['options'][0]['feasible'] and r['recommendation'] is None
    errors=[json.loads(x['output']) for x in seen[-1] if x.get('type')=='function_call_output' and 'error' in json.loads(x['output'])]
    assert len(errors)==4

def test_must_evaluate_three():
    r=w.run(generate(),1,'live',True,caller([[fn('inspect_scenario',{})],[fn('simulate_recovery',{'plan':'loyalty'})],[message('[loyalty:E0001]')]]))
    assert r['status']=='failed'

def test_budget_and_failure_persist():
    saved=[];r=w.run(generate(),1,'live',True,caller([[fn('inspect_scenario',{})]*9]),persist=lambda x:saved.append(copy.deepcopy(x)))
    assert r['status']=='failed' and 'budget' in r['error'] and saved[-1]['status']=='failed'
    r=w.run(generate(),1,'live',True,caller([[fn('inspect_scenario',{})]]*6))
    assert r['status']=='failed' and 'turn' in r['error']
    r=w.run(generate(),1,'live',True,lambda _:1/0)
    assert r['status']=='failed' and 'Provider' in r['error']

def test_consent_and_config(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False);monkeypatch.delenv('TRADEOPS_AI_MODEL',raising=False)
    with pytest.raises(ValueError):w.run(generate(),1,'live')
    with pytest.raises(ValueError):w.run(generate(),1,'live',True)

def test_provider_contract(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','test-key');monkeypatch.setenv('TRADEOPS_AI_MODEL','configured-model')
    def post(url,headers,json,timeout):
        assert url=='https://api.openai.com/v1/responses'
        assert json['store'] is False and json['parallel_tool_calls'] is False
        assert json['include']==['reasoning.encrypted_content']
        assert json['tools'][1]['parameters']['properties']['plan']['enum']==['cfo','loyalty','operations']
        class Response:
            def raise_for_status(self):pass
            def json(self):return {'output':[]}
        return Response()
    monkeypatch.setattr(w.httpx,'post',post);assert w.provider([])=={'output':[]}
