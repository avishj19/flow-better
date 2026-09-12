"""Version 2: bounded recovery simulation with four independent scoring pillars."""
from copy import deepcopy
import random
import re

MODEL_VERSION = 2
HUB = 'PIT'
AIRPORTS = {'PIT': (290,180), 'BOS': (510,65), 'JFK': (480,170), 'DCA': (395,285), 'ORD': (90,95), 'DTW': (180,55)}
PLANS = {
    'cfo': (
        'The CFO Choice',
        'Wait for maintenance and keep the original aircraft and crew. '
        'Lowest cash outlay on paper (no ferry, no reserve crew), but the cascade usually blows the crew-duty buffer, so the desk cannot approve it when legality fails.',
    ),
    'loyalty': (
        'The Loyalty Choice',
        'Ferry a spare from DTW, staff it with reserve crew, finish the bank, then ferry the spare home. '
        'You pay for two positioning legs and a reserve crew to protect today’s passengers and connections; overnight network position can still take a soft penalty.',
    ),
    'operations': (
        'The Operations Choice',
        'Cancel the final ORD round trip and keep the aircraft overnight at PIT for tomorrow’s first bank. '
        'Best for next-day network readiness at the same modeled cash cost as Loyalty, but passengers on the cancelled pair absorb a large assumed overnight delay and missed connections.',
    ),
}
RULES = {'turn':30,'crew_turn':20,'duty':690,'segments':6,'flight_time':420,'rest':600,'connection':35,'gate_window':15}
CREW_SCOPE = 'Simplified Part 117-inspired duty model; actual FAA legality is not evaluated.'
FAA_SOURCE = 'https://www.faa.gov/about/office_org/headquarters_offices/agc/practice_areas/regulations/part117/part117_general'


def network_snapshot(s, state=None):
    """Extensive hub-and-spoke + overnight picture for the desk agent and map overlays."""
    hubs={}
    for tid, meta in s['tails'].items():
        hubs.setdefault(meta['overnight_hub'], {'tails': [], 'deadlines': {}})
        hubs[meta['overnight_hub']]['tails'].append(tid)
        hubs[meta['overnight_hub']]['deadlines'][tid] = meta['overnight_by']
    for hub in hubs:
        hubs[hub]['tails'] = sorted(hubs[hub]['tails'])
    overnight_pressure = None
    if state and state.get('details', {}).get('overnight_positions'):
        overnight_pressure = [
            {'tail': p['tail'], 'position': p['position'], 'hub': p['hub'],
             'deadline': p['deadline'], 'out_of_position': p['out_of_position'], 'penalty': p['penalty']}
            for p in state['details']['overnight_positions']
        ]
    elif state and state.get('scores') is not None:
        # Recompute lightly from viewed flights when details are absent.
        overnight_pressure = []
    airport_flow = {a: {'departures': 0, 'arrivals': 0, 'delayed_departures': 0, 'cancelled': 0, 'disrupted': False} for a in s['airports']}
    for f in s['flights']:
        airport_flow[f['origin']]['departures'] += 1
        airport_flow[f['destination']]['arrivals'] += 1
    if state and state.get('flights'):
        for f in state['flights']:
            if f.get('cancelled'):
                airport_flow[f['origin']]['cancelled'] += 1
            elif f.get('delay'):
                airport_flow[f['origin']]['delayed_departures'] += 1
    for d in s.get('disruptions', []):
        if d.get('airport') in airport_flow:
            airport_flow[d['airport']]['disrupted'] = True
    routes = {}
    for f in s['flights']:
        key = tuple(sorted((f['origin'], f['destination'])))
        routes[key] = routes.get(key, 0) + 1
    overnight_disruption = next((d for d in s.get('disruptions', []) if d.get('kind') == 'overnight'), None)
    return {
        'hub': HUB,
        'model_version': s.get('model_version', MODEL_VERSION),
        'airports': sorted(s['airports']),
        'spokes': [a for a in s['airports'] if a != HUB],
        'gates': {a: s['airports'][a]['gates'] for a in s['airports']},
        'route_pairs': [{'airports': list(k), 'daily_legs': n} for k, n in sorted(routes.items())],
        'airport_flow': airport_flow,
        'overnight_hubs': {
            hub: {
                'tails': info['tails'],
                'count': len(info['tails']),
                'role': 'primary_overnight_hub' if hub == HUB else 'outstation_overnight_hub',
                'deadlines': info['deadlines'],
            } for hub, info in sorted(hubs.items())
        },
        'overnight_disruption': overnight_disruption,
        'overnight_positions': overnight_pressure,
        'connection_groups': len(s.get('connections', [])),
        'flights': len(s['flights']),
        'network_penalty_unit': 20000,
        'scope': 'Synthetic overnight-hub network for four-pillar recovery; not a station plan',
    }


