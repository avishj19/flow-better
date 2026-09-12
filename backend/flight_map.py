"""Public ADSB.lol observation adapter for the optional local Python website."""
import math
import re
import threading
import time
from .live_data import get_json
AIRPORTS={'JFK':(40.6413,-73.7781),'ATL':(33.6407,-84.4277),'ORD':(41.9742,-87.9073),'LAX':(33.9416,-118.4085),'DFW':(32.8998,-97.0403),'LHR':(51.47,-0.4543)}
CACHE={}
LOCK=threading.Lock()
def numeric(x):return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)
def text(x):return x.strip()[:40] if isinstance(x,str) else ''
def snapshot(airport,radius):
    if airport not in AIRPORTS or radius not in (25,50,100,150):raise ValueError('Unsupported airport or radius')
    with LOCK:
        key=(airport,radius);at=time.time()
        if key in CACHE and CACHE[key][0]>at:return CACHE[key][1]
        lat,lon=AIRPORTS[airport]
        raw=get_json(f'https://api.adsb.lol/v2/point/{lat}/{lon}/{radius}',{}, {'Accept':'application/json','User-Agent':'FlowBetter-airport-map/1.0'})
        if not isinstance(raw,dict) or not isinstance(raw.get('ac'),list) or not numeric(raw.get('now')):raise ValueError('Unexpected flight provider response')
        feed=raw['now']/1000 if raw['now']>1e12 else raw['now']
        if not -30<=at-feed<=120:raise ValueError('Flight observations are stale')
        rows=[];seen=set();excluded=0
        for a in raw['ac']:
            if not isinstance(a,dict) or not isinstance(a.get('hex'),str) or not re.fullmatch(r'~?[0-9a-fA-F]{6}',a['hex']) or a['hex'].lower() in seen or not all(numeric(a.get(k)) for k in ('lat','lon','seen_pos')) or abs(a['lat'])>90 or abs(a['lon'])>180 or not 0<=a['seen_pos']<=120 or at-(feed-a['seen_pos'])>120:
                excluded+=1;continue
            rad=math.pi/180;dlat=(a['lat']-lat)*rad;dlon=(a['lon']-lon)*rad
            h=math.sin(dlat/2)**2+math.cos(lat*rad)*math.cos(a['lat']*rad)*math.sin(dlon/2)**2
            distance=3440.065*2*math.atan2(math.sqrt(h),math.sqrt(max(0,1-h)))
            if distance>radius+1:excluded+=1;continue
            seen.add(a['hex'].lower())
            rows.append(dict(id=a['hex'].lower(),callsign=text(a.get('flight')),registration=text(a.get('r')),aircraftType=text(a.get('t')),lat=a['lat'],lon=a['lon'],altitudeFt=a.get('alt_baro') if numeric(a.get('alt_baro')) else None,onGround=True if a.get('alt_baro')=='ground' else False if numeric(a.get('alt_baro')) else None,groundspeedKt=a.get('gs') if numeric(a.get('gs')) and a['gs']>=0 else None,heading=a['track']%360 if numeric(a.get('track')) else None,positionTime=feed-a['seen_pos'],distanceNm=round(distance,1)))
        rows.sort(key=lambda a:a['distanceNm'])
        result=dict(provider='ADSB.lol',providerUrl='https://www.adsb.lol/',license='ODbL-1.0',airport=airport,radiusNm=radius,feedTime=feed,fetchedAt=at,rows=rows,excluded=excluded,refreshSeconds=15,scope='Reported aircraft nearby; not an arrivals or departures manifest.')
        CACHE[key]=(at+15,result)
        return result
