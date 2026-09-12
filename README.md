# FlowBetter — airline recovery sandbox

A working hackathon pivot of TradeOps: generate a synthetic airline day, inject disruptions, compare recovery plans, inspect why they pass or fail, and approve a plan **only inside the simulation**.

**Local demo:** http://127.0.0.1:8010 · API documentation: http://127.0.0.1:8010/docs

## Run

Python 3.11+; no Node build step.

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8010
```

Use one server process (do not add `--workers`). The approval and workflow locks protect one process. For a different port, set `IROP_ORIGINS` to its exact localhost origins. `IROP_DATA` optionally sets a separate storage directory; the default is `./data`. `.env.example` is documentation, not an automatically loaded configuration file.

```sh
python -m pytest -q
```

The implementation was run using the existing TradeOps Python environment. A fresh environment can be installed with the commands above; that fresh-install path has not been separately exercised.

## Two-minute demo

1. **Generate schedule**, seed `42`: 60 flights and a validated on-time baseline.
2. **Inject disruptions**: two weather closures, one maintenance release delay, and one crew availability delay. Delays propagate through rotations and connecting passengers.
3. **Compare six recovery plans**: the local fixed planner actually simulates every option, verifies it independently, and ranks feasible options by modeled cost.
4. Inspect **Try a remote reserve**: evidence `remote:E0410` says the reserve is at BOS but its flight requires PIT. Approval is disabled.
5. Inspect **Protect connections** and switch the timeline to its preview. Review the cost and passing checks. Click **Approve in simulation**.
6. Reopen the saved scenario from history. The baseline, disrupted state, all experiments (including rejected candidates), approval record, and resulting schedule remain available.

The seed changes passenger loads and connection-group sizes. Network topology, rotation times and disruption templates are intentionally fixed for an explainable, reproducible pitch. Seed is an integer from 0 to 999999. Generating a new scenario never overwrites earlier ones.

## Observed synthetic result (seed 42)

| State / plan | Feasible under demo rules | Delayed flights | Passenger delay minutes | Missed connecting passengers | Modeled cost |
|---|---|---:|---:|---:|---:|
| Baseline | Yes | 0 | 0 | 0 | $0 |
| Disrupted / absorb delays | No: duty | 21 | 156,661 | 58 | $136,060.50 |
| Reserve crews | Yes | 12 | 114,269 | 58 | $105,174.50 |
| Aircraft + crews | Yes | 7 | 25,304 | 19 | $30,392 |
| Protect connections | Yes; ranked first | 9 | 30,062 | 0 | $29,341 |
| Remote reserve | No: position | 7 | 25,304 | 19 | $30,392 |
| Smaller reserve | No: seats | 7 | 25,304 | 19 | $30,392 |

These are computed simulator outputs, not observed airline outcomes or demonstrated financial savings. Cost and delay figures for infeasible plans are diagnostic only. Each option has 587 individual hard checks in the default scenario. The ranking is best among the tested fixed candidates, not a global optimum.

## Reused versus new

The isolated copy was exported from clean TradeOps commit `ba19b06a98a6130323935f3f416ac83564fc87c1`. The original repository and its port-8000 app were not modified. FlowBetter is maintained in its own repository; the TradeOps repository and its `main` branch are unchanged.

- **Adapted:** FastAPI/static frontend architecture; SQLite per-desk persistence, WAL, timeout and path locks from `backend/store.py`; bounded planner → tool executor → independent verifier → deterministic supervisor pattern from TradeOps `backend/agent_workflow.py`; pytest layout; localhost origin and host guards.
- **New:** schedule generator, cascading simulator, airline constraint verifier, connection-impact and cost model, six recovery candidates, revision/digest approval protection, coherent FlowBetter interface, network schematic, timeline, option evidence and airline-focused tests.
- **Local reference only (gitignored):** `legacy/` in the development workspace contains the committed TradeOps source and original README. The GitHub repository omits this folder; the original source is available at https://github.com/avishj19/tradeops/tree/ba19b06a98a6130323935f3f416ac83564fc87c1. It is not mounted, imported, or run by the IROP app. Its original tests require the original project layout and dependencies and are not part of the IROP test count.

## Architecture and state

`backend/simulator.py` owns deterministic generation, bounded plans, cascading execution, independent validation and ranking. `backend/agent_workflow.py` wraps this executor with either a transparent fixed plan or a Responses API function-calling planner. `backend/app.py` owns state transitions and approval. `backend/store.py` atomically saves each scenario document and lean history projection in SQLite. `frontend/` is plain JavaScript, HTML and responsive CSS.

State transition: `baseline (revision 0) → disrupted (revision 1) → recovered (revision 2)`. Experiments do not change the scenario revision. A successful approval requires explicit confirmation, the current revision, a completed experiment at that revision, and a feasible tested option. The server reruns the deterministic simulation and compares the complete option digest before applying it. A second or stale approval fails. Rejected approval attempts are recorded. All writes are serialized in the local server process.

Each scenario stores baseline/disrupted/current schedules, seed, inputs, experiment options, failed workflows, evidence, model explanation and tool trace, and audit events. Weather projection updates increment the revision again and retain the prior state in `state_versions`. Each workflow stage persists a snapshot. SQLite commits are atomic. If the server terminates during a workflow, the last stored workflow remains `running` and cannot be approved; run a new experiment after restart. History is local and is not an authenticated audit system.

The sidebar's desk workspace is sent as `X-IROP-Desk`. IDs are normalized and restricted to lowercase letters, numbers, underscores and hyphens. The default DB is `data/irop.db`; other desks use `data/desks/<id>/irop.db`. Scenario membership is checked on every read and write. Desk isolation is organizational separation, **not authentication**. This is a loopback-only, single-user prototype.

## Simulation assumptions

All data is synthetic. All times are integer minutes on one notional day with a shared clock; airport time zones and real flight durations are deliberately omitted. There are six airports (PIT hub; BOS, JFK, DCA, ORD, DTW), ten operating aircraft, six legs per aircraft, and synthetic crew groups treated as indivisible qualified teams. All flight durations are 60 minutes; scheduled legs start 100 minutes apart, with departures staggered eight minutes by rotation.

The simulator visits flights in scheduled-departure order. It assigns the chosen bounded resources, delays each operation until its aircraft and crew are available, moves departures out of closure windows (including arrival closures), and queues for modeled gates. The resulting arrival sets subsequent resource availability. A separate verifier sorts each resource's completed movements and checks its initial location, release availability, subsequent positions and overlaps/turns. Delays are never used to silently fix an impossible starting location; such plans are rejected.

| Demo constraint | Explicit simplification |
|---|---|
| Aircraft | Initial position, maintenance release, no overlap, 30-minute turnaround, seats ≥ booked load |
| Crew | Position, availability, no overlap, 20-minute transfer, matching aircraft type, 30-minute report lead, 15-minute postflight release |
| Crew workload | Duty ≤ 690 minutes from fixed report time; at most six segments; flight time ≤ 420 minutes; prior rest ≥ 600 minutes |
| Gates | Four at PIT and two per spoke; occupancy is 15 minutes before departure and 15 minutes after arrival, half-open intervals; remote parking is assumed between windows |
| Weather | No departure or arrival movement inside two fixed closure windows; flights can be delayed before takeoff to avoid arrival closures |
| Passengers | 16 connecting groups between different rotations at PIT; at least 35 minutes between arrival and departure; group counts fit booked flight loads |
| Schedule | Exactly one operation per original flight; fixed route/duration/load; no early departure |

The crew-only plan uses a later-report reserve on rotation 1 (report 08:00, available 08:30), plus the early reserve on rotation 3. The combined plan uses early-report reserves on both and swaps rotation 1 to the PIT reserve aircraft. Thus the crew-only option trades a larger delay for a modeled duty-feasible assignment. Connection protection adds holds for already simulated inbound groups when the required transfer time is within 60 minutes of the current earliest departure; later gate/weather effects can extend total delay. This heuristic is bounded, sequential and not guaranteed to preserve every connection for every seed or network modification.

**Crew legality is much more complex than a duty-hour cap.** This demo checks several synthetic crew dimensions but does not implement Part 117, cumulative duty, time-of-day tables, acclimatization, augmented crews, fatigue, contracts, deadheading, reserve rules, pairing construction, or real rest accounting. It makes no regulatory compliance claim.

Other omissions: cancellations, itinerary-level rebooking, denied boarding allocation, multi-day tails, maintenance routing, runway/ATC capacity, taxi/fuel constraints, gate compatibility, real positioning/ferry flights, crew composition, live operational/closure feeds. The invalid remote/small candidates are deliberate examples of why the verifier matters. No external operational action tool is present. Optional observations are described below.

## Cost and ranking

```
score = 0.50 × sum(arrival delay minutes × onboard booked passengers)
      + 250  × missed connecting passengers
      + 30   × sum(flight delay minutes)
      + 4500 × distinct reserve aircraft used
      + 1200 × distinct reserve crews used
