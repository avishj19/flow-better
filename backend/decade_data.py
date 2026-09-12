"""On-disk decade pack for FlowBetter's six airports (official public sources)."""
from __future__ import annotations
import csv
from functools import lru_cache
from pathlib import Path

PACK = Path(__file__).resolve().parent / 'decade_pack'
AIRPORTS = ('PIT', 'BOS', 'JFK', 'DCA', 'ORD', 'DTW')
SCOPE = (
    'Official public BTS / FAA / NOAA aggregates for PIT,BOS,JFK,DCA,ORD,DTW · '
    '2016–2025 · teaching context only · not a live airline feed'
)

# Desk teaching labels — derived from pack patterns, not live SOC advice.
PATTERN_SNOWZILLA = 'snowzilla_scale'
PATTERN_ORD_WINTER = 'ord_winter_cascade'
PATTERN_COVID_DEMAND = 'covid_demand_shock'
PATTERN_WEATHER_STORM = 'weather_storm'
PATTERN_GENERIC = 'generic_disruption'

FILES = {
    'otp_year': 'bts_airport_year_enriched.csv',
    'weather_year': 'noaa_ghcn_airport_year_2016-2025.csv',
    'flaw_days': 'major_flaw_days.csv',
    'enplanements': 'faa_enplanements.csv',
    'daily': 'bts_daily_airport_metrics.csv',
    'stations': 'noaa_station_crosswalk.csv',
}


def _path(key: str) -> Path:
    p = PACK / FILES[key]
    if not p.is_file():
        raise FileNotFoundError(f'Decade pack missing {p.name}')
    return p


def _num(v):
    if v is None or v == '':
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v
    s = str(v).strip()
    low = s.lower()
    if low in ('true', 'false'):
        return low == 'true'
    try:
        if s.isdigit() or (s.startswith('-') and s[1:].isdigit()):
            return int(s)
        return float(s)
    except ValueError:
        return s


@lru_cache(maxsize=8)
def _rows(key: str):
    keep = {'airport', 'date', 'station_id', 'station_name', 'source', 'source_url',
            'source_file', 'hub', 'status', 'suggested_station_id', 'verified_station_id',
            'first_date', 'last_date'}
    with _path(key).open(newline='', encoding='utf-8') as f:
        return tuple(
            {k: v if k in keep else _num(v) for k, v in row.items()}
            for row in csv.DictReader(f)
        )


def available() -> bool:
    return PACK.is_dir() and all((PACK / name).is_file() for name in FILES.values())


def catalog():
    counts = {k: len(_rows(k)) for k in FILES}
    return {
        'airports': list(AIRPORTS),
        'years': list(range(2016, 2026)),
        'tables': counts,
        'sources': {
            'otp_year': 'BTS PREZIP reporting-carrier annual OTP + FAA enplanements join',
            'weather_year': 'NOAA GHCND airport-station annual weather',
            'flaw_days': 'Top BTS sample disruption days by cancel/delay score',
            'enplanements': 'FAA commercial-service enplanements CY2016–2025',
            'daily': 'BTS PREZIP sample airport-days used for flaw mining',
            'stations': 'Airport ↔ NOAA station crosswalk',
        },
        'scope': SCOPE,
        'pack_dir': str(PACK),
    }


def _airport(code: str | None):
    if code is None:
        return None
    code = str(code).upper()
    if code not in AIRPORTS:
        raise ValueError(f'Airport must be one of {", ".join(AIRPORTS)}')
    return code


def otp_year(airport: str | None = None, year: int | None = None):
    airport = _airport(airport)
    rows = [r for r in _rows('otp_year') if (airport is None or r['airport'] == airport)
            and (year is None or int(r['year']) == int(year))]
    return rows


def weather_year(airport: str | None = None, year: int | None = None):
    airport = _airport(airport)
    rows = [r for r in _rows('weather_year') if (airport is None or r['airport'] == airport)
            and (year is None or int(r['year']) == int(year))]
    return rows


def enplanements(airport: str | None = None, year: int | None = None):
    airport = _airport(airport)
    rows = [r for r in _rows('enplanements') if (airport is None or r['airport'] == airport)
            and (year is None or int(r['year']) == int(year))]
    return rows


