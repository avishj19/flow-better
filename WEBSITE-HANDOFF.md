# Current integration status

The website now embeds the full Python-backed recovery workspace. Read [INTEGRATION-HANDOFF.md](INTEGRATION-HANDOFF.md) for current run/deployment instructions and the live backend connection requirement. The original narrative below documents the initial version.

# FlowBetter airport website

The airport-facing website is authored in `dist/`. It uses the existing FlowBetter name and ✳ wordmark treatment, an original airport illustration, and repository-derived synthetic recovery results. The original simulator and frontend remain intact; the Python app now serves the new website at `/` and the full recovery desk at `/desk`.

## Edit and run

- `dist/content.js`: hero copy, story chapters, recovery strategy descriptions and saved scenario measures.
- `dist/index.html`: other website copy, navigation, assumptions and links.
- `dist/site.css`: shared design tokens, layout, responsive rules and motion fallbacks.
- `dist/site.js`: scroll choreography, accessible strategy tabs and scenario disclosure.
- `dist/style-tile.html`: editable design board using the same stylesheet and image.
- `brand/wordmark.svg`: editable text-based SVG preserving the repo's ✳ identity. Uses Manrope with Arial fallback; not a newly invented logo.
- `brand/airport-hero-master.png`: original full-resolution generated asset.

For the website with live flight data, run `npm run preview:website` and open http://127.0.0.1:8024. Run `npm run build` to produce the Cloudflare Worker and embedded static assets. The preserved React dashboard uses `npm run build:dashboard`.
For the complete local simulator, install `requirements.txt` in a virtual environment and run `python -m uvicorn backend.app:app --host 127.0.0.1 --port 8011`. The website adds an Open recovery desk link when a local API is available; the dashboard is at http://127.0.0.1:8011/desk. The hosted website does not host the Python service or expose simulation writes.

## Direction and production decisions

Audience: airport operations teams discussing disruption recovery with airline and ground-handling partners. No new airport-management, real dispatch, or gate-allocation capability is claimed. Explorer values reproduce README seed-42 model-v2 results; they are saved examples, not browser-side recalculation. Selecting a strategy does not approve it. No fake client names, testimonials or performance claims were added.

Palette: midnight #071323, operations blue #101F33, signal blue #487FFF, ice #91B8FF, paper #F5F7FB. Type: Manrope and DM Sans from Google Fonts, with local sans-serif fallbacks.

Motion was revised after the user requested preserving their 10 Higgsfield credits. A single Higgsfield still request was rejected with `Requires basic plan or higher` and returned no job. No further Higgsfield jobs were submitted. The user authorized built-in image processing, so the completed still was made through built-in imagegen. No original video or frame sequence exists or is required by this revised implementation.

The final story is a still-image camera move, not simulated takeoff footage. A pinned stage presents disruption, ripple effects, and recovery, with progressive operational signal cards. Desktop active pinned travel is 4.5 viewport heights (550vh stage wrapper minus 100vh visible stage); mobile is approximately 3.7. Chapters change at 31% and 65%. Camera motion uses piecewise progress, including initial and final holds. Scrolling is native and reversible; there is a skip link. Reduced-motion CSS removes pinning, shows all chapters, and disables transitions. The single 115,094-byte WebP also provides a lightweight constrained-device presentation, with no frame decoding queue.

## Asset prompt and provenance

Built-in imagegen, one original 1672 × 941 PNG, downscaled only if needed and encoded as WebP at quality 86 (actual delivered dimensions remain 1672 × 941). No stock image or real airport identity is implied. Metadata labels the airport scene illustrative.

Exact prompt:

> Use case: photorealistic-natural. Asset type: 16:9 cinematic airport operations website hero still for parallax. Create one premium photoreal aviation editorial photograph: broad elevated overhead-oblique view across a wet airport at blue hour. ONE large unbranded white twin-engine passenger aircraft with deep navy tail occupies the right half, all aircraft parts within frame, geometrically correct wings, grounded wheels, nose facing right. Distant terminal buildings and lights in the right background, runway and restrained electric-blue taxiway lights stretch into distance. Left 45% is quiet open dark navy sky and tarmac with minimal visual detail, reserved for HTML headings. Deep navy dusk clouds, subtle wet runway reflections, realistic airport scale, expensive cinematic photography and detailed believable materials. Composition must feel expansive, with aircraft prominent at x=72%, y=62%; view from above at an oblique angle, enough sky at top to establish blue hour. No text, logos, signage, interface, watermark, dramatic emergency, extra aircraft. Generate a landscape 16:9 image.

## Validation

- Browser visual checks at 1440×1000, 664×725 and 390×844.
- Ordinary forward/reverse scrolling switched chapters and operational overlays correctly.
- CFO and Operations tabs displayed their exact saved outcomes; scenario disclosure opened correctly.
- Mobile document width equaled 390 pixels at a 390-pixel viewport: no horizontal overflow.
- JavaScript syntax and repository JavaScript utility tests passed.
- Python route checks passed for landing, preserved dashboard, styles, scripts, design board and image.
- Reduced-motion layout was reviewed in source; OS preference emulation was not exercised in the browser.
- A standalone Playwright launch was unavailable under the local sandbox; visual QA used the supported in-app browser instead.

The deployed audience is owner-private. GitHub origin is preserved; the website source is pushed to Sites hosting separately, not to the user's GitHub default branch.

## Live flight map

Six airport views: JFK, ATL, ORD, LAX, DFW and LHR. Uses the public ADSB.lol point API through a same-origin server endpoint, with Leaflet 1.9.4 and attributed OpenStreetMap tiles. No API key or Higgsfield credits are used. All valid provider-reported positions within the selected radius are plotted, with search, altitude/speed/heading details, pause, refresh and ground/airborne filters. Nearby aircraft are not classified as arrivals or departures. Community coverage is incomplete.

Refresh is every 15 seconds while visible, subject to provider cooldown. Responses are cached for 15 seconds and concurrent identical requests are deduplicated. Requests are paced within a Worker instance; provider rate limits trigger a shared cooldown. Separate Worker instances cannot coordinate in-memory pacing. Errors show an explicit unavailable state; retained positions are marked stale. Positions over 120 seconds old are excluded; no synthetic live data or extrapolated movement is used.

Edit `dist/flight-map.js`, `dist/flight-map.css`, `dist/flight-data.js` and `server/flight-api.mjs`. `scripts/build-website.mjs` packages the assets and server endpoint into `dist/server/index.js`. The Python local service has an equivalent `/api/flight-map` route. Source and deployment have no credentials.
