"""Deterministic educational network. All times are minutes from synthetic day midnight."""
from copy import deepcopy
import random

AIRPORTS = {'PIT': (290,180), 'BOS': (510,65), 'JFK': (480,170), 'DCA': (395,285), 'ORD': (90,95), 'DTW': (180,55)}
PLANS = {
    'delay': ('Absorb delays', 'Keep original aircraft and crew; propagate every delay.'),
    'crew': ('Bring in reserve crews', 'Replace crews on rotations 1 and 3; keep original aircraft.'),
    'combined': ('Swap aircraft + crews', 'Use a hub reserve aircraft on rotation 1 and reserve crews on 1 and 3.'),
    'protect': ('Protect connections', 'Aircraft and crew recovery, plus bounded connection holds up to 60 minutes.'),
    'remote': ('Try a remote reserve', 'Test a reserve aircraft positioned at BOS; location must be verified.'),
    'small': ('Try a smaller reserve', 'Test a 60-seat reserve against booked passenger loads.'),
}
RULES = {'turn': 30, 'crew_turn': 20, 'duty': 690, 'segments': 6, 'flight_time': 420, 'rest': 600, 'connection': 35, 'gate_window': 15}

def generate(seed=42):
    rng = random.Random(seed)
    flights=[]; tails={}; crews={}
    for i in range(10):
        tid=f'T{i+1:02}'; cid=f'C{i+1:02}'; start=360+i*8
        tails[tid]={'position':'PIT','ready':330,'capacity':150,'type':'RJ'}
        crews[cid]={'position':'PIT','ready':330,'report':start-30,'rest':720,'type':'RJ'}
        for leg in range(6):
            spoke=list(AIRPORTS)[1:][(i+leg//2)%5]
            flights.append({'id':f'RX{100+i*6+leg}', 'rotation':i+1, 'leg':leg,
                            'origin':'PIT' if leg%2==0 else spoke, 'destination':spoke if leg%2==0 else 'PIT',
                            'dep':start+leg*100,'arr':start+leg*100+60,'tail':tid,'crew':cid,'pax':rng.randint(85,140)})
    for tid, pos, cap in [('R01','PIT',150),('R02','BOS',150),('R03','PIT',60)]:
        tails[tid]={'position':pos,'ready':330,'capacity':cap,'type':'RJ'}
    for i in (1,3):
        crews[f'RC{i:02}']={'position':'PIT','ready':330,'report':360+(i-1)*8-30,'rest':720,'type':'RJ'}
    crews['LC01']={'position':'PIT','ready':510,'report':480,'rest':720,'type':'RJ'}
    connections=[]
    for leg in (1,3):
        for i in range(10):
            inbound=flights[i*6+leg]
            # Same/later hub wave, separate rotation. Counts fit both flights' loads.
            j=(i+2)%10
            outbound=flights[j*6+leg+1]
            if outbound['dep']-inbound['arr'] >= RULES['connection']:
                connections.append({'id':f'CN{len(connections)+1:02}','inbound':inbound['id'],'outbound':outbound['id'],'pax':rng.randint(12,28)})
    disruptions=[
        {'id':'D1','kind':'mechanical','resource':'T01','until':510,'label':'T01 maintenance release delayed to 08:30'},
        {'id':'D2','kind':'weather','airport':'PIT','start':480,'end':525,'label':'PIT weather closure · 08:00–08:45'},
        {'id':'D3','kind':'crew','resource':'C03','until':465,'label':'C03 unavailable until 07:45'},
        {'id':'D4','kind':'weather','airport':'BOS','start':650,'end':710,'label':'BOS weather closure · 10:50–11:50'},
    ]
    return {'seed':seed,'flights':flights,'tails':tails,'crews':crews,'connections':connections,'disruptions':disruptions,'rules':dict(RULES),'airports':{a:{'x':p[0],'y':p[1],'gates':4 if a=='PIT' else 2} for a,p in AIRPORTS.items()}}

def resources(s, disrupted):
    tails=deepcopy(s['tails']); crews=deepcopy(s['crews'])
    if disrupted:
        for d in s['disruptions']:
            if d['kind']=='mechanical': tails[d['resource']]['ready']=max(tails[d['resource']]['ready'],d['until'])
            if d['kind']=='crew': crews[d['resource']]['ready']=max(crews[d['resource']]['ready'],d['until'])
    return tails,crews

def assignments(s, plan):
    fs=deepcopy(s['flights'])
    for f in fs:
        if plan in ('crew','combined','protect','remote','small') and f['rotation'] in (1,3): f['crew']=f"RC{f['rotation']:02}"
        if plan=='crew' and f['rotation']==1: f['crew']='LC01'
        if plan in ('combined','protect','remote','small') and f['rotation']==1: f['tail']={'remote':'R02','small':'R03'}.get(plan,'R01')
    return fs

def gate_ok(bookings, start, end, cap):
    return all(sum(a<=t<b for a,b in bookings)<cap for t in range(start,end))

def simulate(s, plan='delay', disrupted=True):
    if plan not in PLANS: raise ValueError('Unknown bounded recovery plan')
    rules=s['rules']; tails,crews=resources(s,disrupted)
    fs=assignments(s,plan); result=[]; done={}; gates={a:[] for a in s['airports']}
    for f in sorted(fs,key=lambda f:(f['dep'],f['id'])):
        t=tails[f['tail']]; c=crews[f['crew']]
        earliest=max(f['dep'],t['ready'],c['ready']); causes=[]
        if t['ready']>f['dep']: causes.append(f"Aircraft {f['tail']} available at {t['ready']}")
        if c['ready']>f['dep']: causes.append(f"Crew {f['crew']} available at {c['ready']}")
        if plan=='protect':
            for cn in s['connections']:
                if cn['outbound']==f['id'] and cn['inbound'] in done:
                    ready=done[cn['inbound']]['actual_arr']+rules['connection']
                    if ready<=earliest+60 and ready>earliest:
                        earliest=ready; causes.append('Connection hold '+cn['id'])
        dep=earliest
        for _ in range(1440):
            arr=dep+(f['arr']-f['dep'])
            closure=next((d for d in s['disruptions'] if disrupted and d['kind']=='weather' and
                ((d['airport']==f['origin'] and d['start']<=dep<d['end']) or
                 (d['airport']==f['destination'] and d['start']<=arr<d['end']))),None)
            if closure:
                dep=max(dep+1,closure['end'] if closure['airport']==f['origin'] else closure['end']-(f['arr']-f['dep']))
                if closure['id'] not in causes: causes.append(closure['id'])
                continue
            if not gate_ok(gates[f['origin']],dep-15,dep,s['airports'][f['origin']]['gates']) or not gate_ok(gates[f['destination']],arr,arr+15,s['airports'][f['destination']]['gates']):
                dep+=1
                if 'Gate queue' not in causes: causes.append('Gate queue')
                continue
            break
        else: raise ValueError('Simulation horizon exhausted')
        f.update(actual_dep=dep,actual_arr=arr,delay=dep-f['dep'],causes=causes)
        gates[f['origin']].append((dep-15,dep)); gates[f['destination']].append((arr,arr+15))
        t.update(position=f['destination'],ready=arr+rules['turn'])
        c.update(position=f['destination'],ready=arr+rules['crew_turn'])
        result.append(f);done[f['id']]=f
    evidence=validate(s,result,disrupted)
    missed=[]
    for cn in s['connections']:
        gap=done[cn['outbound']]['actual_dep']-done[cn['inbound']]['actual_arr']
        missed.append(dict(cn,gap=gap,missed=gap<rules['connection']))
    passenger_minutes=sum(f['delay']*f['pax'] for f in result)
    missed_pax=sum(c['pax'] for c in missed if c['missed'])
    delay_minutes=sum(f['delay'] for f in result)
    swaps=len({f['tail'] for f in result if f['tail'].startswith('R')})
    reserves=len({f['crew'] for f in result if f['crew'] not in s['crews'] or f['crew'].startswith(('R','L'))})
    cost={'passenger_delay':passenger_minutes*.5,'missed_connections':missed_pax*250,'operating_delay':delay_minutes*30,'aircraft_swaps':swaps*4500,'reserve_crews':reserves*1200}
    return {'plan':plan,'title':PLANS[plan][0], 'description':PLANS[plan][1], 'flights':result,'connections':missed,'evidence':evidence,
            'feasible':all(e['passed'] for e in evidence),'metrics':{'delayed_flights':sum(f['delay']>0 for f in result),'delay_minutes':delay_minutes,'passenger_minutes':passenger_minutes,'missed_pax':missed_pax,'cost':round(sum(cost.values()),2),'cost_breakdown':cost},'rank':None}

def validate(s, flights, disrupted=True):
    """Independent verifier reads the completed schedule; it does not trust simulator flags."""
    evidence=[]; rules=s['rules']; tails,crews=resources(s,disrupted)
    def check(kind, subject, ok, detail):
        evidence.append({'id':f'E{len(evidence)+1:04}','kind':kind,'subject':subject,'passed':bool(ok),'detail':detail})
    base={f['id']:f for f in s['flights']}
    check('coverage','schedule',len(flights)==len(base) and {f['id'] for f in flights}==set(base),'Exactly one operation for every scheduled flight')
    for f in flights:
        b=base[f['id']]; t=tails[f['tail']];c=crews[f['crew']]
        check('schedule',f['id'],f['actual_dep']>=b['dep'] and f['actual_arr']-f['actual_dep']==b['arr']-b['dep'] and (f['origin'],f['destination'],f['pax'])==(b['origin'],b['destination'],b['pax']),'No early departure; route, duration and booked load retained')
        check('capacity',f['id'],f['pax']<=t['capacity'],f"{f['pax']} passengers / {t['capacity']} seats on {f['tail']}")
        check('qualification',f['id'],c['type']==t['type'],f"Crew {f['crew']} {c['type']} / aircraft {t['type']}")
        for d in s['disruptions'] if disrupted else []:
            if d['kind']=='weather':
                ok=not ((f['origin']==d['airport'] and d['start']<=f['actual_dep']<d['end']) or (f['destination']==d['airport'] and d['start']<=f['actual_arr']<d['end']))
                check('weather',f['id'],ok,f"{d['id']}: no movement at {d['airport']} in [{d['start']}, {d['end']})")
    for kind, fleet, key, turn in [('aircraft',tails,'tail',rules['turn']),('crew',crews,'crew',rules['crew_turn'])]:
        for ident,r in fleet.items():
            assigned=sorted((f for f in flights if f[key]==ident),key=lambda f:(f['actual_dep'],f['id']))
            pos=r['position']; ready=r['ready']
            for f in assigned:
                check(kind+'_position',f['id'],pos==f['origin'],f"{ident} at {pos}; departure requires {f['origin']}")
                check(kind+'_time',f['id'],f['actual_dep']>=ready,f"{ident} departs {f['actual_dep']}; earliest {ready} (availability / {turn}m turnaround)")
                pos=f['destination'];ready=f['actual_arr']+turn
            if kind=='crew' and assigned:
                duty=assigned[-1]['actual_arr']+15-r['report']; airborne=sum(f['actual_arr']-f['actual_dep'] for f in assigned)
                check('crew_duty',ident,duty<=rules['duty'] and assigned[0]['actual_dep']>=r['report']+30,f"Duty incl. report/release {duty}m / {rules['duty']}m; report {r['report']}")
                check('crew_segments',ident,len(assigned)<=rules['segments'],f"{len(assigned)} segments / {rules['segments']}")
                check('crew_flight_time',ident,airborne<=rules['flight_time'],f"Flight time {airborne}m / {rules['flight_time']}m")
                check('crew_rest',ident,r['rest']>=rules['rest'],f"Prior rest {r['rest']}m / minimum {rules['rest']}m")
    for airport,meta in s['airports'].items():
        intervals=[]
        for f in flights:
            if f['origin']==airport: intervals.append((f['actual_dep']-15,f['actual_dep']))
            if f['destination']==airport: intervals.append((f['actual_arr'],f['actual_arr']+15))
        peak=max((sum(a<=t<b for a,b in intervals) for t in {a for a,b in intervals}),default=0)
        check('gate',airport,peak<=meta['gates'],f"Peak modeled gate windows {peak} / {meta['gates']} gates (15m departure/arrival; remote parking between)")
    return evidence

def rank(options):
    ordered=sorted(options,key=lambda o:(not o['feasible'],o['metrics']['cost'],o['plan']))
    n=0
    for o in ordered:
        if o['feasible']: n+=1;o['rank']=n
        else:o['rank']=None
    return ordered
