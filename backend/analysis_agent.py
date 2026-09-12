"""On-demand decade analysis agent grounded in bundled BTS/FAA/NOAA packs.

Local mode answers from deterministic queries (no LLM). Optional live mode exposes
the same query tools to a bounded OpenAI Responses planner with explicit consent.
"""
from __future__ import annotations
import json
import os
import re
import uuid
from datetime import datetime, timezone
import httpx
from . import decade_data as pack

AIRPORT_RE = re.compile(r'\b(PIT|BOS|JFK|DCA|ORD|DTW)\b', re.I)
YEAR_RE = re.compile(r'\b(20(?:1[6-9]|2[0-5]))\b')

TOOLS = [
    {'type': 'function', 'name': 'list_catalog',
     'description': 'List decade pack tables, airports, years, and source labels.',
     'parameters': {'type': 'object', 'properties': {}, 'required': [], 'additionalProperties': False}, 'strict': True},
    {'type': 'function', 'name': 'compare_otp',
     'description': 'Rank the six airports by departure on-time % for one year.',
     'parameters': {'type': 'object', 'properties': {
         'year': {'type': 'integer', 'minimum': 2016, 'maximum': 2025}},
         'required': ['year'], 'additionalProperties': False}, 'strict': True},
    {'type': 'function', 'name': 'airport_otp_year',
     'description': 'Annual OTP, cancel, delay-cause and enplanement row(s).',
     'parameters': {'type': 'object', 'properties': {
         'airport': {'type': 'string', 'enum': list(pack.AIRPORTS)},
         'year': {'type': 'integer', 'minimum': 2016, 'maximum': 2025}},
         'required': ['airport'], 'additionalProperties': False}, 'strict': True},
    {'type': 'function', 'name': 'airport_weather_year',
     'description': 'NOAA GHCND annual weather metrics for an airport year.',
     'parameters': {'type': 'object', 'properties': {
         'airport': {'type': 'string', 'enum': list(pack.AIRPORTS)},
         'year': {'type': 'integer', 'minimum': 2016, 'maximum': 2025}},
         'required': ['airport'], 'additionalProperties': False}, 'strict': True},
    {'type': 'function', 'name': 'weather_risk',
     'description': 'Rank the six airports by packed NOAA hazard cues (snow/thunder/fog/wind) for one year.',
     'parameters': {'type': 'object', 'properties': {
         'year': {'type': 'integer', 'minimum': 2016, 'maximum': 2025}},
         'required': ['year'], 'additionalProperties': False}, 'strict': True},
    {'type': 'function', 'name': 'flaw_days',
     'description': 'Top historical disruption days from the BTS sample pack, with optional storm filter.',
     'parameters': {'type': 'object', 'properties': {
         'airport': {'type': 'string', 'enum': list(pack.AIRPORTS)},
         'limit': {'type': 'integer', 'minimum': 1, 'maximum': 20},
         'weather_only': {'type': 'boolean'}},
         'required': [], 'additionalProperties': False}, 'strict': True},
    {'type': 'function', 'name': 'strategy_mapping',
     'description': 'Map top packed flaw days to CFO/Loyalty/Operations teaching hints (never approvals).',
     'parameters': {'type': 'object', 'properties': {
         'airport': {'type': 'string', 'enum': list(pack.AIRPORTS)},
         'limit': {'type': 'integer', 'minimum': 1, 'maximum': 10}},
         'required': [], 'additionalProperties': False}, 'strict': True},
    {'type': 'function', 'name': 'enplanements',
     'description': 'FAA commercial-service enplanements for an airport.',
     'parameters': {'type': 'object', 'properties': {
         'airport': {'type': 'string', 'enum': list(pack.AIRPORTS)},
         'year': {'type': 'integer', 'minimum': 2016, 'maximum': 2025}},
         'required': ['airport'], 'additionalProperties': False}, 'strict': True},
    {'type': 'function', 'name': 'scenario_history_context',
     'description': 'Map current synthetic scenario disruption airports to decade context and four-pillar desk implications.',
     'parameters': {'type': 'object', 'properties': {}, 'required': [], 'additionalProperties': False}, 'strict': True},
]

