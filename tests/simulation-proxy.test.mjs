import test from 'node:test';
import assert from 'node:assert/strict';
import {simulationProxy} from '../server/simulation-proxy.mjs';
test('unconfigured service fails visibly and rejects arbitrary routes and origins',async()=>{
 assert.equal((await simulationProxy(new Request('https://site.test/api/status'))).status,503);
 assert.equal((await simulationProxy(new Request('https://site.test/api/proxy?url=https://evil.test'))).status,404);
 assert.equal((await simulationProxy(new Request('https://site.test/api/scenarios',{method:'POST',headers:{Origin:'https://evil.test'}}))).status,403);
});
test('simulation requests preserve body, desk and operator token through a fixed authenticated gateway',async()=>{
 const request=new Request('https://site.test/api/scenarios',{method:'POST',headers:{Origin:'https://site.test','X-IROP-Desk':'test','Authorization':'Bearer operator'},body:JSON.stringify({seed:42,profile:'ord_winter'})});
 let calls=0;const result=await simulationProxy(request,{SIMULATION_API_URL:'https://backend.test',SIMULATION_PROXY_TOKEN:'gateway'},async(url,init)=>{
  calls++;assert.equal(String(url),'https://backend.test/api/scenarios');assert.equal(init.headers.get('x-flowbetter-gateway'),'gateway');assert.equal(init.headers.get('authorization'),'Bearer operator');assert.equal(init.headers.get('x-irop-desk'),'test');assert.equal(JSON.parse(init.body).profile,'ord_winter');return Response.json({revision:0});
 });assert.equal(calls,1);assert.equal(result.status,200);assert.equal(result.headers.get('cache-control'),'no-store');assert.equal(result.headers.get('x-flowbetter-gateway'),null);
});
