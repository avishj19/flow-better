"""Local decade analysis agent — pack grounding and intent routing."""
import json
import pytest
from backend import analysis_agent as a
from backend import decade_data as pack


DISRUPTIONS = [
    {'airport': 'ORD', 'kind': 'weather', 'label': 'ORD de-icing signal'},
    {'airport': 'PIT', 'kind': 'overnight', 'label': 'overnight PIT slot'},
    {'airport': 'PIT', 'kind': 'crew', 'label': 'C01 duty squeeze'},
]


def test_pack_available():
    assert pack.available()
    cat = pack.catalog()
    assert cat['tables']['otp_year'] == 60
    assert cat['tables']['flaw_days'] == 150


def test_compare_otp_2024():
    ranked = pack.compare_otp(2024)
    assert [r['airport'] for r in ranked][0] == 'PIT'
    assert ranked[-1]['airport'] == 'ORD'


def test_flaw_day_null_delay_rate_safe():
    r = a.respond('Worst storm days at JFK')
    assert r['status'] == 'completed'
    assert '2022-01-29' in r['reply']
    assert '—' in r['reply'] or '100.0%' in r['reply']  # null delay15 on total-cancel days OK


def test_otp_not_hijacked_by_worst():
    r = a.respond('What is the worst OTP airport in 2024?')
    assert r['topic'] == 'otp_rank'
    assert 'ORD' in r['reply']


def test_starters_and_common_desk_asks():
    cases = [
        ('Brief the decade network', 'brief'),
        ('Rank 2024 on-time performance', 'otp_rank'),
        ('Show ORD weather risk', 'weather'),
        ('Worst storm days at JFK', 'storms'),
        ('How did COVID hit enplanements?', 'traffic'),
        ('Map FlowBetter strategies on storm days', 'strategy'),
        ('Context for this scenario’s airports', 'scenario'),
    ]
    for msg, topic in cases:
        r = a.respond(msg, DISRUPTIONS)
        assert r['topic'] == topic, (msg, r['topic'], r['title'])
        assert r['reply']
        assert 'scope' in r


def test_scenario_includes_pillars():
    r = a.respond('Context for this scenario’s airports', DISRUPTIONS)
    assert 'Financial' in r['reply'] or 'financial' in r['reply'].lower()
    assert r['facts']['pillars']['decision_rule']
    assert {h['airport'] for h in r['facts']['touched']} >= {'ORD', 'PIT'}


def test_strategy_mapping_snowzilla():
    mapped = pack.strategy_mapping('JFK', 3)
    assert mapped[0]['pattern'] == pack.PATTERN_SNOWZILLA
    assert mapped[0]['approves'] is False
    assert 'operations' in mapped[0]['strategy_hints']


def test_covid_not_weather_profile():
    r = a.respond('How did COVID hit enplanements at JFK?')
    assert 'demand' in r['reply'].lower() or 'COVID' in r['reply']
    assert '−' in r['reply'] or 'drop' in r['reply'].lower()


def test_live_requires_consent(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    with pytest.raises(ValueError, match='consent'):
        a.run('Rank 2024 on-time performance', mode='live')


def test_live_scripted_must_use_tools():
    def fn(name, args, ident='c1'):
        return {'type': 'function_call', 'name': name, 'arguments': json.dumps(args), 'call_id': ident}

    def message(text):
        return {'type': 'message', 'content': [{'type': 'output_text', 'text': text}]}

    outputs = iter([
        [fn('compare_otp', {'year': 2024})],
        [message('PIT leads 2024 departure OTP at 82.4% among the packed six.')],
    ])

    def caller(items):
        return {'output': next(outputs)}

    r = a.run('Rank 2024', mode='live', consent=True, call_model=caller)
    assert r['status'] == 'completed'
    assert 'PIT' in r['reply']
    assert 'compare_otp' in r['facts']['tools_used']


def test_live_rejects_answer_without_tools():
    r = a.run('Rank 2024', mode='live', consent=True,
              call_model=lambda _: {'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': 'guess'}]}]})
    assert r['status'] == 'failed'