SYSTEM = (
    'You analyze FlowBetter’s bundled decade airport pack (BTS OTP, FAA enplanements, NOAA weather, flaw days). '
    'Use tools before answering. Cite concrete numbers from tool results only — never invent flights, METAR, or carrier actions. '
    'When scenario disruptions exist, connect decade facts to the four independent pillars '
    '(financial, passenger, network, crew) and the three strategies (CFO absorb, Loyalty ferry+reserve, Operations cancel-bank). '
    'Human chooses among feasible Pareto options; never approve a plan or invent a weighted winner. '
    'Label COVID-year OTP as traffic collapse, not reliability excellence. '
    'Scope is teaching context for the six-airport sandbox, not operational advice.'
)


def config():
    return {
        'available': pack.available(),
        'live_available': bool(os.getenv('OPENAI_API_KEY') and os.getenv('TRADEOPS_AI_MODEL')),
        'model': os.getenv('TRADEOPS_AI_MODEL', ''),
        'airports': list(pack.AIRPORTS),
        'years': [2016, 2025],
        'max_model_turns': 6,
        'max_tool_calls': 10,
        'raw_records_sent': False,
        'scope': pack.SCOPE,
    }


def starter_prompts():
    return [
        'Brief the decade network',
        'Rank 2024 on-time performance',
        'Show ORD weather risk',
        'Worst storm days at JFK',
        'How did COVID hit enplanements?',
        'Map FlowBetter strategies on storm days',
        'Context for this scenario’s airports',
    ]


def _pack(topic, title, reply, highlights, facts, suggested=None):
    return {
        'id': uuid.uuid4().hex,
        'created': datetime.now(timezone.utc).isoformat(),
        'mode': 'local',
        'status': 'completed',
        'topic': topic,
        'title': title,
        'reply': reply,
        'highlights': highlights,
        'facts': facts,
        'citations': [],
        'trace': [{'role': 'LocalAnalyst', 'action': topic, 'data': {'highlights': highlights}}],
        'suggested': suggested or starter_prompts(),
        'scope': pack.SCOPE,
    }


def _pct(v):
    return '—' if v is None else f'{float(v):.1f}%'


def _rate_pct(v):
    """Format a 0–1 rate from the pack as a percent string."""
    return '—' if v is None else f'{100 * float(v):.1f}%'


def _num(v):
    if v is None:
        return '—'
    n = float(v)
    if abs(n - round(n)) < 1e-9:
        return f'{int(round(n)):,}'
    return f'{n:,.1f}'


def _inches(v):
    return '—' if v is None else f'{float(v):.1f}'


def brief_network():
    ranked = pack.compare_otp(2024)
    top = ranked[0] if ranked else None
    bottom = ranked[-1] if ranked else None
    flaws = pack.flaw_days(limit=3)
    risk = pack.weather_risk(2022)
    reply = (
        f"Bundled decade pack covers {', '.join(pack.AIRPORTS)} for 2016–2025 (BTS/FAA/NOAA). "
        f"In 2024 departure OTP, {top['airport']} leads at {_pct(top['dep_ontime_pct'])} while "
        f"{bottom['airport']} sits at {_pct(bottom['dep_ontime_pct'])}. "
        f"2022 weather-risk cue tops at {risk[0]['airport']} "
        f"(snow {_inches(risk[0]['total_snowfall_in'])} in · thunder {_num(risk[0]['thunder_days_WT03'])} days). "
        f"Sample flaw-day pressure includes {flaws[0]['airport']} on {flaws[0]['date']} "
        f"({_rate_pct(flaws[0]['dep_cancel_rate'])} departures cancelled). "
        'Ask for OTP ranks, weather risk, storm days, COVID traffic, strategy mapping, or scenario context — '
        'answers cite the pack only.'
    )
    return _pack('brief', 'Decade network briefing', reply,
                 [r['airport'] for r in ranked[:3]],
                 {'otp_2024': ranked, 'weather_risk_2022': risk[:3], 'sample_flaw_days': flaws},
                 starter_prompts())


