import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';
import {flightAPI} from '../server/flight-api.mjs';
const root=path.resolve(import.meta.dirname,'../dist');const mime={'.html':'text/html','.css':'text/css','.js':'text/javascript','.webp':'image/webp','.png':'image/png','.svg':'image/svg+xml'};
http.createServer(async(req,res)=>{try{const url=new URL(req.url,'http://127.0.0.1:8024');if(url.pathname==='/api/flight-map'){const r=await flightAPI(new Request(url));res.writeHead(r.status,Object.fromEntries(r.headers));res.end(Buffer.from(await r.arrayBuffer()));return;}const requested=url.pathname==='/'?'index.html':decodeURIComponent(url.pathname.slice(1));const file=path.resolve(root,requested);if(!file.startsWith(root+path.sep)||requested.startsWith('server/')||requested.startsWith('.openai/')){res.writeHead(404);res.end();return;}const bytes=await fs.readFile(file);res.writeHead(200,{'content-type':mime[path.extname(file)]||'text/plain'});res.end(bytes);}catch{res.writeHead(404);res.end('Not found');}}).listen(8024,'127.0.0.1',()=>console.log('FlowBetter preview: http://127.0.0.1:8024'));
