import copy
import hashlib
import hmac
import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse, FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field, ConfigDict
from . import store, agent_workflow as workflow, live_data, virtual_agent, analysis_agent, auth
from .simulator import generate, simulate, validate, scope_evidence, MODEL_VERSION, network_snapshot
ROOT=Path(__file__).resolve().parents[1]
DATA=Path(os.getenv('IROP_DATA',str(ROOT/'data')))
app=FastAPI(title='FlowBetter · IROP Recovery Sandbox')
app.add_middleware(TrustedHostMiddleware,allowed_hosts=os.getenv('IROP_ALLOWED_HOSTS','127.0.0.1,localhost,testserver').split(','))
lock=threading.RLock()

@app.middleware('http')
async def guard(request:Request,call_next):
    gateway_token=os.getenv('IROP_PROXY_TOKEN','')
    if gateway_token and request.url.path.startswith('/api/') and not hmac.compare_digest(request.headers.get('x-flowbetter-gateway',''),gateway_token):
        return JSONResponse({'detail':'Gateway authentication required'},status_code=401)
    origin=request.headers.get('origin')
    allowed=os.getenv('IROP_ORIGINS','http://127.0.0.1:8010,http://localhost:8010,http://127.0.0.1:8011,http://localhost:8011').split(',')
    if request.method not in ('GET','HEAD','OPTIONS') and origin and origin not in allowed:return JSONResponse({'detail':'Cross-origin writes forbidden'},status_code=403)
    auth.set_claims(None)
    try:
        if auth.enabled() and not auth.is_public(request.url.path) and request.method!='OPTIONS':
            claims=await auth.authenticate(request)
            auth.set_claims(claims)
            store.set_desk(auth.desk_for(claims))
        else:
            store.set_desk(request.headers.get('x-irop-desk') if not auth.enabled() else 'default')
    except auth.AuthError as e:
        return auth.error_response(e)
    except ValueError as e:
        return JSONResponse({'detail':str(e)},status_code=400)
    r=await call_next(request);r.headers['X-Content-Type-Options']='nosniff';r.headers['X-IROP-Desk']=store.get_desk();return r

class Strict(BaseModel):model_config=ConfigDict(extra='forbid')
class Scenario(Strict):
    seed:int=Field(default=42,ge=0,le=999999,strict=True)
    profile:Literal['default','snowzilla_ne','ord_winter']='default'
class Revision(Strict):revision:int=Field(ge=0,strict=True)
class Experiment(Revision):
    mode:Literal['local','live']='local'
    consent:bool=False
class Approval(Revision):
    experiment_id:str
    plan:str
    confirm:bool=False
class AgentChat(Strict):
    message:str=Field(min_length=1,max_length=500)
class AnalysisAsk(Strict):
    message:str=Field(min_length=1,max_length=500)
    mode:Literal['local','live']='local'
    consent:bool=False
    scenario_id:str|None=None

def get(ident):
    r=store.get_run(DATA,ident)
    if not r:raise HTTPException(404,'Scenario not found in this desk')
    return r

def event(r,action,data):r['events'].append({'created':datetime.now(timezone.utc).isoformat(),'action':action,'data':auth.attach_actor(data)})
def fresh(r,revision):
    if r['revision']!=revision:raise HTTPException(409,'Stale scenario revision. Reload before acting.')
def digest(o):return hashlib.sha256(json.dumps({k:v for k,v in o.items() if k not in ('rank','digest','pareto_optimal','best_for')},sort_keys=True).encode()).hexdigest()

def current_model(r):
    if r['scenario'].get('model_version')!=MODEL_VERSION:raise HTTPException(409,'Archived model: generate a new scenario to use four-pillar recovery')

@app.get('/healthz')
def health():return {'status':'ok'}

@app.get('/api/status')
def status():
    payload=dict(status='ok',model_version=MODEL_VERSION,virtual_agent=True,analysis=analysis_agent.config(),**workflow.config(),auth=auth.public_config())
    if auth.enabled():payload['desk']=auth.actor() and store.get_desk()
    else:payload['desk']=store.get_desk()
    return payload
@app.get('/api/auth/config')
def auth_config():return auth.public_config()
@app.get('/api/auth/me')
def auth_me():
    claims=auth.current_claims()
    if not auth.enabled():return {'enabled':False,'authenticated':False}
    if not claims:raise HTTPException(401,{'error':'invalid_request','error_description':'Authentication required'})
    return {'enabled':True,'authenticated':True,'identity':auth.public_identity(claims),'permissions':sorted(auth.permissions(claims)),'desk':store.get_desk()}