def brief_otp(year=2024, airport=None):
    year = int(year)
    if airport:
        rows = pack.otp_year(airport, year)
        if not rows:
            return _pack('otp', f'No OTP row for {airport} {year}',
                         f'No packed OTP row for {airport} in {year}.', [airport], {})
        r = rows[0]
        reply = (
            f"{airport} {year}: departure OTP {_pct(r.get('dep_ontime_pct'))}, "
            f"arrival OTP {_pct(r.get('arr_ontime_pct'))}, cancel {_pct(r.get('dep_cancelled_pct'))}. "
            f"Delay-cause shares — late aircraft {_pct(r.get('origin_cause_late_aircraft_share_pct'))}, "
            f"weather {_pct(r.get('origin_cause_weather_share_pct'))}, NAS {_pct(r.get('origin_cause_nas_share_pct'))}. "
            f"FAA enplanements {_num(r.get('enplanements'))}."
        )
        if year == 2020:
            reply += ' 2020 OTP looks strong mainly because traffic collapsed, not because the NAS got easier.'
        return _pack('otp', f'{airport} OTP {year}', reply, [airport], {'row': r})
    ranked = pack.compare_otp(year)
    lines = [f"{i+1}. {r['airport']} dep {_pct(r['dep_ontime_pct'])} · arr {_pct(r['arr_ontime_pct'])}"
             for i, r in enumerate(ranked)]
    reply = f"{year} departure on-time ranking for the FlowBetter six:\n" + '\n'.join(lines)
    if year == 2020:
        reply += '\nNote: treat 2020 as a demand-shock year, not a reliability crown.'
    elif ranked:
        reply += (
            f"\nRead: {ranked[0]['airport']} is the cleanest departure mark that year; "
            f"{ranked[-1]['airport']} is the fragile end of this set. Late-aircraft usually dominates annual cause share."
        )
    return _pack('otp_rank', f'{year} OTP ranking', reply,
                 [r['airport'] for r in ranked], {'ranked': ranked})


def brief_weather(airport=None, year=2022, compare=False):
    year = int(year)
    if compare or airport is None:
        ranked = pack.weather_risk(year)
        lines = [
            f"{i+1}. {r['airport']}: snow {_inches(r['total_snowfall_in'])} in · "
            f"thunder {_num(r['thunder_days_WT03'])} · fog {_num(r['fog_days_WT01'])} · "
            f"heavy fog {_num(r['heavy_fog_days_WT02'])} · wind≥40 {_num(r['extreme_wind_days_WSF2_ge_40mph'])}"
            for i, r in enumerate(ranked)
        ]
        reply = (
            f"{year} NOAA hazard cues across the FlowBetter six (teaching risk order, not a forecast):\n"
            + '\n'.join(lines)
            + '.\nHierarchy cue from the decade brief: thunder → ORD/PIT/DCA; snow depth → BOS/PIT/DTW/ORD; '
            'heavy fog episodes → JFK; wind days → JFK often leads.'
        )
        highlights = [r['airport'] for r in ranked[:3]]
        if airport:
            highlights = [airport] + [a for a in highlights if a != airport]
        return _pack('weather_risk', f'{year} weather risk ranking', reply, highlights,
                     {'ranked': ranked},
                     ['Show ORD weather risk', 'Worst storm days at JFK', 'Rank 2024 on-time performance'])
    airport = airport.upper()
    rows = pack.weather_year(airport, year)
    if not rows:
        return _pack('weather', f'No weather row for {airport} {year}',
                     f'No NOAA annual row for {airport} {year}.', [airport], {})
    r = rows[0]
    station = pack.station_for(airport)
    ranked = pack.weather_risk(year)
    place = next((i + 1 for i, x in enumerate(ranked) if x['airport'] == airport), None)
    reply = (
        f"{airport} {year} (station {station['station_id'] if station else '—'}): "
        f"snowfall {_inches(r.get('total_snowfall_in'))} in, thunder days {_num(r.get('thunder_days_WT03'))}, "
        f"fog days {_num(r.get('fog_days_WT01'))}, heavy fog {_num(r.get('heavy_fog_days_WT02'))}, "
        f"heavy precip days {_num(r.get('heavy_precip_days_ge_1in'))}, "
        f"extreme wind (≥40 mph) {_num(r.get('extreme_wind_days_WSF2_ge_40mph'))}."
    )
    if place:
        reply += f" Among the six, that ranks #{place} on the {year} packed hazard cue."
    reply += ' Use as desk context for holds — not a live METAR or closure call.'
    return _pack('weather', f'{airport} weather {year}', reply, [airport],
                 {'row': r, 'station': station, 'risk_rank': place, 'risk_table': ranked})


