import fs from 'node:fs';
import path from 'node:path';
const root=path.resolve(import.meta.dirname,'..');
const mime={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.webp':'image/webp','.png':'image/png','.svg':'image/svg+xml','.txt':'text/plain; charset=utf-8'};
const assets={};
function collect(dir){for(const entry of fs.readdirSync(dir,{withFileTypes:true})){if(entry.name==='server'||entry.name==='.openai')continue;const p=path.join(dir,entry.name);if(entry.isDirectory())collect(p);else {const url='/'+path.relative(path.join(root,'dist'),p).split(path.sep).join('/');assets[url]={type:mime[path.extname(p)]||'text/plain; charset=utf-8',data:fs.readFileSync(p).toString('base64')};}}}
collect(path.join(root,'dist'));
for(const name of fs.readdirSync(path.join(root,'frontend'))){if(!/\.(js|css|svg)$/.test(name)||name.endsWith('.test.js'))continue;const p=path.join(root,'frontend',name);assets['/static/'+name]={type:mime[path.extname(p)],data:fs.readFileSync(p).toString('base64')};}
const data=fs.readFileSync(path.join(root,'dist/flight-data.js'),'utf8');const api=fs.readFileSync(path.join(root,'server/flight-api.mjs'),'utf8').replace(/^import[^\n]+\n/,'');
const proxy=fs.readFileSync(path.join(root,'server/simulation-proxy.mjs'),'utf8');
const serve=`\nconst ASSETS=${JSON.stringify(assets)};\nexport default {async fetch(request,env,ctx){const url=new URL(request.url);if(url.pathname==='/desk')return Response.redirect(url.origin+'/#simulation',307);if(url.pathname.startsWith('/api/')&&url.pathname!=='/api/flight-map')return simulationProxy(request,env);if(!['GET','HEAD'].includes(request.method))return new Response('Method not allowed',{status:405,headers:{Allow:'GET, HEAD'}});if(url.pathname==='/api/flight-map')return flightAPI(request,env,ctx);const p=url.pathname==='/'?'/index.html':url.pathname==='/simulation'?'/simulation.html':url.pathname;const asset=ASSETS[p];if(!asset)return new Response('Not found',{status:404});const bytes=Uint8Array.from(atob(asset.data),c=>c.charCodeAt(0));return new Response(request.method==='HEAD'?null:bytes,{headers:{'content-type':asset.type,'cache-control':p.endsWith('.html')?'no-cache':'public, max-age=300','x-content-type-options':'nosniff','referrer-policy':'strict-origin-when-cross-origin'}});}};\n`;
fs.mkdirSync(path.join(root,'dist/server'),{recursive:true});fs.writeFileSync(path.join(root,'dist/server/index.js'),data+'\n'+api+'\n'+proxy+serve);
fs.mkdirSync(path.join(root,'dist/.openai'),{recursive:true});fs.copyFileSync(path.join(root,'.openai/hosting.json'),path.join(root,'dist/.openai/hosting.json'));
console.log(`Website worker built: ${Object.keys(assets).length} assets, ${fs.statSync(path.join(root,'dist/server/index.js')).size} bytes`);