@app.get('/api/agent/starters')
def agent_starters():return {'prompts':virtual_agent.starter_prompts(),'scope':'Local desk agent · network + overnight hub briefings'}
@app.get('/api/analysis/status')
def analysis_status():return analysis_agent.config()
@app.get('/api/analysis/starters')
def analysis_starters():return {'prompts':analysis_agent.starter_prompts(),'scope':analysis_agent.config()['scope']}
@app.post('/api/analysis/ask')
def analysis_ask(body:AnalysisAsk):
    disruptions=None
    if body.scenario_id:
        disruptions=get(body.scenario_id)['scenario'].get('disruptions')
    try:return analysis_agent.run(body.message,disruptions,body.mode,body.consent)
    except ValueError as e:raise HTTPException(422,str(e))
@app.post('/api/scenarios/{ident}/analysis')
def scenario_analysis(ident:str,body:AnalysisAsk):
    r=get(ident)
    try:return analysis_agent.run(body.message,r['scenario'].get('disruptions'),body.mode,body.consent)
    except ValueError as e:raise HTTPException(422,str(e))
@app.get('/api/scenarios')
def history():return store.list_run_summaries(DATA)
@app.get('/api/scenarios/{ident}')
def detail(ident:str):return get(ident)
@app.get('/api/scenarios/{ident}/network')
def scenario_network(ident:str):
    r=get(ident);return network_snapshot(r['scenario'],r.get('current'))
@app.post('/api/scenarios/{ident}/agent')
def scenario_agent(ident:str,body:AgentChat):
    return virtual_agent.respond(get(ident),body.message)
@app.post('/api/scenarios')
def create(body:Scenario):
    s=generate(body.seed, body.profile); baseline=simulate(s,disrupted=False)
    if not baseline['feasible']:raise HTTPException(422,'Generated baseline failed validation')
    r={'id':uuid.uuid4().hex,'name':f'PIT overnight hub · {body.profile} · seed {body.seed}','created':datetime.now(timezone.utc).isoformat(),'seed':body.seed,'profile':body.profile,'revision':0,'phase':'baseline','scenario':s,'baseline':baseline,'disrupted':None,'current':baseline,'experiments':[],'events':[]}
    event(r,'scenario_generated',{'seed':body.seed,'profile':body.profile,'flights':len(s['flights']),'weather_disruptions':sum(1 for d in s['disruptions'] if d['kind']=='weather')});store.save_run(DATA,r);return r
@app.post('/api/scenarios/{ident}/disrupt')
def disrupt(ident:str,body:Revision):
    with lock:
        r=get(ident);fresh(r,body.revision);current_model(r)
        if r['phase']!='baseline':raise HTTPException(409,'Disruptions already injected')
        r['disrupted']=simulate(r['scenario']);r['current']=r['disrupted'];r['phase']='disrupted';r['revision']+=1
        event(r,'disruptions_injected',{'disruptions':r['scenario']['disruptions'],'result':r['disrupted']['metrics']});store.save_run(DATA,r);return r
@app.post('/api/scenarios/{ident}/experiments')
def experiment(ident:str,body:Experiment):
    # Single-process local app: serialize state-changing work; provider work is bounded.
    with lock:
        r=get(ident);fresh(r,body.revision);current_model(r)
        if r['phase']!='disrupted':raise HTTPException(409,'Inject disruptions before evaluating; create a new scenario after approval')
        def persist(report):
            existing=next((i for i,x in enumerate(r['experiments']) if x['id']==report['id']),None)
            if existing is None:r['experiments'].append(copy.deepcopy(report))
            else:r['experiments'][existing]=copy.deepcopy(report)
            store.save_run(DATA,r)
        try:report=workflow.run(r['scenario'],r['revision'],body.mode,body.consent,persist=persist)
        except ValueError as e:raise HTTPException(422,str(e))
        for o in report['options']:o['digest']=digest({k:v for k,v in o.items() if k not in ('rank','digest')})
        persist(report);event(r,'experiment_finished',{'id':report['id'],'status':report['status'],'rejected':[o['plan'] for o in report['options'] if not o['feasible']]});store.save_run(DATA,r);return r
@app.post('/api/scenarios/{ident}/approve')
def approve(ident:str,body:Approval):
    with lock:
        r=get(ident)
        current_model(r)
        def reject(reason,code=409):
            event(r,'approval_rejected',{'reason':reason,'plan':body.plan,'experiment_id':body.experiment_id});store.save_run(DATA,r);raise HTTPException(code,reason)
        if not body.confirm:reject('Explicit simulation approval required',422)
        if r['revision']!=body.revision:reject('Stale scenario revision. Reload before acting.')
        if r['phase']!='disrupted':reject('Scenario is not awaiting recovery')
        ex=next((x for x in r['experiments'] if x['id']==body.experiment_id),None)
        if not ex or ex['status']!='completed' or ex['revision']!=r['revision']:reject('Experiment missing, failed, or stale')
        option=next((o for o in ex['options'] if o['plan']==body.plan),None)
        if not option or not option['feasible']:reject('Option missing or infeasible')
        if r.get('live_weather'):
            try:live_data.projected_weather(r['live_weather'])
            except ValueError:reject('Weather basis is stale; refresh and reapply observations before evaluating again')
        actual=scope_evidence(simulate(r['scenario'],body.plan))
        if not actual['feasible'] or digest({k:v for k,v in actual.items() if k!='rank'})!=option['digest']:reject('Verification changed; reevaluate before approval')
        r['current']=actual;r['revision']+=1;r['phase']='recovered'
        event(r,'simulation_approved',{'experiment_id':ex['id'],'plan':body.plan,'from_revision':body.revision,'to_revision':r['revision'],'result':actual['metrics'],'scope':'Simulation only'})
        store.save_run(DATA,r);return r
