# Airport decade dataset (FlowBetter)

Official public aggregates for PIT · BOS · JFK · DCA · ORD · DTW (2016–2025).

**Source of truth:** the CSVs in this folder.  
**Teaching helper:** `storm_profiles.json` maps scenario profiles `snowzilla_ne` / `ord_winter` to BTS PREZIP flaw-day cancel counts and delay minutes (hold windows are synthetic evening-bank mocks sized from those values — not FAA closures).

| File | Contents |
|---|---|
| `major_flaw_days.csv` | Top disruption days (cancel/delay score) |
| `bts_daily_airport_metrics.csv` | Sample airport-days used for flaw mining |
| `bts_prezip_airport_year_2016-2025.csv` | Full PREZIP annual OTP |
| `bts_airport_year_enriched.csv` | OTP + FAA enplanements join |
| `faa_enplanements.csv` | FAA commercial-service enplanements |
| `noaa_ghcn_*.csv` / `noaa_station_crosswalk.csv` | NOAA weather annuals + stations |
| `storm_profiles.json` | Frontend/API-friendly storm profile pack |

Analysis write-up: [`../six-airport-decade-analysis.md`](../six-airport-decade-analysis.md).

The recovery sandbox loads this pack via `backend/decade_data.py` (with a copy under `backend/decade_pack/` for the decade analyst).