def brief_storms(airport=None, limit=8, weather_only=False):
    rows = pack.flaw_days(airport, limit, weather_only=weather_only)
    if not rows:
        return _pack('storms', 'No flaw days', 'No packed flaw days matched that filter.',
                     [airport] if airport else list(pack.AIRPORTS), {})
    bits = []
    mappings = []
    for r in rows:
        mapped = pack.classify_flaw_day(r)
        mappings.append({'date': r['date'], 'airport': r['airport'], **mapped})
        bits.append(
            f"{r['date']} {r['airport']}: cancel {_rate_pct(r.get('dep_cancel_rate'))}, "
            f"delay≥15 {_rate_pct(r.get('dep_delay15_rate'))}, weather delay min {_num(r.get('weather_delay_min'))}, "
            f"late-aircraft min {_num(r.get('late_aircraft_delay_min'))}"
            f" · pattern {mapped['pattern']}"
        )
    reply = (
        'Highest-scoring disruption days in the BTS sample pack'
        + (f' for {airport}' if airport else '')
        + (' (weather-linked filter)' if weather_only else '')
        + ':\n' + '\n'.join(bits)
    )
    # Lead with the top day's strategy teaching, grounded in pack classification.
    top = mappings[0]
    reply += (
        f"\nFlowBetter desk read on {rows[0]['date']} {rows[0]['airport']} ({top['pattern']}): {top['desk_read']} "
        f"CFO — {top['strategy_hints']['cfo']} Loyalty — {top['strategy_hints']['loyalty']} "
        f"Operations — {top['strategy_hints']['operations']} "
        'These are teaching hints from packed history, not approvals.'
    )
    return _pack('storms', 'Historical flaw days', reply,
                 sorted({r['airport'] for r in rows}),
                 {'flaw_days': rows, 'strategy_mapping': mappings},
                 ['Map FlowBetter strategies on storm days', 'Rank 2024 on-time performance',
                  'Context for this scenario’s airports'])


def brief_strategy(airport=None, limit=5):
    rows = pack.strategy_mapping(airport, limit)
    if not rows:
        return _pack('strategy', 'No mapping rows', 'No packed flaw days to map.',
                     [airport] if airport else list(pack.AIRPORTS), {})
    lines = []
    for r in rows:
        lines.append(
            f"{r['date']} {r['airport']} ({r['pattern']}, cancel {_rate_pct(r.get('dep_cancel_rate'))}): "
            f"{r['desk_read']}"
        )
    reply = (
        'FlowBetter strategy mapping on packed storm/flaw days '
        '(CFO absorb · Loyalty ferry+reserve · Operations cancel-bank). '
        'Four pillars stay independent — human chooses; agent never approves.\n'
        + '\n'.join(lines)
        + '\nHard finding: on Snowzilla-scale cancel days, absorb and ferry-first are illegal under the model’s own crew rules; '
        'cancel-first Operations is the feasible teaching path, with passenger impact correctly exploding.'
    )
    return _pack('strategy', 'Storm days ↔ FlowBetter strategies', reply,
                 sorted({r['airport'] for r in rows}), {'mapped': rows},
                 ['Worst storm days at JFK', 'Context for this scenario’s airports', 'Rank 2024 on-time performance'])


def brief_traffic(airport=None):
    if airport:
        rows = pack.enplanements(airport)
        y2019 = next((r for r in rows if int(r['year']) == 2019), None)
        y2020 = next((r for r in rows if int(r['year']) == 2020), None)
        y2024 = next((r for r in rows if int(r['year']) == 2024), None)
        drop = None
        if y2019 and y2020 and y2019.get('enplanements'):
            drop = 100 * (1 - y2020['enplanements'] / y2019['enplanements'])
        reply = (
            f"{airport} enplanements: 2019 {_num(y2019 and y2019.get('enplanements'))}, "
            f"2020 {_num(y2020 and y2020.get('enplanements'))}"
            + (f' (−{drop:.0f}% YoY)' if drop is not None else '')
            + f", 2024 {_num(y2024 and y2024.get('enplanements'))}. "
            'COVID is a demand/schedule shock, not a weather profile — do not train it as Snowzilla.'
        )
        return _pack('traffic', f'{airport} traffic', reply, [airport], {'rows': rows})
    snaps = []
    for ap in pack.AIRPORTS:
        rows = pack.enplanements(ap)
        y2019 = next((r for r in rows if int(r['year']) == 2019), None)
        y2020 = next((r for r in rows if int(r['year']) == 2020), None)
        if y2019 and y2020 and y2019.get('enplanements'):
            snaps.append((ap, 100 * (1 - y2020['enplanements'] / y2019['enplanements'])))
    snaps.sort(key=lambda x: -x[1])
    reply = (
        'COVID enplanement drops (2019→2020): '
        + '; '.join(f'{ap} −{drop:.0f}%' for ap, drop in snaps)
        + '. CPE roughly doubles in authority reports when fixed airfield cost meets collapsed traffic — '
        'financial-pillar teaching, not a live cost quote.'
    )
    return _pack('traffic', 'COVID traffic shock', reply, [ap for ap, _ in snaps[:3]],
                 {'drops': [{'airport': ap, 'drop_pct': round(drop, 1)} for ap, drop in snaps]})


