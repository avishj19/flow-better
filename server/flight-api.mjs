import {AIRPORTS,RADII,normalizeFlights} from '../dist/flight-data.js';
const cache=new Map(),pending=new Map();
let providerRetryAt=0,nextProviderAt=0;
const json=(body,status=200,headers={})=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store','x-content-type-options':'nosniff',...headers}});
export function parseQuery(url){const airport=url.searchParams.get('airport')||'JFK';const raw=url.searchParams.get('radius')||'100';const radius=Number(raw);if(!Object.hasOwn(AIRPORTS,airport)||!RADII.includes(radius)||!/^\d+$/.test(raw))return null;return{airport,radius};}
async function readBounded(response){if(Number(response.headers.get('content-length'))>4000000)throw new Error('The flight provider response is too large.');const reader=response.body?.getReader();if(!reader)throw new Error('The flight provider returned no data.');const chunks=[];let bytes=0;try{while(true){const {done,value}=await reader.read();if(done)break;bytes+=value.byteLength;if(bytes>4000000){await reader.cancel();throw new Error('The flight provider response is too large.');}chunks.push(value);}}finally{reader.releaseLock();}const buffer=new Uint8Array(bytes);let offset=0;for(const c of chunks){buffer.set(c,offset);offset+=c.length;}return JSON.parse(new TextDecoder().decode(buffer));}
export async function flightAPI(request,env={},ctx={},upstream=fetch){
 const query=parseQuery(new URL(request.url));if(!query)return json({error:'Choose one of the six airports and a 25, 50, 100, or 150 NM radius.'},400);
 const {airport,radius}=query,key=`${airport}:${radius}`;const prior=cache.get(key);if(prior&&Date.now()<prior.expires)return json(prior.body,prior.status,prior.headers);
 if(pending.has(key))return json(...await pending.get(key));
 const job=(async()=>{const cfCache=globalThis.caches?.default;const cacheKey=new Request(`${new URL(request.url).origin}/_flight-cache/v1/${airport}/${radius}`);
 try{
  const saved=await cfCache?.match(cacheKey);if(saved){const body=await saved.json();cache.set(key,{body,status:200,headers:{},expires:Date.now()+10000});return[body,200,{}];}
  if(Date.now()<providerRetryAt){const error=new Error('The flight provider is rate-limiting requests. Please wait before refreshing.');error.retrySeconds=Math.ceil((providerRetryAt-Date.now())/1000);throw error;}
  const slot=Math.max(Date.now(),nextProviderAt);nextProviderAt=slot+1200;await new Promise(resolve=>setTimeout(resolve,Math.max(0,slot-Date.now())));
  if(Date.now()<providerRetryAt){const error=new Error('The flight provider is rate-limiting requests. Please wait before refreshing.');error.retrySeconds=Math.ceil((providerRetryAt-Date.now())/1000);throw error;}
  const a=AIRPORTS[airport];const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),18000);
  let body;try{const response=await upstream(`https://api.adsb.lol/v2/point/${a.lat}/${a.lon}/${radius}`,{headers:{Accept:'application/json','User-Agent':'FlowBetter-airport-map/1.0'},signal:controller.signal});
   if(!response.ok){const wait=Math.min(3600,Math.max(30,Number(response.headers.get('retry-after'))||60));const error=new Error(response.status===429?'The flight provider is rate-limiting requests. Please wait before refreshing.':'The live flight provider is temporarily unavailable.');error.retrySeconds=wait;if(response.status===429)providerRetryAt=Date.now()+wait*1000;throw error;}
   body=normalizeFlights(await readBounded(response),airport,radius);
  }finally{clearTimeout(timer);}
  cache.set(key,{body,status:200,headers:{},expires:Date.now()+15000});
  if(cfCache){const write=cfCache.put(cacheKey,json(body,200,{'cache-control':'public, max-age=15'}));if(ctx.waitUntil)ctx.waitUntil(write);else await write;}
  return[body,200,{}];
 }catch(error){const retrySeconds=error.retrySeconds||30;const body={error:error.name==='AbortError'?'The flight provider timed out. Please try again shortly.':error.message?.startsWith('The flight provider')||error.message?.startsWith('The live flight')?error.message:'The live flight feed could not be read. Please try again shortly.',retrySeconds};const headers={'retry-after':String(retrySeconds)};cache.set(key,{body,status:503,headers,expires:Date.now()+retrySeconds*1000});return[body,503,headers];}
 })();pending.set(key,job);try{return json(...await job);}finally{pending.delete(key);}
}
