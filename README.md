# FlowBetter — explainable airline recovery

**Airport-facing website:** the new cinematic landing page is served at `/`; the complete recovery dashboard is now at `/desk`. See [WEBSITE-HANDOFF.md](WEBSITE-HANDOFF.md) for site editing, assets, motion, and hosting details.

A dark-mode Airline IROP Recovery Dashboard: generate a synthetic day, apply four disruptions, compare three recovery strategies, inspect the underlying math, and approve a plan inside the simulation. Existing navigation, network, timeline and history structure are retained; React renders the recovery cards.

## Run

Python 3.11+:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8011
```

Open [FlowBetter](http://127.0.0.1:8011/) or [API docs](http://127.0.0.1:8011/docs). Ports 8010 and 8011 have default localhost origin permission. For another port set `IROP_ORIGINS` to its exact localhost origins. Run one server process; approval locks are process-local. `IROP_DATA` optionally changes the storage directory. `.env.example` is documentation, not automatically loaded.

The React bundle is included, so running the demo requires no Node build. After editing JSX or frontend utilities:

```sh
npm ci
npm run build
npm test
python -m pytest -q
```

## Demo: four disruptions, three decisions

1. Generate seed **42**: 60 flights, six airports, ten operating aircraft and a valid on-time baseline.
2. Apply four connected disruptions:
   - **Maintenance:** T01 is released at 20:45, 105 minutes after RX104's scheduled departure.
   - **Ground operations:** synthetic ORD Slack text adds 45 minutes to affected turnarounds.
   - **Crew:** C01's updated duty budget leaves only 45 minutes beyond its original final release.
   - **Overnight positioning:** T01 must reach PIT by 23:20 to protect tomorrow's first rotation.
3. Compare **CFO**, **Loyalty** and **Operations**. Inspect context, math citations, crew checks, overnight positions and the timeline.
4. CFO approval is disabled because its modeled crew duty exceeds the limit. Choose either feasible trade-off and approve in simulation. History preserves the decision and evidence.

Weather is optional, collapsed near the bottom. The default scenario requires no external provider. “Try a remote reserve” and the old six-option ranking are removed.

## Four-pillar model

`backend/simulator.py::calculate_recovery_scores` returns separate scores rather than a weighted dollar objective:

| Pillar | Formula / rule |
|---|---|
| Financial cost | Operated flight delay minutes × $100 + ferry flights × $10,000 + cancellations × $15,000 + distinct reserve crews used × $3,000 |
| Passenger impact | Sum of booked passengers × their delay minutes + missed connecting passengers × 250 points |
| Network health | 20,000 points per aircraft away from its planned overnight hub at its cutoff; in-transit counts as out of position |
| Crew buffer | Minimum remaining modeled duty minutes across operated crews, also expressed in hours; a negative buffer blocks approval |

Ferry slippage contributes to operating delay cost. Cancellations carry an assumed 1,440-minute passenger delay, no invented aircraft movement, and no operating-delay charge. Missed connections are counted as passengers, not itinerary groups. Network health is a soft objective, not an approval veto. Other aircraft/crew/gate hard constraints are independently checked.

**Crew legality is a simplified Part 117-inspired model, not actual FAA regulatory compliance.** The model checks fixed report/release times, duty, rest, segments, flight time, qualifications, position and overlap. Full Part 117 tables, acclimatization, augmented crews and extensions are not implemented. See [FAA Part 117 reference material](https://www.faa.gov/about/office_org/headquarters_offices/agc/practice_areas/regulations/part117/part117_general).

### Unstructured input changes the simulation

`unstructured_signals` preserves the original synthetic message and source window:

> Unstructured Input: Slack message from ORD Ground Ops: 'De-icing trucks are backed up, add 45 mins to any gate turnaround.'

A bounded deterministic parser extracts ORD and 45 minutes. Affected arrivals from 19:00 to 22:00 require a 75-minute turnaround (30 + 45). The resulting downstream delays affect money, passengers, crew buffer and overnight position. Unknown formats fail closed; this is not general NLP or a live Slack connector. The independent verifier re-derives required turnaround from the original input.

### Computed default results

| Strategy | Financial cost | Passenger points | Network penalty | Minimum crew buffer | Feasible |
|---|---:|---:|---:|---:|---|
| CFO — wait for original resources | $31,500 | 33,845 | 20,000 | −95 min | No |
| Loyalty — spare, reserve crew, two ferries | $37,000 | 12,635 | 20,000 | 50 min | Yes |
| Operations — cancel final ORD round trip | $37,000 | 305,015 | 0 | 50 min | Yes |

These are synthetic outcomes, not observed airline results. CFO spends least but cannot be approved. Loyalty and Operations share financial cost here and trade passenger continuity against overnight positioning. The interface identifies non-dominated feasible strategies without selecting a hidden weighted winner. Changing the seed changes passenger loads, not the fixed topology or disruption template. `demo-results.json` contains reproducible model-v2 outputs.

## Components and architecture

- `frontend/components/RecoveryOptions.jsx`: React recovery cards, three impact bars, crew rejection, rationale/context/citations and approval controls.
- `frontend/scoring.js`: formatting, relative impact indicators and approval eligibility presentation utilities. Python remains authoritative.
- `frontend/app.js`: existing page workflow, selected schedule/evidence, connections, timeline and saved history.
- `backend/simulator.py`: generator, bounded strategies, propagation, four scores, independent validation and explainability.
- `backend/agent_workflow.py`: deterministic tool workflow or optional bounded OpenAI Responses planner. All three strategies must be evaluated; no auto-approval.
- `backend/analysis_agent.py` + `backend/decade_data.py`: on-demand **decade analyst** grounded in bundled BTS/FAA/NOAA CSVs under `backend/decade_pack/`. Local answers need no API key; optional live mode is consent-gated and tool-bounded. Does not auto-approve and does not poll in the background.
- `backend/app.py` / `backend/store.py`: revision/digest protection, API, atomic SQLite persistence and desk separation.

State moves baseline → disrupted → recovered. Approval requires a current completed experiment, explicit simulation approval, all hard checks passing and an unchanged rerun digest. Stale, duplicate or changed-input approvals fail. Older model-v1 scenarios remain inspectable in history; generate a new scenario to use model-v2 recovery.

All schedules are synthetic, use one shared notional clock and assume 60-minute flights. Aircraft turns are normally 30 minutes, crew transfers 20 minutes, connection transfers 35 minutes. Gate occupancy is modeled around arrivals/departures. Tomorrow's network impact is an overnight-position proxy, not a simulated next-day network. The three fixed strategies are not a global optimization search.

SQLite history and desk IDs provide organization, not authentication, until Auth0 is configured. This remains a simulation: no real airline actions are exposed.

## Optional Auth0 desk security

When `AUTH0_DOMAIN`, `AUTH0_AUDIENCE` and `AUTH0_CLIENT_ID` are set, the recovery desk stops trusting the `X-IROP-Desk` header. Operators sign in with Auth0 Universal Login (SPA + PKCE). Access tokens are validated on the FastAPI API with `auth0-fastapi-api`. The workspace is taken from the token: Auth0 Organization slug, the namespaced `https://flowbetter.app/desk` claim, or a per-user `u-` workspace.

