const simulationFrame=document.getElementById('simulation-frame');
const connection=document.getElementById('simulation-connection');
window.addEventListener('message',event=>{
 if(event.origin!==location.origin||event.source!==simulationFrame.contentWindow)return;
 if(event.data?.type==='flowbetter-height'&&Number.isFinite(event.data.height))simulationFrame.style.height=Math.min(16000,Math.max(1000,event.data.height+8))+'px';
 if(event.data?.type==='flowbetter-service'){
  connection.dataset.state=event.data.available?'ready':'offline';
  connection.textContent=event.data.available?'Simulation service connected · results and history are calculated and saved by the server.':'The simulation service is not connected. The live map remains available; simulation controls will unlock when the Python service is connected.';
 }
});
