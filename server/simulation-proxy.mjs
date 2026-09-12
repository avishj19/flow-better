export async function simulationProxy(request,env={},upstream=fetch){
 const reply=(detail,status)=>Response.json({detail},{status,headers:{'cache-control':'no-store'}});
 const url=new URL(request.url);
 if(!/^\/api\/(status|auth\/(config|me)|scenarios(?:\/[a-f0-9]{32}(?:\/(disrupt|experiments|approve|weather-projection|network|agent|analysis))?)?|observations(?:\/status)?|agent\/starters|analysis\/(status|starters|ask))$/.test(url.pathname))return reply('Unknown API route',404);
 if(!['GET','POST'].includes(request.method))return reply('Method not allowed',405);
 if(request.headers.get('origin')&&request.headers.get('origin')!==url.origin)return reply('Cross-origin request forbidden',403);
 if(!env.SIMULATION_API_URL||!env.SIMULATION_PROXY_TOKEN)return reply('The Python simulation service has not been connected.',503);
 let base;try{base=new URL(env.SIMULATION_API_URL);if(base.protocol!=='https:'||base.username||base.password)throw Error();}catch{return reply('The simulation service configuration is invalid.',503);}
 if(Number(request.headers.get('content-length'))>32768)return reply('Request too large',413);
 const body=request.method==='POST'?await request.text():undefined;if(body&&new TextEncoder().encode(body).length>32768)return reply('Request too large',413);
 const target=new URL(url.pathname,base.origin);
 const headers=new Headers({'Accept':'application/json','Content-Type':'application/json','Origin':base.origin,'X-FlowBetter-Gateway':env.SIMULATION_PROXY_TOKEN});
 for(const key of ['authorization','x-irop-desk'])if(request.headers.has(key))headers.set(key,request.headers.get(key));
 try{
  const response=await upstream(target,{method:request.method,headers,body,redirect:'error',signal:AbortSignal.timeout(120000)});
  return new Response(response.body,{status:response.status,headers:{'content-type':response.headers.get('content-type')||'application/json','cache-control':'no-store','x-content-type-options':'nosniff'}});
 }catch{return reply('The simulation service could not be reached. Please try again shortly.',503);}
}