| Permission | Who | What it unlocks |
|---|---|---|
| `read:scenarios` | Viewer | History, timeline, evidence |
| `write:scenarios` | Analyst | Generate, disrupt, compare, project weather |
| `fetch:observations` | Analyst | NOAA / FR24 snapshot fetch (FR24 token stays server-side) |
| `approve:recovery` | Approver | The only path that locks a simulation decision |

Approvals record the Auth0 `sub` and organization on the event. If an analyst tries to approve, the API returns `insufficient_scope` and the UI can send them through MFA step-up (`acr_values` + `max_age=0`). Configure a post-login Action so `approve:recovery` is only added after MFA. Enable RBAC and **Add Permissions in the Access Token** on the Auth0 API.

Create an Auth0 **API** with identifier `https://flowbetter.local/api` and a **Single Page Application** (no client secret) whose callback, logout, and web origins match this origin (`http://127.0.0.1:8011`). Organizations map one airline/airport OCC to one isolated SQLite desk. Local demo without those env vars stays open on loopback.

## Optional OpenAI planner

Set server-side `OPENAI_API_KEY` and `TRADEOPS_AI_MODEL`, restart, then explicitly enable the UI consent checkbox. The Responses workflow exposes only bounded simulation tools and aggregate evidence, with six model turns, eight tool calls and a 45-second per-request timeout. It uses `store:false` and encrypted reasoning continuity. Explanation citations must reference observed evidence IDs; this verifies citation membership, not every natural-language claim. Provider failures remain visible failures. Local mode labels its rationale as a deterministic translation of verified math; it does not pretend an LLM ran.

The **Decade analyst** panel (`/api/analysis/ask` and `/api/scenarios/{id}/analysis`) reuses the same credential pair for an optional live ask. Default local mode answers from the packed decade CSVs (OTP ranks, weather risk, flaw days, COVID traffic, scenario↔pillar context). Live asks send only aggregate pack query results, never raw schedule rows.

No actual OpenAI provider run was performed for this refactor; scripted integration and request-contract tests cover that path.

## Verification