@app.get('/')
def home():return FileResponse(ROOT/'dist/index.html')

@app.get('/desk')
def recovery_desk():return RedirectResponse('/simulation',status_code=307)

@app.get('/simulation')
def embedded_simulator():return FileResponse(ROOT/'dist/simulation.html')

@app.get('/site.css')
def story_styles():return FileResponse(ROOT/'dist/site.css')

@app.get('/site.js')
def story_script():return FileResponse(ROOT/'dist/site.js')

@app.get('/content.js')
def story_content():return FileResponse(ROOT/'dist/content.js')

@app.get('/style-tile.html')
def story_board():return FileResponse(ROOT/'dist/style-tile.html')

app.mount('/assets',StaticFiles(directory=ROOT/'dist/assets'),name='story-assets')

@app.get('/api/flight-map')
def flight_map_observations(airport:str='JFK',radius:int=100):
    from .flight_map import snapshot, AIRPORTS
    if airport not in AIRPORTS or radius not in (25,50,100,150):raise HTTPException(400,'Unsupported airport or radius')
    from fastapi.responses import RedirectResponse, JSONResponse
    try:return JSONResponse(snapshot(airport,radius),headers={'Cache-Control':'no-store'})
    except ValueError:return JSONResponse({'error':'The live flight feed is temporarily unavailable.','retrySeconds':30},status_code=503,headers={'Retry-After':'30','Cache-Control':'no-store'})

@app.get('/flight-map.js')
@app.get('/flight-map.css')
@app.get('/flight-data.js')
def flight_map_assets(request:Request):return FileResponse(ROOT/'dist'/request.url.path.lstrip('/'))

app.mount('/vendor',StaticFiles(directory=ROOT/'dist/vendor'),name='website-vendor')

@app.get('/workspace.css')
@app.get('/workspace.js')
def workspace_assets(request:Request):return FileResponse(ROOT/'dist'/request.url.path.lstrip('/'))

app.mount('/static',StaticFiles(directory=ROOT/'frontend'),name='static')


observation_lock=threading.Lock()
class ObservationRequest(Strict):
    source:Literal['weather','fr24']='weather'
    airport:Literal['PIT','BOS','JFK','DCA','ORD','DTW']='PIT'
    consent:bool=False
class WeatherProjection(Revision):
    snapshot_id:str=Field(pattern=r'^[a-f0-9]{32}$')

@app.get('/api/observations/status')
def observation_status():return live_data.config()
@app.get('/api/observations')
def observation_history():return live_data.snapshots(store.desk_dir(DATA))[:12]
@app.post('/api/observations')
def observation_fetch(body:ObservationRequest):
    with observation_lock:
        try:return live_data.fetch(store.desk_dir(DATA),body.source,body.airport,body.consent)
        except ValueError as e:raise HTTPException(422,str(e))
@app.post('/api/scenarios/{ident}/weather-projection')
def apply_weather(ident:str,body:WeatherProjection):
    with lock:
        r=get(ident);fresh(r,body.revision);current_model(r)
        try:
            snapshot=live_data.read(store.desk_dir(DATA),body.snapshot_id)
            changes,decisions=live_data.projected_weather(snapshot)
        except ValueError as e:raise HTTPException(422,str(e))
        # Archive the actual previous state, including a prior approved recovery.
        r.setdefault('state_versions',[]).append({k:copy.deepcopy(r.get(k)) for k in ('revision','phase','scenario','current','disrupted','live_weather')})
        r['scenario']['disruptions']=[d for d in r['scenario']['disruptions'] if d['kind']!='weather']+changes
        r['live_weather']=snapshot;r['weather_projection']=decisions
        r['disrupted']=simulate(r['scenario']);r['current']=r['disrupted'];r['phase']='disrupted';r['revision']+=1
        event(r,'observed_weather_projected',{'snapshot_id':snapshot['id'],'new_revision':r['revision'],'decisions':decisions,'scope':'Live observation snapshot + synthetic weather-to-hold policy; prior experiments cannot be approved'})
        store.save_run(DATA,r);return r