def brief_scenario(disruptions):
    ctx = pack.scenario_context(disruptions)
    if not ctx['touched']:
        return _pack('scenario', 'No airport-linked disruptions yet',
                     'This scenario has no airport-tagged disruptions to map. Inject disruptions or ask a decade OTP/weather question.',
                     ['PIT'], ctx, starter_prompts())
    lines = []
    highlights = []
    for hit in ctx['touched']:
        highlights.append(hit['airport'])
        otp = hit.get('otp_2024') or {}
        wx = hit.get('weather_2022') or {}
        flaw = (hit.get('recent_flaw_days') or [{}])[0]
        hint = (hit.get('strategy_hints') or [{}])[0]
        lines.append(
            f"{hit['airport']} ({hit.get('disruption_kind')} — {hit.get('disruption_label')}): "
            f"2024 dep OTP {_pct(otp.get('dep_ontime_pct'))}; "
            f"2022 snow {_inches(wx.get('total_snowfall_in'))} in / thunder {_num(wx.get('thunder_days_WT03'))}; "
            f"sample flaw day {flaw.get('date', '—')} cancel {_rate_pct(flaw.get('dep_cancel_rate'))}"
            + (f" · teaching pattern {hint.get('pattern')}" if hint.get('pattern') else '')
            + '.'
        )
    pillars = ctx.get('pillars') or {}
    reply = 'Historical context for airports touched by the current synthetic day:\n' + '\n'.join(lines)
    if pillars.get('implications'):
        reply += '\nFour-pillar desk implications (context only — no approval):'
        for note in pillars['implications']:
            reply += f"\n· {note['pillar'].title()}: {note['read']}"
        reply += f"\n{pillars.get('decision_rule', '')}"
    reply += ' Decade facts do not change the simulator until you project live weather or choose a recovery plan.'
    return _pack('scenario', 'Scenario ↔ decade context', reply, highlights, ctx,
                 ['Map FlowBetter strategies on storm days', 'Compare recovery strategies',
                  'Rank 2024 on-time performance'])


def _wants_otp(low: str) -> bool:
    return any(k in low for k in (
        'otp', 'on-time', 'on time', 'ontime', 'rank', 'reliab', 'compare', 'delay cause', 'punctual',
    ))


def _wants_storm(low: str) -> bool:
    return any(k in low for k in (
        'storm', 'flaw', 'cancel day', 'snowzilla', 'nor’easter', "nor'easter", 'nor easter',
        'disruption day', 'worst day', 'worst days',
    )) or (any(k in low for k in ('worst', 'bad day', 'meltdown')) and not _wants_otp(low))


def _wants_weather(low: str) -> bool:
    return any(k in low for k in (
        'weather', 'snow', 'thunder', 'fog', 'wind', 'precip', 'hazard', 'climate', 'wx ',
        'weather risk',
    )) or ('risk' in low and any(k in low for k in ('weather', 'snow', 'storm', 'wx', 'hazard')))


def _wants_strategy(low: str) -> bool:
    return any(k in low for k in (
        'strategy', 'strategies', 'cfo', 'loyalty', 'operations choice', 'flowbetter',
        'ferry', 'cancel bank', 'cancel-bank', 'absorb', 'pillar', 'four pillar', '4 pillar',
        'how would flow', 'map flow',
    ))


