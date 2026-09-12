const reportSize=()=>{if(parent!==window)parent.postMessage({type:'flowbetter-height',height:document.documentElement.scrollHeight},location.origin)};
new ResizeObserver(reportSize).observe(document.body);
window.addEventListener('load',reportSize);
fetch('/api/status').then(async response=>{
 const status=await response.json();if(!response.ok||status.status!=='ok')throw Error('unavailable');
 parent.postMessage({type:'flowbetter-service',available:true},location.origin);
}).catch(()=>{
 document.body.classList.add('offline');
 const notice=document.createElement('div');notice.className='unavailable-notice';notice.setAttribute('role','status');notice.textContent='The simulation service is not connected. This workspace needs the FlowBetter Python service to calculate results and save decisions. No sample results will be substituted.';
 document.querySelector('main').prepend(notice);
 document.querySelectorAll('button,input,select').forEach(el=>el.disabled=true);
 parent.postMessage({type:'flowbetter-service',available:false},location.origin);
 reportSize();
});
