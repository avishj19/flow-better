export const AIRPORTS = {
  JFK: {code:'JFK', name:'John F. Kennedy', city:'New York', lat:40.6413, lon:-73.7781},
  ATL: {code:'ATL', name:'Hartsfield–Jackson', city:'Atlanta', lat:33.6407, lon:-84.4277},
  ORD: {code:'ORD', name:'O’Hare', city:'Chicago', lat:41.9742, lon:-87.9073},
  LAX: {code:'LAX', name:'Los Angeles International', city:'Los Angeles', lat:33.9416, lon:-118.4085},
  DFW: {code:'DFW', name:'Dallas Fort Worth', city:'Dallas–Fort Worth', lat:32.8998, lon:-97.0403},
  LHR: {code:'LHR', name:'Heathrow', city:'London', lat:51.47, lon:-0.4543}
};
export const RADII=[25,50,100,150];
export const STALE_SECONDS=120;
const numeric=x=>typeof x==='number'&&Number.isFinite(x);
const text=(v,n=40)=>typeof v==='string'?v.trim().slice(0,n):'';
export function distanceNm(lat,lon,a){const r=Math.PI/180,dlat=(lat-a.lat)*r,dlon=(lon-a.lon)*r;const h=Math.sin(dlat/2)**2+Math.cos(a.lat*r)*Math.cos(lat*r)*Math.sin(dlon/2)**2;return 3440.065*2*Math.atan2(Math.sqrt(h),Math.sqrt(Math.max(0,1-h)));}
export function normalizeFlights(payload,airport,radius,at=Date.now()){
  if(!payload||!Array.isArray(payload.ac)||!numeric(payload.now))throw new Error('The flight provider returned an unexpected response.');
  const feedTime=payload.now>1e12?payload.now/1000:payload.now;
  if(at/1000-feedTime>STALE_SECONDS||feedTime-at/1000>30)throw new Error('The flight provider’s observation time is stale or invalid.');
  const seen=new Set(),rows=[];let excluded=0;
  for(const a of payload.ac){
    if(!a||typeof a.hex!=='string'||!/^~?[0-9a-f]{6}$/i.test(a.hex)||seen.has(a.hex.toLowerCase())||!numeric(a.lat)||!numeric(a.lon)||Math.abs(a.lat)>90||Math.abs(a.lon)>180||!numeric(a.seen_pos)||a.seen_pos<0||a.seen_pos>STALE_SECONDS){excluded++;continue;}
    const positionTime=feedTime-a.seen_pos;
    if(at/1000-positionTime>STALE_SECONDS){excluded++;continue;}
    const distance=distanceNm(a.lat,a.lon,AIRPORTS[airport]);
    if(distance>radius+1){excluded++;continue;}
    seen.add(a.hex.toLowerCase());
    rows.push({id:a.hex.toLowerCase(),callsign:text(a.flight),registration:text(a.r),aircraftType:text(a.t,12),lat:a.lat,lon:a.lon,altitudeFt:numeric(a.alt_baro)?a.alt_baro:null,onGround:a.alt_baro==='ground'?true:numeric(a.alt_baro)?false:null,groundspeedKt:numeric(a.gs)&&a.gs>=0?a.gs:null,heading:numeric(a.track)?((a.track%360)+360)%360:null,positionTime,distanceNm:Math.round(distance*10)/10});
  }
  rows.sort((a,b)=>a.distanceNm-b.distanceNm);
  return {provider:'ADSB.lol',providerUrl:'https://www.adsb.lol/',license:'ODbL-1.0',airport,radiusNm:radius,feedTime,fetchedAt:at/1000,rows,excluded,refreshSeconds:15,scope:'Reported aircraft within the selected radius. Coverage is incomplete; nearby aircraft are not necessarily arriving at or departing this airport.'};
}