def _wants_traffic(low: str) -> bool:
    return any(k in low for k in (
        'covid', 'enplane', 'traffic', 'demand shock', 'demand-shock', 'pax volume', 'passenger volume',
    ))


def _wants_scenario(low: str) -> bool:
    return any(k in low for k in (
        'scenario', 'this day', 'current disruption', 'context for this', 'this desk', 'touched airport',
    ))


def respond(message: str, disruptions=None):
    if not pack.available():
        raise ValueError('Decade analysis pack is not installed on this server')
    text = (message or '').strip()
    if not text or len(text) > 500:
        raise ValueError('Ask a concrete decade question (max 500 characters)')
    airports = [a.upper() for a in AIRPORT_RE.findall(text)]
    years = [int(y) for y in YEAR_RE.findall(text)]
    year = years[0] if years else None
    airport = airports[0] if airports else None
    low = text.lower()

    if _wants_scenario(low):
        return brief_scenario(disruptions)
    if _wants_strategy(low) and not _wants_otp(low):
        # Strategy asks that also mention storms stay on strategy mapping.
        return brief_strategy(airport)
    if _wants_traffic(low):
        return brief_traffic(airport)
    if _wants_storm(low) and not _wants_otp(low):
        weather_only = any(k in low for k in (
            'storm', 'snow', 'weather', "nor'easter", 'nor’easter', 'snowzilla',
        ))
        return brief_storms(airport, weather_only=weather_only)
    if _wants_weather(low):
        compare = airport is None or any(k in low for k in ('risk', 'rank', 'compare', 'across', 'network'))
        # "Show ORD weather risk" → single-airport detail with rank cue; bare "weather risk" → compare.
        if airport and 'risk' in low and not any(k in low for k in ('compare', 'across', 'all six', 'rank the')):
            return brief_weather(airport, year or 2022, compare=False)
        return brief_weather(airport, year or 2022, compare=compare or airport is None)
    if _wants_otp(low):
        return brief_otp(year or 2024, airport)
    if airport and any(k in low for k in ('show', 'brief', 'about', 'how is', 'what about', 'tell me')):
        otp = brief_otp(year or 2024, airport)
        wx = pack.weather_year(airport, 2022)
        if wx:
            otp['reply'] += (
                f" Weather cue (2022): snow {_inches(wx[0].get('total_snowfall_in'))} in, "
                f"thunder {_num(wx[0].get('thunder_days_WT03'))} days."
            )
            otp['facts']['weather_2022'] = wx[0]
        # If the desk already has disruptions on this airport, attach a short pillar cue.
        if disruptions and any(d.get('airport') == airport for d in disruptions):
            pillars = pack.pillar_implications([d for d in disruptions if d.get('airport') == airport])
            if pillars['implications']:
                otp['reply'] += ' Scenario cue: ' + pillars['implications'][0]['read']
                otp['facts']['pillars'] = pillars
        return otp
    if any(k in low for k in ('brief', 'overview', 'decade', 'network', 'help', 'what can', 'status')):
        return brief_network()
    # Default: if disruptions exist, prefer scenario grounding; else network brief.
    if disruptions:
        return brief_scenario(disruptions)
    return brief_network()


def _tool(name, args, disruptions):
    if name == 'list_catalog' and args == {}:
        return pack.catalog()
    if name == 'compare_otp' and set(args) == {'year'}:
        return {'ranked': pack.compare_otp(args['year'])}
    if name == 'airport_otp_year' and 'airport' in args and set(args) <= {'airport', 'year'}:
        return {'rows': pack.otp_year(args['airport'], args.get('year'))}
    if name == 'airport_weather_year' and 'airport' in args and set(args) <= {'airport', 'year'}:
        return {'rows': pack.weather_year(args['airport'], args.get('year'))}
    if name == 'weather_risk' and set(args) == {'year'}:
        return {'ranked': pack.weather_risk(args['year'])}
    if name == 'flaw_days' and set(args) <= {'airport', 'limit', 'weather_only'}:
        return {'rows': pack.flaw_days(args.get('airport'), args.get('limit', 10),
                                       weather_only=bool(args.get('weather_only', False)))}
    if name == 'strategy_mapping' and set(args) <= {'airport', 'limit'}:
        return {'rows': pack.strategy_mapping(args.get('airport'), args.get('limit', 5))}
    if name == 'enplanements' and 'airport' in args and set(args) <= {'airport', 'year'}:
        return {'rows': pack.enplanements(args['airport'], args.get('year'))}
    if name == 'scenario_history_context' and args == {}:
        return pack.scenario_context(disruptions)
    return {'error': 'Unknown tool or invalid arguments'}