def flaw_days(airport: str | None = None, limit: int = 12, weather_only: bool = False):
    airport = _airport(airport)
    limit = max(1, min(int(limit), 40))
    rows = [r for r in _rows('flaw_days') if airport is None or r['airport'] == airport]
    if weather_only:
        rows = [r for r in rows if (r.get('weather_delay_min') or 0) > 0
                or classify_flaw_day(r)['pattern'] in (PATTERN_SNOWZILLA, PATTERN_ORD_WINTER, PATTERN_WEATHER_STORM)]
        # Drop pure COVID demand shocks when the ask is storm-focused.
        rows = [r for r in rows if classify_flaw_day(r)['pattern'] != PATTERN_COVID_DEMAND]
    return rows[:limit]


def daily(airport: str, date: str | None = None, year: int | None = None, limit: int = 20):
    airport = _airport(airport)
    if airport is None:
        raise ValueError('Airport is required for daily metrics')
    limit = max(1, min(int(limit), 50))
    rows = [r for r in _rows('daily') if r['airport'] == airport]
    if date:
        rows = [r for r in rows if r['date'] == date]
    elif year is not None:
        rows = [r for r in rows if int(r['year']) == int(year)]
    return rows[:limit]


def compare_otp(year: int = 2024):
    year = int(year)
    rows = otp_year(year=year)
    ranked = sorted(rows, key=lambda r: (-(r.get('dep_ontime_pct') or 0), r['airport']))
    return [{
        'airport': r['airport'],
        'year': r['year'],
        'dep_ontime_pct': r.get('dep_ontime_pct'),
        'arr_ontime_pct': r.get('arr_ontime_pct'),
        'dep_cancelled_pct': r.get('dep_cancelled_pct'),
        'origin_cause_weather_share_pct': r.get('origin_cause_weather_share_pct'),
        'origin_cause_late_aircraft_share_pct': r.get('origin_cause_late_aircraft_share_pct'),
        'enplanements': r.get('enplanements'),
    } for r in ranked]


def weather_risk(year: int = 2022):
    """Rank airports by packed NOAA annual hazard cues for one year."""
    year = int(year)
    rows = weather_year(year=year)
    ranked = []
    for r in rows:
        snow = float(r.get('total_snowfall_in') or 0)
        thunder = float(r.get('thunder_days_WT03') or 0)
        fog = float(r.get('fog_days_WT01') or 0)
        heavy_fog = float(r.get('heavy_fog_days_WT02') or 0)
        wind = float(r.get('extreme_wind_days_WSF2_ge_40mph') or 0)
        # Relative teaching score — not an operational weather index.
        score = snow * 1.2 + thunder * 1.5 + fog * 0.15 + heavy_fog * 0.8 + wind * 2.0
        ranked.append({
            'airport': r['airport'],
            'year': year,
            'risk_score': round(score, 1),
            'total_snowfall_in': r.get('total_snowfall_in'),
            'thunder_days_WT03': r.get('thunder_days_WT03'),
            'fog_days_WT01': r.get('fog_days_WT01'),
            'heavy_fog_days_WT02': r.get('heavy_fog_days_WT02'),
            'extreme_wind_days_WSF2_ge_40mph': r.get('extreme_wind_days_WSF2_ge_40mph'),
        })
    ranked.sort(key=lambda x: (-x['risk_score'], x['airport']))
    return ranked


def station_for(airport: str):
    airport = _airport(airport)
    for r in _rows('stations'):
        if r['airport'] == airport:
            return {
                'airport': airport,
                'station_id': r.get('verified_station_id') or r.get('suggested_station_id'),
                'station_name': r.get('station_name'),
                'status': r.get('status'),
            }
    return None


