"""FlowBetter FastAPI — ground-ops recovery desk (model v3)."""

from __future__ import annotations

import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import store
from .issues import MAX_ISSUES, catalog
from .simulator import MODEL_VERSION, generate, option_by_id

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.getenv('IROP_DATA', str(ROOT / 'data')))
FRONTEND = ROOT / 'frontend'

app = FastAPI(title='FlowBetter · Ground Ops Desk', version='0.3.0')
app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', 'testserver'])
lock = threading.RLock()


@app.middleware('http')
async def guard(request: Request, call_next):
    origin = request.headers.get('origin')
    allowed = os.getenv(
        'IROP_ORIGINS',
        'http://127.0.0.1:8010,http://localhost:8010,http://127.0.0.1:8011,http://localhost:8011',
    ).split(',')
    if request.method not in ('GET', 'HEAD', 'OPTIONS') and origin and origin not in allowed:
        return Response('Cross-origin writes forbidden', status_code=403)
    try:
        store.set_desk(request.headers.get('x-irop-desk'))
    except ValueError as exc:
        return Response(str(exc), status_code=400)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-IROP-Desk'] = store.get_desk()
    return response


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class ScenarioRequest(Strict):
    seed: int = Field(default=42, ge=0, le=999999, strict=True)
    issue_ids: List[str] = Field(min_length=1, max_length=MAX_ISSUES)


class ApproveRequest(Strict):
    option_id: str
    confirm: bool = False


def get(ident: str) -> dict:
    run = store.get_run(DATA, ident)
    if not run:
        raise HTTPException(404, 'Scenario not found in this desk')
    return run


def event(run: dict, action: str, data: dict) -> None:
    run.setdefault('events', []).append({
        'created': datetime.now(timezone.utc).isoformat(),
        'action': action,
        'data': data,
    })


@app.get('/api/health')
@app.get('/api/status')
def status() -> dict:
    return {
        'ok': True,
        'status': 'ok',
        'service': 'flow-better',
        'mode': 'ground_ops_desk',
        'model_version': MODEL_VERSION,
        'desk': store.get_desk(),
        'max_issues': MAX_ISSUES,
        'issue_count': len(catalog()['issues']),
    }


@app.get('/api/issues')
def list_issues() -> dict:
    return catalog()


@app.get('/api/scenarios')
def history() -> list:
    return store.list_run_summaries(DATA)


@app.get('/api/scenarios/{ident}')
def detail(ident: str) -> dict:
    return get(ident)


@app.post('/api/scenarios')
def create(body: ScenarioRequest) -> dict:
    try:
        scenario = generate(seed=body.seed, issue_ids=body.issue_ids)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    titles = [i['title'] for i in scenario['issues']]
    run = {
        'id': uuid.uuid4().hex,
        'name': ' · '.join(titles[:2]) + (f' +{len(titles) - 2}' if len(titles) > 2 else ''),
        'created': datetime.now(timezone.utc).isoformat(),
        'seed': body.seed,
        'revision': 1,
        'phase': 'options',
        'model_version': MODEL_VERSION,
        'issue_ids': scenario['issue_ids'],
        'issues': scenario['issues'],
        'ground': scenario['ground'],
        'situation': scenario['situation'],
        'options': scenario['options'],
        'selected_option_id': None,
        'decision': None,
        'events': [],
        'scope': scenario.get('scope'),
        'faa_source': scenario.get('faa_source'),
    }
    event(run, 'scenario_generated', {
        'seed': body.seed,
        'issue_ids': body.issue_ids,
        'option_count': len(run['options']),
        'feasible': sum(1 for o in run['options'] if o['feasible']),
    })
    store.save_run(DATA, run)
    return run


@app.post('/api/scenarios/{ident}/approve')
def approve(ident: str, body: ApproveRequest) -> dict:
    with lock:
        run = get(ident)
        if run.get('model_version') != MODEL_VERSION:
            raise HTTPException(409, 'Archived model — generate a new ground-ops scenario')
        if not body.confirm:
            raise HTTPException(422, 'Explicit simulation approval required')
        if run.get('phase') != 'options':
            raise HTTPException(409, 'Scenario already decided')

        option = option_by_id(run, body.option_id)
        if not option:
            raise HTTPException(400, f'Unknown option_id: {body.option_id}')
        if not option.get('feasible'):
            raise HTTPException(409, 'Option is blocked in this scenario')

        run['selected_option_id'] = body.option_id
        run['decision'] = {
            'option_id': option['id'],
            'title': option['title'],
            'feasible': True,
            'cost': option['cost'],
            'passenger_delay_minutes': option['passenger_delay_minutes'],
            'missed_connecting_passengers': option['missed_connecting_passengers'],
            'flights_cancelled': option.get('flights_cancelled', []),
            'people': option.get('people'),
            'money_breakdown': option.get('money_breakdown'),
            'regulation': option.get('regulation'),
            'tradeoffs': option.get('tradeoffs'),
        }
        run['phase'] = 'done'
        run['revision'] = int(run.get('revision', 1)) + 1
        event(run, 'simulation_approved', {
            'option_id': body.option_id,
            'cost': option['cost'],
            'scope': 'Simulation only',
        })
        store.save_run(DATA, run)
        return run


@app.get('/')
def home() -> FileResponse:
    return FileResponse(FRONTEND / 'index.html')


app.mount('/static', StaticFiles(directory=str(FRONTEND)), name='static')