Backend tests and three JavaScript utility tests cover the four-pillar model plus optional Auth0 desk isolation. Coverage includes formula arithmetic, text-to-delay counterfactuals, all three trade-offs, cancellation/ferry continuity, modeled hard constraints, stale/concurrent approvals, legacy scenario guards, planner bounds/citations and live-data adapter failures. Backend tests report two upstream Starlette/AnyIO warnings. The Python suite used the existing local Python environment; a fresh dependency installation has not been separately exercised.

The app originated as an isolated TradeOps adaptation; the original TradeOps project remains unchanged. Local `legacy/`, runtime data, credentials, build dependencies and working files are ignored by Git.

## Live observations (added September 12, 2026)

The collapsed **Optional live airport data** panel supports manual, timestamped snapshots. There is no unattended polling or background API spend. `backend/live_data.py` uses official endpoints with TLS verification, a 20-second timeout and a 2 MB response bound. Provider errors are shown rather than replaced with fabricated live data. Snapshot JSON is saved atomically under the current desk's `observations/` directory. Tokens are never returned, logged or saved in snapshots.

### NOAA airport weather — connected and exercised

**Fetch airport weather** makes one public [Aviation Weather Center METAR API](https://aviationweather.gov/data/api/) request for KPIT, KBOS, KJFK, KDCA, KORD and KDTW. No key is required. Requests are cached for five minutes. Rows show source observation time, category, wind/gust, visibility and original METAR. Receipt time is not substituted for observation time. Missing or older-than-90-minute airport observations block projection; unknown categories and excessively future timestamps also fail closed.

**Project observed weather** replaces only the synthetic weather disruptions, retaining synthetic mechanical and crew disruptions. The explicit `demo-weather-v1` policy projects a hypothetical movement hold at 19:00 on the synthetic day: VFR=0, MVFR=15, IFR=30, LIFR=60 minutes; gusts ≥30 knots imply at least 45 minutes and thunderstorm weather implies at least 60 minutes. These are invented teaching thresholds, not FAA closures or an operational forecast. Current-time conditions are intentionally projected into a replay clock, not presented as observations at the synthetic flight times.

Every application archives the prior scenario/current/disrupted state, increments the scenario revision, and requires new recovery experiments. Previous experiments remain inspectable but cannot be approved against the new revision. Approval also rechecks observation age; an expired weather basis blocks approval until observations are refreshed and applied again. Fetching a snapshot alone does not change a scenario or invalidate it. A zero-hold projection is valid: clear weather must not invent a disruption.

### Flightradar24 — adapter ready, credentials still required

Set `FR24_API_TOKEN` in the server environment and restart. Use a separately provisioned [FR24 API subscription](https://fr24api.flightradar24.com/docs/getting-started); a normal Flightradar24 website subscription is not API access. Do not put the token in the frontend or chat. `FR24_ENVIRONMENT=production` is the default; set `sandbox` when using a sandbox key so static sandbox observations are visibly labeled. FR24 selects sandbox data via the key using the same endpoint; static sandbox data is not live.

Choose an airport and explicitly confirm API-credit use, then fetch one `/api/live/flight-positions/full` request, bounded to a small airport vicinity box and 50 tracked objects. A one-minute per-airport cache limits repeated clicks. The implementation uses the official `Authorization: Bearer …` and `Accept-Version: v1` headers. No scraping, unofficial website endpoints or login automation is used.

The panel shows registration, flight/callsign, type, altitude, ground speed and observation timestamp. Observations older than five minutes are marked stale. A speed ≤40 knots is only labeled **low speed; ground status unconfirmed**. The official position schema does not provide a verified available-at-gate inventory; ground vehicles may be present and parked aircraft may be absent. No observed aircraft is automatically assigned to a synthetic tail, crew, maintenance release or reserve pool. Airport delays/closures are not inferred from tracking density or speed. A real disruption feed or airline operational source would be an additional adapter.

The official FR24 request/schema and error paths were tested with scripted data; no token was available for an actual FR24 provider run. Public NOAA observations were retrieved successfully for all six airports. Their initial VFR categories correctly produced no modeled weather closures.

Additional tests cover weather parsing, cache behavior, projection weights, missing/stale/future/unknown observations, token and consent gates, FR24 bounds/headers/limits, uncertain ground state, provider failure, snapshot persistence, revision invalidation and expired-basis approval rejection. The complete backend suite now has 55 passing tests.

References: [official FR24 Python SDK and typed schemas](https://github.com/Flightradar24/fr24api-sdk-python), [FR24 FAQ](https://fr24api.flightradar24.com/docs/faq), [FR24 sandbox behavior](https://fr24api.flightradar24.com/docs/sandbox-environment), [AWC API guidance](https://aviationweather.gov/data/api/).