def classify_flaw_day(row: dict) -> dict:
    """Map a packed flaw day to a FlowBetter teaching pattern (not an approval)."""
    cancel = row.get('dep_cancel_rate')
    cancel = float(cancel) if cancel is not None else 0.0
    delay15 = row.get('dep_delay15_rate')
    delay15 = float(delay15) if delay15 is not None else 0.0
    wx_min = float(row.get('weather_delay_min') or 0)
    late_min = float(row.get('late_aircraft_delay_min') or 0)
    year = int(row.get('year') or 0)
    month = int(row.get('month') or 0)
    airport = row.get('airport')

    if year == 2020 and month in (3, 4, 5) and wx_min < 50:
        pattern = PATTERN_COVID_DEMAND
        desk = (
            'COVID demand/schedule shock — not weather. FlowBetter has no schedule-trim lever; '
            'do not train cancel-bank as the “right” COVID answer.'
        )
        strategies = {
            'cfo': 'No demand-cut tool; absorb framing does not model collapsed bookings.',
            'loyalty': 'Ferry/reserve spend is the wrong lever for empty banks.',
            'operations': 'Cancel tool exists but for the wrong reason — need a demand-shock profile.',
        }
        teaching = 'partial_mismatch'
    elif cancel >= 0.67 and airport in ('JFK', 'DCA', 'BOS'):
        pattern = PATTERN_SNOWZILLA
        desk = (
            'Snowzilla-scale multi-airport stop. Absorb and ferry-first fail crew legality in the '
            'sandbox; cancel-first Operations is the only feasible teaching path once holds wipe the last bank.'
        )
        strategies = {
            'cfo': 'Infeasible — forcing fly wrecks duty/network on near-total cancel days.',
            'loyalty': 'Infeasible — ferries do not clear multi-hour multi-airport closures.',
            'operations': 'Feasible teaching path — cancel last bank; passenger pillar correctly explodes.',
        }
        teaching = 'operations_only'
    elif airport == 'ORD' and cancel >= 0.4 and (late_min >= 3000 or delay15 >= 0.6):
        pattern = PATTERN_ORD_WINTER
        desk = (
            'ORD winter cancel+delay with late-aircraft cascade. Ferry helps one rotation; '
            'Operations cancel-bank protects overnight when the last ORD bank is cut.'
        )
        strategies = {
            'cfo': 'Likely infeasible — duty/network fail under long weather+late-aircraft minutes.',
            'loyalty': 'Partial — ferry helps one rotation; still weak on system late-aircraft.',
            'operations': 'Closer teaching fit — cancel last bank, protect overnight network pillar.',
        }
        teaching = 'operations_favored'
    elif wx_min > 0 or cancel >= 0.25:
        pattern = PATTERN_WEATHER_STORM
        desk = (
            'Weather-driven cancel/delay day. Desk should separate passenger vs network priorities '
            'among feasible plans — no blended winner.'
        )
        strategies = {
            'cfo': 'Cheap absorb only works on short single-airport bumps; fails on long holds.',
            'loyalty': 'Useful when metal/crew exist and today’s connections matter.',
            'operations': 'Use when tomorrow’s overnight position matters more than today’s flown load.',
        }
        teaching = 'pillar_tradeoff'
    else:
        pattern = PATTERN_GENERIC
        desk = 'Generic disruption sample — cite packed cancel/delay minutes; human chooses the pillar trade.'
        strategies = {
            'cfo': 'Compare financial cost only after hard crew checks pass.',
            'loyalty': 'Passenger pillar priority among feasible Pareto options.',
            'operations': 'Network/overnight pillar priority among feasible Pareto options.',
        }
        teaching = 'context_only'

    return {
        'pattern': pattern,
        'teaching': teaching,
        'desk_read': desk,
        'strategy_hints': strategies,
        'approves': False,
    }


def strategy_mapping(airport: str | None = None, limit: int = 5):
    """Top flaw days with FlowBetter CFO/Loyalty/Operations teaching hints."""
    rows = flaw_days(airport, limit)
    return [{
        **{k: r.get(k) for k in (
            'airport', 'date', 'dep_cancel_rate', 'dep_delay15_rate',
            'weather_delay_min', 'late_aircraft_delay_min', 'disruption_score',
        )},
        **classify_flaw_day(r),
    } for r in rows]


def _disruption_airports(disruptions):
    hits = []
    seen = set()
    for d in disruptions or []:
        ap = d.get('airport')
        if not ap or ap not in AIRPORTS or ap in seen:
            continue
        seen.add(ap)
        hits.append(d)
    return hits


