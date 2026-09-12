# FlowBetter — ground-ops recovery desk

A simple **on-ground** airline IROP teaching sandbox for a PIT hub (with BOS / JFK / DCA / ORD / DTW destinations). Users pick catalog issues, see the airfield picture, then approve one recovery option with explicit money / people / regulation tradeoffs.

This is **not** a live Flightradar24 air-traffic dashboard. Scenarios are synthetic, sized from the six-airport decade stress pack (BTS / NOAA / FAA notes).

## Run

Python 3.11+:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8011
```

Open [FlowBetter](http://127.0.0.1:8011/) or [API docs](http://127.0.0.1:8011/docs). Ports 8010 and 8011 have default localhost origin permission. For another port set `IROP_ORIGINS` to its exact localhost origins. `IROP_DATA` optionally changes the storage directory.

```sh
python -m pytest -q
```

## Desk flow (model v3)

1. **Pick issues** — choose **1–4** from a catalog of **13** ground issues across weather, mechanical, human, airport, and network. Each issue shows a decade-analysis basis note.
2. **Ground picture** — see aircraft at gates, crew buffers, holds, blocked departures, connection risk, and alerts. Focus is on-ground ops only.
3. **Options & tradeoffs** — get **3–5** recovery options (absorb, cancel last bank, swap reserve, ferry spare, protect connections). Each shows cash, passenger delay minutes, people counts, money breakdown, regulation notes, and why blocked options fail.
4. **Approve in simulation** — pick one feasible option; history stores the decision per desk.

Example teaching combo: `wx_ne_cascade` + `crew_timeout` → absorb / ferry blocked; cancel-first stays feasible (matches decade cancel-cascade winters).

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/issues` | Catalog + max select (4) |
| POST | `/api/scenarios` | `{ seed, issue_ids[1..4] }` → situation + options |
| GET | `/api/scenarios/{id}` | Load run |
| POST | `/api/scenarios/{id}/approve` | `{ option_id, confirm: true }` |
| GET | `/api/scenarios` | Desk history summaries |
| GET | `/api/health` | Model version / mode |

Desk isolation uses the `X-IROP-Desk` header (same as before).

## Code map

- `backend/issues.py` — selectable issue catalog + decade basis text
- `backend/simulator.py` — ground picture + option builder (model v3)
- `backend/app.py` — FastAPI desk endpoints
- `backend/store.py` — SQLite per-desk persistence
- `frontend/` — three-step vanilla UI (no React recovery bundle required)

Crew legality remains a **simplified Part 117-inspired** teaching check, not an FAA determination. See [FAA Part 117](https://www.faa.gov/about/office_org/headquarters_offices/agc/practice_areas/regulations/part117).

Optional NOAA / FR24 adapters may still exist under `backend/live_data.py` for earlier experiments; they are **not** part of the main ground-ops desk UI.

SQLite history and desk IDs provide organization, not authentication. No real airline actions are exposed.
