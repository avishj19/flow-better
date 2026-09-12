# Integrated FlowBetter

All seven GitHub feature branches are merged, preserving their history. The new airport website is the main frontend. `frontend/index.html` was removed; its complete working controls now live in `dist/simulation.html`, embedded at `/#simulation` and available full-screen at `/simulation`. `/desk` redirects into the new website. Existing functional frontend modules remain shared implementation, not a second website.

## Included branch functionality

| Branch | Integrated capability |
| --- | --- |
| cursor/live-weather-visuals-6e6b | Seed validation/randomization, NOAA cards, weather overlay, explicit projection |
| cursor/airport-manager-recovery-options-7c11 | Four-pillar airport manager briefing and explanations |
| cursor/virtual-overnight-hub-agent-1cf4 | Network map, overnight hubs, local agent, ferry and cutoff context |
| cursor/airport-decade-storm-analysis-f706 | Standard / Northeast winter / ORD winter profile inputs and cancellation-heavy validation |
| cursor/decade-analysis-agent-da3a | BTS/FAA/NOAA packaged evidence, decade analyst, local or consented live mode |
| cursor/auth0-recovery-desk-security-d57c | Optional identity, token validation, desk isolation, permission checks and approval attribution |
| cursor/recovery-desk-fixes-461c | Desk error handling and favicon; newer fixes retained |

Preserved: generation, disruption injection, all three recovery strategies, math/evidence, preview timeline, rotations, passenger connections, hard constraints, explicit approval, revision/digest guards, SQLite history, observation snapshots, weather projection, FR24 consent, optional OpenAI and Auth0. Live flight map remains independent of synthetic simulation.

## Run the complete app

Use Python 3.11+ and install `requirements.txt`, then `python -m uvicorn backend.app:app --host 127.0.0.1 --port 8011`. Open `http://127.0.0.1:8011/`. The checked-in React bundle is ready to run. `npm run build:dashboard` rebuilds it after JSX changes. `npm run build` packages the Sites Worker and all website/desk assets.

## Remaining hosted-service connection

The Sites URL runs JavaScript Workers; it cannot execute this repository's Python/FastAPI/SQLite service. The exact Python engine is retained rather than replaced with a different browser calculation. The published interface explicitly reports an unavailable simulation service until a persistent Python deployment is connected. No synthetic fallback is substituted for server results.

`Dockerfile` runs the full application with one server process. Deploy it on a Python/container host, attach persistent storage at `/data`, and configure:

- `IROP_ALLOWED_HOSTS`: exact backend hostname, comma separated if needed.
- `IROP_ORIGINS`: exact backend HTTPS origin (the Sites gateway rewrites Origin to this).
- `IROP_PROXY_TOKEN`: a generated secret shared only with the Sites server configuration. Do not commit it.
- `IROP_DATA=/data`: persistent state. Run one worker because approval locking is process-local.

Then configure Sites server values `SIMULATION_API_URL=https://<backend-host>` and `SIMULATION_PROXY_TOKEN` equal to the backend gateway secret. The gateway forwards only recognized API routes, preserves Auth0 access tokens, rejects cross-origin requests, and never returns its secret. `/healthz` is a public liveness probe without scenario data. The backend's API requires the gateway secret when configured; direct browser access to that backend's API will intentionally be rejected.

Optional Auth0 / OpenAI / FR24 settings stay on the Python backend. Auth0 callback must be the public Sites origin plus `/simulation`; logout and web origins must match the public Sites origin; preserve all role/permission rules. Without Auth0, the site must remain owner-private because desk IDs are organizational, not authentication. No account or service was purchased and no credentials were invented.

## Verification

79 existing and merged Python tests pass, including simulation, live-data adapters, decade analysis, overnight agent and Auth0 permission contracts. Additional integration checks exercise route forwarding and disabled-service behavior. Local browser checks exercise the embedded generation/disruption/comparison flow. External Auth0/OpenAI/FR24 provider calls require the corresponding configured accounts and were not exercised.