def pillar_implications(disruptions=None):
    """Four-pillar desk implications for airports touched by the synthetic scenario."""
    notes = []
    kinds = {d.get('kind') for d in (disruptions or [])}
    airports = [d.get('airport') for d in _disruption_airports(disruptions)]
    weatherish = bool(kinds & {'weather', 'hold', 'deice', 'de-icing'}) or any(
        'weather' in (d.get('label') or '').lower()
        or 'de-ic' in (d.get('label') or '').lower()
        or 'ifr' in (d.get('label') or '').lower()
        for d in (disruptions or [])
    )
    overnight = 'overnight' in kinds or any(
        'overnight' in (d.get('label') or '').lower() for d in (disruptions or [])
    )
    duty = 'crew' in kinds or 'duty' in kinds or any(
        'duty' in (d.get('label') or '').lower() for d in (disruptions or [])
    )

    if weatherish or any(a in ('ORD', 'JFK', 'BOS', 'DCA') for a in airports):
        notes.append({
            'pillar': 'financial',
            'read': 'Storm-linked holds raise delay minutes ($100/m) before any ferry/cancel spend — cash looks cheap until legality fails.',
        })
        notes.append({
            'pillar': 'passenger',
            'read': 'Loyalty (ferry+reserve) protects today’s connections when metal exists; Operations cancel-bank spikes passenger pts via assumed overnight delay.',
        })
    if overnight or 'PIT' in airports or 'ORD' in airports:
        notes.append({
            'pillar': 'network',
            'read': 'Overnight PIT position is the network pillar — out-of-place tails cost 20k soft pts each; Operations cancel-bank is the teaching lever that zeros that penalty.',
        })
    if duty or overnight:
        notes.append({
            'pillar': 'crew',
            'read': 'Hard gate: negative crew buffer rejects the plan. On Snowzilla-scale history, CFO/Loyalty often go illegal; Operations stays legal when the last bank is cancelled.',
        })
    if not notes:
        notes = [
            {'pillar': 'financial', 'read': 'Compare cash only among crew-legal plans.'},
            {'pillar': 'passenger', 'read': 'Loyalty vs Operations is usually today’s pax vs tomorrow’s bank.'},
            {'pillar': 'network', 'read': 'Protect PIT overnight tails when the hub priority is tomorrow.'},
            {'pillar': 'crew', 'read': 'Discard any plan with failed hard crew checks — no blended score rescues it.'},
        ]
    return {
        'airports': airports,
        'implications': notes,
        'decision_rule': (
            'Discard hard-check failures first. Among feasible Pareto options, pick the hub priority '
            '(Loyalty → passengers; Operations → overnight network). Never average the four pillars. Never auto-approve.'
        ),
    }


def _relevant_flaws(airport: str, disruption: dict, limit: int = 3):
    """Prefer weather-linked history for weather/overnight pressure; still pack-only."""
    kind = (disruption.get('kind') or '').lower()
    label = (disruption.get('label') or '').lower()
    weatherish = kind in ('weather', 'hold', 'deice') or any(
        t in label for t in ('weather', 'de-ic', 'snow', 'ifr', 'storm')
    )
    overnightish = kind == 'overnight' or 'overnight' in label
    if weatherish or overnightish:
        preferred = flaw_days(airport, limit, weather_only=True)
        if preferred:
            return preferred
    # Default: skip pure COVID demand rows when the desk is not asking about COVID.
    rows = []
    for r in flaw_days(airport, 12):
        if classify_flaw_day(r)['pattern'] == PATTERN_COVID_DEMAND and not weatherish:
            continue
        rows.append(r)
        if len(rows) >= limit:
            break
    return rows or flaw_days(airport, limit)


def scenario_context(disruptions=None):
    """Aggregate historical context for airports touched by the current synthetic scenario."""
    hits = []
    for d in _disruption_airports(disruptions):
        ap = d.get('airport')
        otp = otp_year(ap, 2024)
        wx = weather_year(ap, 2022)
        flaws = _relevant_flaws(ap, d, 3)
        mapped = [classify_flaw_day(f) | {
            'date': f.get('date'),
            'dep_cancel_rate': f.get('dep_cancel_rate'),
            'weather_delay_min': f.get('weather_delay_min'),
        } for f in flaws]
        hits.append({
            'airport': ap,
            'disruption_kind': d.get('kind'),
            'disruption_label': d.get('label'),
            'otp_2024': otp[0] if otp else None,
            'weather_2022': wx[0] if wx else None,
            'recent_flaw_days': flaws,
            'strategy_hints': mapped,
        })
    return {
        'touched': hits,
        'pillars': pillar_implications(disruptions),
        'scope': SCOPE,
    }
