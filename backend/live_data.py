"""Official, read-only observation feeds. No scraping or inferred aircraft availability."""
import json
import math
import os
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import httpx

AWC='https://aviationweather.gov/api/data/metar'
FR24='https://fr24api.flightradar24.com/api/live/flight-positions/full'
# Small, fixed airport vicinity bounding boxes, not airport property boundaries.
BOUNDS={'PIT':'40.53,40.43,-80.30,-80.15','BOS':'42.41,42.31,-71.08,-70.93','JFK':'40.69,40.59,-73.85,-73.70','DCA':'38.90,38.80,-77.12,-76.97','ORD':'42.03,41.93,-87.98,-87.83','DTW':'42.27,42.17,-83.42,-83.27'}

def now():return datetime.now(timezone.utc).timestamp()
def stamp(t):return datetime.fromtimestamp(t,timezone.utc).isoformat()
def config():return {'fr24_configured':bool(os.getenv('FR24_API_TOKEN')),'fr24_environment':os.getenv('FR24_ENVIRONMENT','production'),'weather_source':'NOAA Aviation Weather Center','weather_cache_seconds':300,'fr24_cache_seconds':60,'automatic_polling':False}

def epoch(value):
    try:
        if isinstance(value,(float,int)) and not isinstance(value,bool):return float(value) if math.isfinite(value) else None
        return datetime.fromisoformat(value.replace('Z','+00:00')).timestamp() if value else None
    except (ValueError,TypeError,AttributeError):return None

def age(t,at,limit):return t is not None and -300<=at-t<=limit

def get_json(url,params,headers):
    try:
        with httpx.stream('GET',url,params=params,headers=headers,timeout=20) as response:
            response.raise_for_status()
            if response.status_code==204:return []
            chunks=[];size=0
            for chunk in response.iter_bytes():
                size+=len(chunk)
                if size>2_000_000:raise ValueError('Provider response exceeded the 2 MB safety bound')
                chunks.append(chunk)
            return json.loads(b''.join(chunks))
    except httpx.HTTPStatusError as e:
        raise ValueError(f'Provider HTTP {e.response.status_code}; check token, API subscription, quota or provider status.') from None
    except (httpx.HTTPError,json.JSONDecodeError):raise ValueError('Provider unavailable or returned invalid JSON. No fabricated live result was substituted.') from None

def normalize_weather(payload,at):
    if not isinstance(payload,list):raise ValueError('Unexpected weather response format')
    by_station={}
    for row in payload:
        if not isinstance(row,dict) or row.get('icaoId') not in {'K'+a for a in BOUNDS}:continue
        t=epoch(row.get('obsTime'))
        old=by_station.get(row['icaoId'])
        if t is None or old and t<=old['observed_epoch']:continue
        by_station[row['icaoId']]={'airport':row['icaoId'][1:],'observed_epoch':t,'observed_at':stamp(t),'category':row.get('fltCat','UNKNOWN'),'wind_kt':row.get('wspd'),'gust_kt':row.get('wgst'),'visibility_sm':row.get('visib'),'weather':row.get('wxString',''),'raw':str(row.get('rawOb',''))[:500],'fresh':age(t,at,5400)}
    return list(by_station.values())

def normalize_positions(payload,at,airport):
    if not isinstance(payload,dict) or not isinstance(payload.get('data'),list):raise ValueError('Unexpected FR24 response format')
    out=[];seen=set();north,south,west,east=map(float,BOUNDS[airport].split(','))
    for r in payload['data'][:50]:
        if not isinstance(r,dict):continue
        ident=r.get('fr24_id');t=epoch(r.get('timestamp'))
        lat,lon=r.get('lat'),r.get('lon')
        if not ident or ident in seen or not all(isinstance(n,(float,int)) and not isinstance(n,bool) and math.isfinite(n) for n in (lat,lon)):continue
        if not south<=lat<=north or not west<=lon<=east:continue
        seen.add(ident)
        speed=r.get('gspeed')
        slow=isinstance(speed,(float,int)) and not isinstance(speed,bool) and 0<=speed<=40
        out.append({'id':str(ident)[:80],'registration':str(r.get('reg') or 'Unknown')[:40],'flight':str(r.get('flight') or r.get('callsign') or 'Unknown')[:40],'aircraft_type':str(r.get('type') or 'Unknown')[:20],'lat':lat,'lon':lon,'altitude_ft':r.get('alt'),'groundspeed_kt':speed,'observed_epoch':t,'observed_at':stamp(t) if t is not None else None,'fresh':age(t,at,300),'ground_status':'Low speed; ground status unconfirmed' if slow else 'Ground status unknown','available_for_swap':False})
    return out