def provider(items):
    r = httpx.post(
        'https://api.openai.com/v1/responses',
        headers={'Authorization': 'Bearer ' + os.environ['OPENAI_API_KEY']},
        json={
            'model': os.environ['TRADEOPS_AI_MODEL'],
            'instructions': SYSTEM,
            'input': items,
            'tools': TOOLS,
            'parallel_tool_calls': False,
            'max_output_tokens': 1600,
            'store': False,
            'include': ['reasoning.encrypted_content'],
        },
        timeout=45,
    )
    r.raise_for_status()
    return r.json()


def run(message: str, disruptions=None, mode='local', consent=False, call_model=None):
    if mode not in ('local', 'live'):
        raise ValueError('Unknown mode')
    if mode == 'local':
        return respond(message, disruptions)
    if not consent:
        raise ValueError('Explicit consent required for aggregate decade metrics sent to OpenAI')
    if not call_model and not config()['live_available']:
        raise ValueError('Set OPENAI_API_KEY and TRADEOPS_AI_MODEL on the server')
    if not pack.available():
        raise ValueError('Decade analysis pack is not installed on this server')
    text = (message or '').strip()
    if not text or len(text) > 500:
        raise ValueError('Ask a concrete decade question (max 500 characters)')

    report = {
        'id': uuid.uuid4().hex,
        'created': datetime.now(timezone.utc).isoformat(),
        'mode': 'live',
        'status': 'running',
        'topic': 'live_analysis',
        'title': 'Live decade analysis',
        'reply': '',
        'highlights': [],
        'facts': {},
        'citations': [],
        'trace': [],
        'suggested': starter_prompts(),
        'scope': pack.SCOPE,
    }
    observed = set()

    def event(role, action, data):
        report['trace'].append({'role': role, 'action': action, 'data': data})

    try:
        event('Planner', 'started', {'mode': 'live', 'label': 'OpenAI decade tool planner'})
        items = [{'role': 'user', 'content': text}]
        calls = 0
        used = False
        for _turn in range(6):
            output = (call_model or provider)(items).get('output', [])
            items.extend(output)
            fns = [x for x in output if x.get('type') == 'function_call']
            if not fns:
                prose = '\n'.join(
                    p.get('text', '') for x in output if x.get('type') == 'message'
                    for p in x.get('content', []) if p.get('type') == 'output_text'
                )[:8000]
                if not used:
                    raise ValueError('Planner must query the decade pack before answering')
                if not prose.strip():
                    raise ValueError('Empty model answer')
                report['reply'] = prose
                report['highlights'] = sorted({a.upper() for a in AIRPORT_RE.findall(prose)})
                report['status'] = 'completed'
                event('Supervisor', 'answered', {'tools_used': calls})
                break
            for fn in fns:
                calls += 1
                if calls > 10:
                    raise ValueError('Tool-call budget reached')
                try:
                    args = json.loads(fn.get('arguments', '{}'))
                    result = _tool(fn.get('name'), args, disruptions) if isinstance(args, dict) else {'error': 'Arguments must be an object'}
                except (json.JSONDecodeError, TypeError, ValueError) as exc:
                    result = {'error': str(exc) if isinstance(exc, ValueError) else 'Invalid arguments'}
                if 'error' not in result:
                    used = True
                    observed.add(fn.get('name'))
                event('Planner', 'requested_tool', {'name': fn.get('name')})
                event('Tool', fn.get('name'), {'ok': 'error' not in result, 'keys': sorted(result)})
                items.append({'type': 'function_call_output', 'call_id': fn['call_id'], 'output': json.dumps(result)})
        else:
            raise ValueError('Model-turn budget reached')
        report['facts'] = {'tools_used': sorted(observed)}
    except Exception as exc:
        report['status'] = 'failed'
        report['reply'] = ''
        report['error'] = str(exc) if isinstance(exc, ValueError) else 'Provider or execution failed; check configuration and connectivity.'
        event('Supervisor', 'stopped', report['error'])
    return report