def generate(seed=42):
    rng=random.Random(seed);flights=[];tails={};crews={}
    for i in range(10):
        tid=f'T{i+1:02}';cid=f'C{i+1:02}';start=740+i*8
        tails[tid]={'position':'PIT','ready':700,'capacity':150,'type':'RJ','overnight_hub':'PIT','overnight_by':1440}
        crews[cid]={'position':'PIT','ready':700,'report':start-30,'rest':720,'type':'RJ','max_duty':690}
        for leg in range(6):
            spoke=list(AIRPORTS)[1:][(i+leg//2)%5]
            if i==0 and leg>=4:spoke='ORD'
            flights.append({'id':f'RX{100+i*6+leg}','rotation':i+1,'leg':leg,'origin':'PIT' if leg%2==0 else spoke,'destination':spoke if leg%2==0 else 'PIT','dep':start+leg*100,'arr':start+leg*100+60,'tail':tid,'crew':cid,'pax':rng.randint(85,140),'ferry':False})
    tails['R01']={'position':'DTW','ready':1050,'capacity':150,'type':'RJ','overnight_hub':'DTW','overnight_by':1400}
    crews['RC01']={'position':'DTW','ready':1050,'report':1020,'rest':720,'type':'RJ','max_duty':690}
    connections=[]
    for leg in (1,3):
        for i in range(10):
            inbound=flights[i*6+leg];outbound=flights[((i+2)%10)*6+leg+1]
            if outbound['dep']-inbound['arr']>=RULES['connection']:
                connections.append({'id':f'CN{len(connections)+1:02}','inbound':inbound['id'],'outbound':outbound['id'],'pax':rng.randint(12,28)})
    # A real consequence of the final outbound cancellation: a protected inbound connection.
    connections.append({'id':'CN17','inbound':'RX103','outbound':'RX104','pax':20})
    signals=[{'id':'SIG-ORD-01','source':'Synthetic Slack message · ORD Ground Ops','text':"Unstructured Input: Slack message from ORD Ground Ops: 'De-icing trucks are backed up, add 45 mins to any gate turnaround.'",'start':1140,'end':1320}]
    disruptions=[
        {'id':'D1','kind':'mechanical','resource':'T01','flight_id':'RX104','until':1245,'label':'Maintenance delay · T01 released at 20:45, 105m after RX104’s planned departure'},
        {'id':'D2','kind':'ground_ops','airport':'ORD','signal_id':'SIG-ORD-01','label':'ORD de-icing backlog · ground-ops text adds 45m to each affected turnaround'},
        {'id':'D3','kind':'crew_limit','resource':'C01','max_duty':650,'label':'Crew availability update · C01 has only 45m buffer beyond its original final release'},
        {'id':'D4','kind':'overnight','resource':'T01','deadline':1400,'label':'Overnight slot change · T01 must be at PIT by 23:20 to protect tomorrow’s first rotation'},
    ]
    return {'model_version':MODEL_VERSION,'seed':seed,'hub':HUB,'flights':flights,'tails':tails,'crews':crews,'connections':connections,'disruptions':disruptions,'unstructured_signals':signals,'rules':dict(RULES),
            'airports':{a:{'x':p[0],'y':p[1],'gates':4 if a==HUB else 2,'role':'hub' if a==HUB else 'spoke',
                          'overnight_role':'primary' if a==HUB else ('spare_base' if a=='DTW' else 'spoke')} for a,p in AIRPORTS.items()}}


def parse_signals(s,disrupted=True):
    """Narrow, deterministic extraction, not an LLM or general Slack understanding."""
    if not disrupted:return []
    active={d['signal_id'] for d in s['disruptions'] if d['kind']=='ground_ops'}
    parsed=[]
    for signal in s.get('unstructured_signals',[]):
        if signal['id'] not in active:continue
        text=signal['text']
        airport=re.search(r'\b([A-Z]{3}) Ground Ops\b',text)
        amount=re.search(r'\badd (\d{1,3}) mins? to any gate turnaround\b',text,re.I)
        if not airport or airport[1] not in s['airports'] or not amount or not 0<=int(amount[1])<=180:
            raise ValueError('Unrecognized ground-ops signal; review the text before simulation')
        parsed.append({'id':signal['id'],'airport':airport[1],'extra_turn_minutes':int(amount[1]),'start':signal['start'],'end':signal['end'],'text':text,'source':signal['source']})
    if active!={p['id'] for p in parsed}:raise ValueError('A ground-ops disruption is missing its source signal')
    return parsed


def extra_turn(f,signals):
    matches=[p for p in signals if f['destination']==p['airport'] and p['start']<=f['actual_arr']<p['end']]
    return sum(p['extra_turn_minutes'] for p in matches),[p['id'] for p in matches]


def resources(s,disrupted):
    tails=deepcopy(s['tails']);crews=deepcopy(s['crews'])
    if disrupted:
        for d in s['disruptions']:
            if d['kind']=='crew_limit':crews[d['resource']]['max_duty']=d['max_duty']
            if d['kind']=='overnight':tails[d['resource']]['overnight_by']=d['deadline']
    return tails,crews


def assignments(s,plan):
    fs=deepcopy(s['flights'])
    for f in fs:
        f['cancelled']=plan=='operations' and f['rotation']==1 and f['leg']>=4
        if plan=='loyalty' and f['rotation']==1 and f['leg']>=4:f.update(tail='R01',crew='RC01')
    if plan=='loyalty':
        for ident,origin,dest,dep in [('FERRY-1','DTW','PIT',1050),('FERRY-2','PIT','DTW',1330)]:
            fs.append({'id':ident,'rotation':1,'leg':-1,'origin':origin,'destination':dest,'dep':dep,'arr':dep+60,'tail':'R01','crew':'RC01','pax':0,'ferry':True,'cancelled':False})
    return fs


def gate_ok(bookings,start,end,cap):
    return all(sum(a<=t<b for a,b in bookings)<cap for t in range(start,end))


def simulate(s,plan='cfo',disrupted=True):
    if s.get('model_version')!=MODEL_VERSION:raise ValueError('Archived model version: generate a new scenario for four-pillar recovery')
    if plan not in PLANS:raise ValueError('Unknown recovery strategy')
    rules=s['rules'];signals=parse_signals(s,disrupted);tails,crews=resources(s,disrupted)
    result=[];done={};gates={a:[] for a in s['airports']}
    for f in sorted(assignments(s,plan),key=lambda f:(f['dep'],f['id'])):
        if f['cancelled']:
            f.update(actual_dep=None,actual_arr=None,delay=0,passenger_delay=1440,causes=['Cancelled to keep T01 at its overnight hub; 24h passenger delay assumed'],signal_ids=[])
            result.append(f);done[f['id']]=f;continue
        t=tails[f['tail']];c=crews[f['crew']];earliest=max(f['dep'],t['ready'],c['ready']);causes=[]
        if t['ready']>f['dep']:causes.append(f"Aircraft {f['tail']} ready {t['ready']}")
        if c['ready']>f['dep']:causes.append(f"Crew {f['crew']} ready {c['ready']}")
        for d in s['disruptions'] if disrupted else []:
            if d['kind']=='mechanical' and d['resource']==f['tail'] and d['flight_id']==f['id']:
                earliest=max(earliest,d['until']);causes.append(d['id']+' maintenance release')
        dep=earliest
        for _ in range(1440):
            arr=dep+f['arr']-f['dep']
            closure=next((d for d in s['disruptions'] if disrupted and d['kind']=='weather' and ((d['airport']==f['origin'] and d['start']<=dep<d['end']) or (d['airport']==f['destination'] and d['start']<=arr<d['end']))),None)
            if closure:
                dep=max(dep+1,closure['end'] if closure['airport']==f['origin'] else closure['end']-60);causes.append(closure['id']);continue
            if not gate_ok(gates[f['origin']],dep-15,dep,s['airports'][f['origin']]['gates']) or not gate_ok(gates[f['destination']],arr,arr+15,s['airports'][f['destination']]['gates']):
                dep+=1
                if 'Gate queue' not in causes:causes.append('Gate queue')
                continue
            break
        else:raise ValueError('Simulation horizon exhausted')
        f.update(actual_dep=dep,actual_arr=arr,delay=dep-f['dep'],passenger_delay=dep-f['dep'],causes=causes)
        extra,ids=extra_turn(f,signals);f['signal_ids']=ids;f['ground_extra_minutes']=extra
        # Explain the delayed *next* flight using its predecessor's source signal.
        if t.get('last_signals') and dep>f['dep']:f['causes'].append('Turnaround context: '+', '.join(t['last_signals']))
        gates[f['origin']].append((dep-15,dep));gates[f['destination']].append((arr,arr+15))
        t.update(position=f['destination'],ready=arr+rules['turn']+extra,last_signals=ids)
        c.update(position=f['destination'],ready=arr+rules['crew_turn'])
        result.append(f);done[f['id']]=f
    evidence=validate(s,result,disrupted)
    connections=[]
    for cn in s['connections']:
        inbound,outbound=done[cn['inbound']],done[cn['outbound']]
        gap=None if inbound['cancelled'] or outbound['cancelled'] else outbound['actual_dep']-inbound['actual_arr']
        connections.append(dict(cn,gap=gap,missed=gap is None or gap<rules['connection']))
    scores,details=calculate_recovery_scores(s,result,connections,disrupted)
    def add(kind,subject,passed,detail,hard=False):
        evidence.append({'id':f'E{len(evidence)+1:04}','kind':kind,'subject':subject,'passed':passed,'hard':hard,'detail':detail})
    for item in details['overnight_positions']:
        add('network_health',item['tail'],not item['out_of_position'],f"At cutoff {item['deadline']}: {item['position']}; planned {item['hub']}; {item['penalty']} network points")
    add('financial_score','option',True,f"{details['delay_minutes']} flight-delay min × $100 + {details['ferries']} ferries × $10,000 + {details['cancelled']} cancellations × $15,000 + {details['reserve_crews']} reserve crews × $3,000 = ${scores['financial_cost']:,}")
    add('passenger_score','option',True,f"{details['passenger_minutes']} passenger-delay min + {details['missed_pax']} missed connecting passengers × 250 = {scores['passenger_impact']:,} points; cancelled flight passengers get 1,440m assumed delay")
    for signal in signals:
        impacted=[f for f in result if signal['id'] in f.get('signal_ids',[])]
        add('signal_context',signal['id'],True,f"Parsed text: {signal['airport']} turnaround +{signal['extra_turn_minutes']}m in [{signal['start']}, {signal['end']}); {len(impacted)} aircraft visits affected")
    feasible=all(e['passed'] for e in evidence if e.get('hard',True))
    crew_legal=all(e['passed'] for e in evidence if e['kind'].startswith('crew_') or e['kind']=='qualification')
    scores['crew_buffer']['isLegal']=crew_legal
    o={'model_version':MODEL_VERSION,'plan':plan,'title':PLANS[plan][0],'description':PLANS[plan][1],'flights':result,'connections':connections,'evidence':evidence,'feasible':feasible,'isLegal':crew_legal,'scores':scores,'rank':None,'details':details,
       'metrics':{'delayed_flights':sum(f['delay']>0 and not f['ferry'] for f in result),'cancelled_flights':details['cancelled'],'delay_minutes':details['delay_minutes'],'passenger_minutes':details['passenger_minutes'],'missed_pax':details['missed_pax'],'cost':scores['financial_cost'],'cost_breakdown':details['cost_breakdown']}}
    o['rationale']=explain(o,signals)
    return o


def calculate_recovery_scores(s,flights,connections,disrupted=True):
    """Return four pillars. Never merge dollars, passenger points and network points."""
    tails,crews=resources(s,disrupted);operated=[f for f in flights if not f['cancelled']]
    # All operated flight delay, including ferry schedule slippage, is costed.
    delay=sum(f['delay'] for f in operated);ferries=sum(f['ferry'] for f in operated)
    cancelled=sum(f['cancelled'] for f in flights);reserves=len({f['crew'] for f in operated if f['crew'].startswith('R')})
    pax_minutes=sum(f['pax']*f['passenger_delay'] for f in flights)
    missed=sum(c['pax'] for c in connections if c['missed'])
    overnight=[]
    for tid,t in tails.items():
        pos=t['position'];deadline=t['overnight_by']
        for f in sorted((f for f in operated if f['tail']==tid),key=lambda f:f['actual_dep']):
            if f['actual_arr']<=deadline:pos=f['destination']
            elif f['actual_dep']<=deadline:pos=f"In flight {f['origin']}→{f['destination']}";break
        oop=pos!=t['overnight_hub']
        overnight.append({'tail':tid,'position':pos,'hub':t['overnight_hub'],'deadline':deadline,'out_of_position':oop,'penalty':20000 if oop else 0})
    buffers=[]
    for cid,c in crews.items():
        legs=[f for f in operated if f['crew']==cid]
        if legs:
            release=max(f['actual_arr'] for f in legs)+15;limit=min(s['rules']['duty'],c['max_duty'])
            buffers.append({'crew':cid,'report':c['report'],'release':release,'deadline':c['report']+limit,'minutes_remaining':c['report']+limit-release})
    minimum=min((b['minutes_remaining'] for b in buffers),default=0)
    breakdown={'delay':delay*100,'ferry_flights':ferries*10000,'cancellations':cancelled*15000,'reserve_crews':reserves*3000}
    scores={'financial_cost':sum(breakdown.values()),'passenger_impact':pax_minutes+missed*250,'network_health':sum(o['penalty'] for o in overnight),'crew_buffer':{'hours_remaining':round(minimum/60,3),'minutes_remaining':minimum,'exceeds_by_minutes':max(0,-minimum),'isLegal':minimum>=0,'scope':CREW_SCOPE}}
    return scores,{'delay_minutes':delay,'ferries':ferries,'cancelled':cancelled,'reserve_crews':reserves,'passenger_minutes':pax_minutes,'missed_pax':missed,'cost_breakdown':breakdown,'crew_buffers':buffers,'overnight_positions':overnight}


def validate(s,flights,disrupted=True):
    evidence=[];rules=s['rules'];tails,crews=resources(s,disrupted);signals=parse_signals(s,disrupted)
    def check(kind,subject,ok,detail):evidence.append({'id':f'E{len(evidence)+1:04}','kind':kind,'subject':subject,'passed':bool(ok),'hard':True,'detail':detail})
    base={f['id']:f for f in s['flights']};revenue=[f for f in flights if not f['ferry']];ops=[f for f in flights if not f['cancelled']]
    check('coverage','schedule',len(revenue)==len(base) and {f['id'] for f in revenue}==set(base) and len({f['id'] for f in flights})==len(flights),'One operated or explicitly cancelled record per original flight; unique ferry IDs')
    for f in flights:
        b=base.get(f['id']);t=tails[f['tail']];c=crews[f['crew']]
        if f['ferry']:
            spec={'FERRY-1':('DTW','PIT'),'FERRY-2':('PIT','DTW')}
            check('ferry',f['id'],f['id'] in spec and (f['origin'],f['destination'])==spec[f['id']] and f['pax']==0 and not f['cancelled'],'Bounded, zero-passenger positioning flight')
        elif b:
            check('schedule',f['id'],(f['origin'],f['destination'],f['pax'])==(b['origin'],b['destination'],b['pax']),'Original route and booked load retained')
        if f['cancelled']:
            check('cancellation',f['id'],f['actual_dep'] is None and f['actual_arr'] is None and f['passenger_delay']==1440,'Cancelled service has no physical movement; 24h passenger-delay assumption')
            continue
        check('schedule',f['id'],f['actual_dep']>=f['dep'] and f['actual_arr']-f['actual_dep']==60 and f['delay']==f['actual_dep']-f['dep'] and f['passenger_delay']==f['delay'],'No early departure; 60m flight duration')
        check('capacity',f['id'],f['pax']<=t['capacity'],f"{f['pax']} passengers / {t['capacity']} seats on {f['tail']}")
        check('qualification',f['id'],c['type']==t['type'],f"{f['crew']} {c['type']} / {t['type']}")
        for d in s['disruptions'] if disrupted else []:
            if d['kind']=='mechanical' and f['tail']==d['resource'] and f['id']==d['flight_id']:check('maintenance',f['id'],f['actual_dep']>=d['until'],f"D1 release {d['until']}; actual departure {f['actual_dep']}")
            if d['kind']=='weather':check('weather',f['id'],not ((f['origin']==d['airport'] and d['start']<=f['actual_dep']<d['end']) or (f['destination']==d['airport'] and d['start']<=f['actual_arr']<d['end'])),f"{d['id']} movement restriction [{d['start']},{d['end']})")
    for kind,fleet,key,turn in [('aircraft',tails,'tail',rules['turn']),('crew',crews,'crew',rules['crew_turn'])]:
        for ident,r in fleet.items():
            assigned=sorted((f for f in ops if f[key]==ident),key=lambda f:(f['actual_dep'],f['id']));pos=r['position'];ready=r['ready'];context='initial availability'
            for f in assigned:
                check(kind+'_position',f['id'],pos==f['origin'],f"{ident} at {pos}; departure requires {f['origin']}")
                check(kind+'_time',f['id'],f['actual_dep']>=ready,f"{ident} departs {f['actual_dep']}; earliest {ready} ({context})")
                extra,ids=extra_turn(f,signals) if kind=='aircraft' else (0,[])
                pos=f['destination'];ready=f['actual_arr']+turn+extra;context=f"{turn}m turn + {extra}m signal {' '.join(ids)}"
            if kind=='crew' and assigned:
                duty=assigned[-1]['actual_arr']+15-r['report'];limit=min(rules['duty'],r['max_duty']);buffer=limit-duty
                check('crew_duty',ident,buffer>=0,f"Modeled duty {duty}m / {limit}m; buffer {buffer}m; report {r['report']}, release {assigned[-1]['actual_arr']+15}. {CREW_SCOPE}")
                check('crew_report',ident,assigned[0]['actual_dep']>=r['report']+30,'30m report lead required')
                check('crew_segments',ident,len(assigned)<=rules['segments'],f"{len(assigned)} segments / {rules['segments']}")
                check('crew_flight_time',ident,len(assigned)*60<=rules['flight_time'],f"{len(assigned)*60}m airborne / {rules['flight_time']}m")
                check('crew_rest',ident,r['rest']>=rules['rest'],f"Prior rest {r['rest']}m / {rules['rest']}m")
    for airport,meta in s['airports'].items():
        intervals=[interval for f in ops for a,interval in [(f['origin'],(f['actual_dep']-15,f['actual_dep'])),(f['destination'],(f['actual_arr'],f['actual_arr']+15))] if a==airport]
        peak=max((sum(a<=t<b for a,b in intervals) for t in {a for a,b in intervals}),default=0)
        check('gate',airport,peak<=meta['gates'],f"Peak 15m service windows {peak} / {meta['gates']} gates; remote parking between services")
    return evidence


def explain(option,signals):
    scores=option['scores'];details=option['details'];plan=option['plan']
    objectives={
        'cfo':'Airport-desk read: cheapest cash path by waiting, but reject if crew buffer goes negative—money saved is useless when the plan is illegal.',
        'loyalty':'Airport-desk read: spend on ferry + reserve crew to keep passengers moving today; accept a softer overnight-position hit if the hub’s passenger product matters more.',
        'operations':'Airport-desk read: sacrifice today’s ORD bank to park metal at PIT for tomorrow; choose this when next-day network health outranks passenger impact.',
    }
    kinds=['financial_score','passenger_score','network_health','crew_duty','signal_context']
    citations=[]
    for kind in kinds:
        rows=[e for e in option['evidence'] if e['kind']==kind]
        if kind in ('network_health','crew_duty'):rows=sorted(rows,key=lambda e:(e['passed'], e['subject']!='T01' and e['subject']!='C01'))[:2]
        citations.extend({'id':e['id'],'kind':kind,'detail':e['detail']} for e in rows)
    return {'label':'AI rationale & citations','generator':'Deterministic translation of verified math · no LLM required','why':objectives[plan],'context_applied':[{'id':p['id'],'text':p['text'],'translation':f"{p['airport']}: {option['details'].get('base_turn',30)}m base + {p['extra_turn_minutes']}m = {30+p['extra_turn_minutes']}m turnaround for arrivals in [{p['start']}, {p['end']})."} for p in signals],'citations':citations,'crew_reference':FAA_SOURCE,'crew_scope':CREW_SCOPE,'rejection':f"REJECTED: Exceeds modeled crew duty limits by {scores['crew_buffer']['exceeds_by_minutes']} minutes." if scores['crew_buffer']['exceeds_by_minutes'] else ('REJECTED: A modeled hard constraint failed.' if not option['feasible'] else None)}


def scope_evidence(option):
    prefix=option['plan']+':'
    for e in option['evidence']:e['id']=prefix+e['id']
    for c in option['rationale']['citations']:c['id']=prefix+c['id']
    return option


def rank(options):
    """Pareto membership, not an arbitrary weighted sum or a forced winner."""
    keys=('financial_cost','passenger_impact','network_health')
    for o in options:
        o['rank']=None
        o['pareto_optimal']=o['feasible'] and not any(p['feasible'] and all(p['scores'][k]<=o['scores'][k] for k in keys) and any(p['scores'][k]<o['scores'][k] for k in keys) for p in options if p is not o)
        o['best_for']=[k for k in keys if o['scores'][k]==min(p['scores'][k] for p in options)]
    return sorted(options,key=lambda o:list(PLANS).index(o['plan']))