```

Delay is equal at departure and arrival because durations stay fixed. Passenger delay counts flight segments, not unique trip-level passengers. A connecting passenger can appear on two segments; the missed-connection penalty is additional. No actual rebooking cost or final destination arrival is estimated. All dollar coefficients are illustrative constants. Feasible candidates sort by score, with plan key breaking ties. Infeasible candidates have no rank regardless of how attractive their score looks. The UI exposes every cost component.

## Evidence and optional model planner

Evidence is scoped to a scenario experiment and candidate: e.g. `remote:E0410`. IDs are deterministic sequential check IDs within a plan evaluation, not globally unique records. Always retain the scenario ID, experiment ID and revision when citing an ID. Each evidence row has constraint kind, subject, pass/fail and observed detail. The UI shows these exact rows. An evidence ID can change if the generator or verifier changes.

Local mode executes all six fixed plans without an LLM. Live mode lets the model choose safe simulations after `inspect_scenario`. At least two distinct options must be compared. Only `inspect_scenario` and `simulate_recovery` are exposed. Tool schemas reject arbitrary inputs; each candidate can run once. The supervisor ranks only tested candidates.

To enable live mode, set `OPENAI_API_KEY` and the retained compatibility variable `TRADEOPS_AI_MODEL` on the server, choosing a Responses model available in your account that supports function calls. Restart the server and check the explicit consent box. Keys remain on the server. Tool results contain aggregate counts, costs, grouped check results and sample evidence IDs, not raw flight/crew/passenger rows. Provider requests set `store:false` and request `reasoning.encrypted_content`; encrypted reasoning items are passed back during the loop and are not displayed as reasoning traces. This setting is not a promise of zero provider retention.

Limits: six model turns, eight tool calls, six distinct plans, 45-second timeout per provider request, 1,800 output tokens per turn. No shell, real flight mutations, arbitrary solver inputs, or approval tools are exposed. Explanations must cite at least one evidence ID actually sent in a tool result; unknown/unobserved citations stop the workflow. Citation membership does **not** prove that every prose claim is semantically correct. The explanation is advisory, and the server's independently verified ranking and approval checks always control the outcome.

No provider credentials were configured for this implementation. The live integration was exercised with scripted provider responses and a checked HTTP request contract; an actual provider run still requires server configuration and consent. Provider failures persist as failures and never silently become local or pretend live results.

## Verification and debugging

- IROP pytest suite: **53 passed**, with two upstream Starlette/AnyIO deprecation warnings in the reused Python environment.
- Tests cover reproducible baselines across six seeds; cascades and missed connections; all six candidates; cost/ranking; aircraft and crew positions, overlap and turns; duty/rest/segments/flight time/qualification; gate, weather, seats and coverage; desk/origin boundaries; infeasible, stale, changed-input and duplicate concurrent approvals; model tool ordering, arguments, duplicate calls, budgets, aggregate-only output, encrypted context, consent, citations, provider contract and failure persistence.
- Browser exercised: generate → inject → compare → inspect rejected remote aircraft → preview rotation → approve. Observed recovered revision 2 with 9 delayed flights, 30,062 passenger delay minutes and 0 missed connecting passengers.
- Reloaded state is accessible through scenario history. Local fixed mode remains clearly labeled throughout.

If a button fails, read the page status line and browser console, then check server output. `GET /api/status` reports the active desk and provider availability without exposing the key. A 403 on writes usually means the port's origin is absent from `IROP_ORIGINS`. A 409 indicates stale state or a blocked transition: reopen history, inspect the phase/revision, and use a current experiment. For provider failures, check the configured model, key availability and network; do not infer live availability from scripted tests. Inspect the persisted experiment trace for the last completed stage. Use a new `IROP_DATA` directory for a clean disposable demo.

## Official context

These sources inform the architecture/context, not the synthetic thresholds or dollar assumptions:

- [FAA weather-delay FAQ](https://www.faa.gov/nextgen/programs/weather/faq) explains weather impacts and traffic-management responses.
- [FAA flight/duty/rest FAQ](https://www.faa.gov/faq/what-are-crewmember-flight-and-duty-time-and-rest-requirements) distinguishes operational categories and applicable requirements.
- [FAA Part 117 advisory material](https://www.faa.gov/about/office_org/headquarters_offices/agc/practice_areas/regulations/part117/part117_general) illustrates the broader regulatory context deliberately omitted here.
- [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling) documents executing application functions and returning tool outputs.
- [OpenAI Responses request reference](https://developers.openai.com/api/reference/cli/resources/responses/methods/create) documents `store` and encrypted reasoning inclusion.


## Live observations (added September 12, 2026)

The **Real observations / synthetic decisions** panel supports manual, timestamped snapshots. There is no unattended polling or background API spend. `backend/live_data.py` uses official endpoints with TLS verification, a 20-second timeout and a 2 MB response bound. Provider errors are shown rather than replaced with fabricated live data. Snapshot JSON is saved atomically under the current desk's `observations/` directory. Tokens are never returned, logged or saved in snapshots.

### NOAA airport weather — connected and exercised

**Fetch airport weather** makes one public [Aviation Weather Center METAR API](https://aviationweather.gov/data/api/) request for KPIT, KBOS, KJFK, KDCA, KORD and KDTW. No key is required. Requests are cached for five minutes. Rows show source observation time, category, wind/gust, visibility and original METAR. Receipt time is not substituted for observation time. Missing or older-than-90-minute airport observations block projection; unknown categories and excessively future timestamps also fail closed.

**Project observed weather** replaces only the synthetic weather disruptions, retaining synthetic mechanical and crew disruptions. The explicit `demo-weather-v1` policy projects a hypothetical movement hold at 08:00 on the synthetic day: VFR=0, MVFR=15, IFR=30, LIFR=60 minutes; gusts ≥30 knots imply at least 45 minutes and thunderstorm weather implies at least 60 minutes. These are invented teaching thresholds, not FAA closures or an operational forecast. Current-time conditions are intentionally projected into a replay clock, not presented as observations at the synthetic flight times.

Every application archives the prior scenario/current/disrupted state, increments the scenario revision, and requires new recovery experiments. Previous experiments remain inspectable but cannot be approved against the new revision. Approval also rechecks observation age; an expired weather basis blocks approval until observations are refreshed and applied again. Fetching a snapshot alone does not change a scenario or invalidate it. A zero-hold projection is valid: clear weather must not invent a disruption.

### Flightradar24 — adapter ready, credentials still required

Set `FR24_API_TOKEN` in the server environment and restart. Use a separately provisioned [FR24 API subscription](https://fr24api.flightradar24.com/docs/getting-started); a normal Flightradar24 website subscription is not API access. Do not put the token in the frontend or chat. `FR24_ENVIRONMENT=production` is the default; set `sandbox` when using a sandbox key so static sandbox observations are visibly labeled. FR24 selects sandbox data via the key using the same endpoint; static sandbox data is not live.

Choose an airport and explicitly confirm API-credit use, then fetch one `/api/live/flight-positions/full` request, bounded to a small airport vicinity box and 50 tracked objects. A one-minute per-airport cache limits repeated clicks. The implementation uses the official `Authorization: Bearer …` and `Accept-Version: v1` headers. No scraping, unofficial website endpoints or login automation is used.

The panel shows registration, flight/callsign, type, altitude, ground speed and observation timestamp. Observations older than five minutes are marked stale. A speed ≤40 knots is only labeled **low speed; ground status unconfirmed**. The official position schema does not provide a verified available-at-gate inventory; ground vehicles may be present and parked aircraft may be absent. No observed aircraft is automatically assigned to a synthetic tail, crew, maintenance release or reserve pool. Airport delays/closures are not inferred from tracking density or speed. A real disruption feed or airline operational source would be an additional adapter.

The official FR24 request/schema and error paths were tested with scripted data; no token was available for an actual FR24 provider run. Public NOAA observations were retrieved successfully for all six airports. Their initial VFR categories correctly produced no modeled weather closures.

Additional tests cover weather parsing, cache behavior, projection weights, missing/stale/future/unknown observations, token and consent gates, FR24 bounds/headers/limits, uncertain ground state, provider failure, snapshot persistence, revision invalidation and expired-basis approval rejection. Total: 53 tests pass.

References: [official FR24 Python SDK and typed schemas](https://github.com/Flightradar24/fr24api-sdk-python), [FR24 FAQ](https://fr24api.flightradar24.com/docs/faq), [FR24 sandbox behavior](https://fr24api.flightradar24.com/docs/sandbox-environment), [AWC API guidance](https://aviationweather.gov/data/api/).