def folder(root):
    p=Path(root)/'observations';p.mkdir(parents=True,exist_ok=True);return p

def snapshots(root):
    out=[]
    for p in folder(root).glob('*.json'):
        try:out.append(json.loads(p.read_text()))
        except (OSError,json.JSONDecodeError):continue
    return sorted(out,key=lambda s:s['fetched_epoch'],reverse=True)

def read(root,ident):
    if len(ident)!=32 or any(c not in '0123456789abcdef' for c in ident):raise ValueError('Invalid snapshot ID')
    p=folder(root)/(ident+'.json')
    if not p.exists():raise ValueError('Snapshot not found in this desk')
    return json.loads(p.read_text())

def fetch(root,source,airport='PIT',consent=False,request=get_json,at=None):
    at=now() if at is None else at
    if source not in ('weather','fr24') or airport not in BOUNDS:raise ValueError('Unsupported source or airport')
    if source=='fr24' and not consent:raise ValueError('Confirm one bounded FR24 request; API credits may be consumed')
    for s in snapshots(root):
        if s['source']==source and (source=='weather' or (s['airport']==airport and s['environment']==os.getenv('FR24_ENVIRONMENT','production'))) and age(s['fetched_epoch'],at,300 if source=='weather' else 60):
            return dict(s,cached=True)
    headers={'Accept':'application/json','User-Agent':'FlowBetter-local-demo/0.2'}
    if source=='weather':
        raw=request(AWC,{'ids':','.join('K'+a for a in BOUNDS),'format':'json'},headers)
        rows=normalize_weather(raw,at);environment='production';url=AWC
    else:
        token=os.getenv('FR24_API_TOKEN')
        if not token:raise ValueError('FR24_API_TOKEN is not configured on the server; a separate FR24 API subscription is required')
        environment=os.getenv('FR24_ENVIRONMENT','production')
        if environment not in ('production','sandbox'):raise ValueError('FR24_ENVIRONMENT must be production or sandbox')
        headers.update({'Authorization':'Bearer '+token,'Accept-Version':'v1'})
        url=FR24  # FR24 selects sandbox data via the sandbox API key, on the same endpoint.
        raw=request(url,{'bounds':BOUNDS[airport],'limit':50},headers)
        rows=normalize_positions(raw,at,airport)
    report={'id':uuid.uuid4().hex,'source':source,'provider':'NOAA AWC' if source=='weather' else 'Flightradar24','environment':environment,'airport':airport if source=='fr24' else 'network','fetched_epoch':at,'fetched_at':stamp(at),'rows':rows,'missing_airports':[a for a in BOUNDS if a not in {r['airport'] for r in rows}] if source=='weather' else [],'cached':False,'source_url':url,'scope':'Observed weather; no official closure status' if source=='weather' else 'Tracked vicinity traffic only; incomplete ground coverage; not available reserve aircraft; ground vehicles may be present','potentially_truncated':source=='fr24' and len(raw.get('data',[]))>=50}
    p=folder(root)/(report['id']+'.json');tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(report));tmp.replace(p)
    return report

def projected_weather(snapshot,at=None):
    at=now() if at is None else at
    if snapshot['source']!='weather' or snapshot['environment']!='production':raise ValueError('Only production weather observations can drive this projection')
    rows=snapshot['rows']
    if {r['airport'] for r in rows}!=set(BOUNDS) or not all(age(r['observed_epoch'],at,5400) for r in rows):raise ValueError('All six airports need observations no older than 90 minutes; refresh weather')
    disruptions=[];decisions=[]
    for r in rows:
        cat=r['category'];gust=r.get('gust_kt');wx=str(r.get('weather',''))
        if cat not in ('VFR','MVFR','IFR','LIFR'):raise ValueError('Unknown weather category; projection blocked')
        minutes={'VFR':0,'MVFR':15,'IFR':30,'LIFR':60}[cat]
        if isinstance(gust,(int,float)) and gust>=30:minutes=max(minutes,45)
        if 'TS' in wx:minutes=max(minutes,60)
        decisions.append({'airport':r['airport'],'observed_at':r['observed_at'],'category':cat,'hold_minutes':minutes,'rule':'demo-weather-v1','basis':'Hypothetical movement hold projected to synthetic 19:00; not an official closure'})
        if minutes:disruptions.append({'id':'WX-'+r['airport'],'kind':'weather','airport':r['airport'],'start':1140,'end':1140+minutes,'label':f"{r['airport']} observed {cat} → hypothetical {minutes}m hold at synthetic 19:00",'source_snapshot':snapshot['id'],'observed_at':r['observed_at']})
    return disruptions,decisions
