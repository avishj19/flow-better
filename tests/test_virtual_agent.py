from backend.simulator import generate, simulate, network_snapshot, HUB
from backend import virtual_agent as va

def test_network_snapshot_overnight_hubs():
    s=generate(42); net=network_snapshot(s)
    assert net['hub']==HUB=='PIT'
    assert set(net['overnight_hubs'])=={'PIT','DTW'}
    assert net['overnight_hubs']['PIT']['count']==10
    assert net['overnight_hubs']['DTW']['tails']==['R01']
    assert net['overnight_disruption']['id']=='D4'
    disrupted=simulate(s)
    viewed=network_snapshot(s, disrupted)
    assert any(p['out_of_position'] for p in viewed['overnight_positions'])

def test_virtual_agent_overnight_and_strategies():
    baseline=simulate(generate(42), disrupted=False)
    run={'name':'PIT overnight hub · seed 42','seed':42,'phase':'baseline','revision':0,
         'scenario':generate(42),'baseline':baseline,'current':baseline,'experiments':[]}
    overnight=va.respond(run,'Brief the overnight hubs')
    assert overnight['topic']=='overnight_hub' and 'PIT' in overnight['highlights'] and 'DTW' in overnight['reply']
    network=va.respond(run,'Show me the flight network')
    assert network['topic']=='network' and set(network['highlights']) >= {'PIT','BOS'}
    t01=va.respond(run,'What about T01 overnight?')
    assert t01['topic']=='overnight_tail' and 'T01' in t01['reply']
    ops=va.respond(run,'How does Operations protect overnight?')
    assert ops['topic']=='strategy_operations' and 'ORD' in ops['highlights']
    loyalty=va.respond(run,'Show me the Loyalty ferry path')
    assert loyalty['topic']=='strategy_loyalty' and 'DTW' in loyalty['highlights']
    assert 'Brief the overnight hubs' in va.starter_prompts()
