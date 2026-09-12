import http from 'node:http';
import worker from '../dist/server/index.js';
http.createServer(async(req,res)=>{
 try {
  const url=new URL(req.url,'http://127.0.0.1:8024');
  const request=new Request(url,{method:req.method,headers:req.headers,...(!['GET','HEAD'].includes(req.method)?{body:req,duplex:'half'}:{})});
  const response=await worker.fetch(request,process.env,{});
  res.writeHead(response.status,Object.fromEntries(response.headers));res.end(Buffer.from(await response.arrayBuffer()));
 } catch {res.writeHead(500);res.end('Preview request failed');}
}).listen(8024,'127.0.0.1',()=>console.log('Built Sites preview: http://127.0.0.1:8024 (use Python on 8011 for the complete local simulation)'));
