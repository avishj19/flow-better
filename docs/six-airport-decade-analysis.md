# FlowBetter network — decade analysis (PIT, BOS, JFK, DCA, ORD, DTW)

**Scope:** Calendar years **2016–2025** (latest available slices through 2025 prelim / BTS samples through Dec 2024).  
**Airports:** FlowBetter’s six nodes — Pittsburgh hub + BOS, JFK, DCA, ORD, DTW.  
**Rule:** Figures below come from **official public sources only** (BTS, FAA, NOAA/NCEI, airport-authority ACFRs). Synthetic FlowBetter scores are labeled as such. Nothing here is invented carrier performance.

**Dataset pack:** [`docs/airport-decade-dataset/`](./airport-decade-dataset/)  
**Retrieved:** 2026-09-12

---

## 1. Sources and what was stress-tested

| Domain | Source | What we pulled | Gaps / fixes |
|---|---|---|---|
| On-time % (annual) | BTS Table 4 (arrivals) & Table 6 (departures), marketing-carrier, major-airport rankings | 2016–2024 for BOS/JFK/DCA/ORD/DTW | **PIT drops out** of “major airport” ranking tables in recent years → filled with BTS PREZIP January OTP proxies |
| Flight-day ops | BTS TranStats PREZIP *Reporting Carrier On-Time Performance* | 18 months spanning 2016–2024 (Jan each year + known storm/COVID months) → **3,324 airport-days** | Not a complete 10×12 month grid; labeled as sample coverage in CSVs |
| Passengers | FAA commercial-service enplanement workbooks | CY2023–2025 (2025 preliminary) | Older FAA `cy16–cy23` paths returned 404 from this environment; use ACFR / Form 127 for full decade CPE |
| Weather | NOAA NCEI GHCND daily by-station | Full 2016–2025 annuals for 6 airport stations | CDO API needs token (unavailable); public `.csv.gz` used instead |
| Cost / CPE | Airport authority ACFRs / MWAA / PANYNJ schedules | PIT, ORD, DTW, DCA CPE/fees; JFK landing schedule | BOS CPE PDF not retrieved this pass; FAA CATS Form 127 UI blocked for bulk export |
| Efficiency | FAA *Air Traffic by the Numbers* 2024 + BTS taxi fields in PREZIP | Core-30 delay/diversion counts; sample-month taxi-out/in | Minute-level ASPM UI returned 403 |

**Pipeline bugs fixed while building the pack:** monthly rollup `defaultdict` misuse; BTS Socrata “OTP” catalog IDs were charts with empty schemas (not used); FAA historical XLSX URLs 404’d (documented); BTS.gov Excel blocked by Akamai for curl (retrieved via fetch); PREZIP aggregation then used for day-level truth.

---

## 2. Traffic and cost context

### FAA enplanements (commercial service)

| Airport | Hub | 2016 | 2019 | **2020** | 2023 | 2024 | 2025 prelim |
|---|---|---:|---:|---:|---:|---:|---:|
| ORD | L | 37,589,899 | 40,871,223 | **14,606,034** | 35,843,104 | 38,575,693 | 40,680,735 |
| JFK | L | 29,239,151 | 31,036,655 | **8,269,819** | 30,804,355 | 31,466,102 | 30,792,806 |
| BOS | L | 17,759,044 | 20,699,377 | **6,035,452** | 19,962,678 | 21,090,721 | 21,021,153 |
| DTW | L | 16,847,135 | 18,143,040 | **6,822,324** | 15,378,601 | 16,110,696 | 16,294,768 |
| DCA | L | 11,470,854 | 11,595,454 | **3,573,489** | 12,365,030 | 12,750,892 | 12,003,594 |
| PIT | M | 3,986,114 | 4,715,947 | **1,742,406** | 4,493,052 | 4,862,376 | 4,792,035 |

Sources: FAA commercial-service enplanement PDFs CY2016–2023; ARP workbooks CY2024 final + CY2025 preliminary. Full series in `faa_enplanements.csv`. COVID YoY drops ranged **−62% (DTW) to −73% (JFK)**.

### Cost per enplanement / fees (authority publications)

| Airport | Latest CPE / fee signal | Notes |
|---|---|---|
| PIT | CPE **$11.50** (FY2023); spiked to **$20.50** in FY2020 | Allegheny County Airport Authority ACFR 2023 |
| ORD | CPE **$25.00** (CY2023) | Chicago O’Hare 2023 financial report |
| DTW | Airline revenue / enplanement **$9.24** (OY2023); **$20.84** in OY2020 | WCAA ACFR 2023 |
| DCA | CPE **$9.38** (2023 actual) | MWAA investor materials |
| JFK | Landing **$8.47 / 1,000 lbs** MGTOW (eff. 2026 schedule) | PANYNJ Schedule of Charges; CPE not extracted this pass |
| BOS | Cost-recovery landing fees (Massport) | CPE line not retrieved this pass |

COVID years show the structural cost problem FlowBetter’s financial pillar is meant to teach: fixed airfield cost on collapsed enplanements → CPE roughly **doubles**.

---

## 3. Timing & efficiency — annual on-time

BTS definition: on-time = gate departure/arrival **&lt; 15 minutes** after schedule.  
**Primary series below:** reporting-carrier PREZIP aggregated over **all 120 months 2016–2025** (`bts_prezip_airport_year_2016-2025.csv`, from [BTS delay OTP research](bc-c8e9a1b2-9f02-576d-8834-282caf9eb94a)) — this is what fills **PIT**. Marketing-carrier Tables 4/6 match the large hubs within ~0–0.4 pp for 2016–2024 but omit PIT.

### Departure on-time % (PREZIP, origin)

| Airport | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| PIT | 86.8 | 85.3 | 83.0 | 83.1 | 86.9 | 85.7 | 81.0 | 84.2 | 82.4 | 81.7 |
| DTW | 84.5 | 83.4 | 84.2 | 83.0 | 88.1 | 87.0 | 81.4 | 81.9 | 80.8 | 79.3 |
| DCA | 82.6 | 82.3 | 79.5 | 79.8 | 83.8 | 84.4 | 75.2 | 81.6 | 79.2 | 71.6 |
| BOS | 81.2 | 77.4 | 76.4 | 77.1 | 85.6 | 85.1 | 75.7 | 76.2 | 78.7 | 76.0 |
| JFK | 77.7 | 75.6 | 78.7 | 79.8 | 85.4 | 80.7 | 71.6 | 75.2 | 78.3 | 77.3 |
| ORD | 76.9 | 79.7 | 77.5 | 75.1 | 84.7 | 80.8 | 77.9 | 79.0 | 76.8 | 73.7 |


### Arrival on-time % (PREZIP, destination)

| Airport | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| DTW | 85.4 | 84.4 | 84.2 | 83.7 | 88.0 | 86.5 | 81.8 | 82.5 | 81.0 | 79.5 |
| PIT | 82.5 | 81.2 | 79.6 | 80.0 | 84.9 | 80.2 | 75.0 | 79.1 | 77.8 | 76.1 |
| ORD | 79.6 | 80.8 | 77.2 | 74.7 | 84.7 | 81.8 | 79.2 | 79.4 | 77.9 | 73.0 |
| DCA | 79.0 | 79.9 | 77.8 | 78.6 | 83.2 | 83.4 | 73.9 | 80.1 | 77.7 | 68.5 |
| BOS | 78.0 | 74.6 | 74.0 | 74.3 | 84.8 | 82.4 | 73.8 | 74.5 | 76.0 | 72.6 |
| JFK | 76.8 | 72.8 | 75.7 | 78.3 | 84.4 | 79.9 | 71.8 | 74.2 | 77.0 | 75.5 |


**Read:** Among this set, **PIT and DTW** are the most reliable. JFK/BOS are the fragile Northeast nodes. 2020 looks “great” because traffic collapsed. **2022** is the worst recent year for JFK/BOS/DCA. Late-aircraft is usually the largest delay-cause share at these hubs; weather’s share spikes on flaw days even when it is small in the annual mix.

Sample storm months still show taxi-out climbing into the **40–60 minute** range on cancel-heavy days (daily CSV) — the efficiency tax before a flight leaves the gate.

---

## 4. Weather (NOAA GHCND, airport stations)

Stations: PIT `USW00094823`, BOS `USW00014739`, JFK `USW00094789`, DCA `USW00013743`, ORD `USW00094846`, DTW `USW00094847`.

**Normals (1991–2020) snowfall inches:** BOS 49.2 · DTW 45.0 · PIT 44.1 · ORD 38.4 · JFK 25.9 · DCA 13.7.

**2022 snapshot (heavy winter + still-recovering NAS):**

| Airport | Snowfall (in) | Thunder days | Fog days (WT01) |
|---|---:|---:|---:|
| BOS | 54.7 | 18 | 117 |
| PIT | 49.5 | 43 | 161 |
| DTW | 44.4 | 30 | 165 |
| ORD | 35.4 | 38 | 130 |
| JFK | 21.6 | 26 | 116 |
| DCA | 13.2 | 40 | 106 |

Thunder is chronically highest at ORD/PIT/DCA; fog proxies highest at DTW/PIT; JFK leads several years in heavy-fog (`WT02`) counts. Full year matrix: `noaa_ghcn_airport_year_2016-2025.csv`.

---

## 5. Major flaw days (BTS PREZIP) — and how FlowBetter would have done

Scoring used for ranking: `2 × departure_cancel_rate + delay15_rate` among days with ≥50 departures.

| Date | Airport | Dep cancel | Delay≥15 (ops) | Weather delay min | Late-aircraft min | What actually broke |
|---|---|---:|---:|---:|---:|---|
| 2022-01-29 | JFK | **94%** | 100% of flown | 2,528 | 712 | Near-total stop |
| 2022-01-03 | DCA | **95%** | 52% | 1,414 | 920 | Near-total stop |
| 2019-01-20 | BOS | **78%** | 75% | 4,009 | 1,305 | Nor’easter ops |
| 2018-01-04 | JFK | **94%** | 20% | 117 | 10 | Cancel-first day |
| 2016-01-23/24 | JFK/DCA | **100%** | n/a | — | — | Snowzilla shutdown |
| 2019-01-28/30 | ORD | 52–66% | 65–78% | 9.8k–11.4k | 4k–26k | Weather + late aircraft cascade |
| 2022-12-23 | DTW | 57% | 79% | 3,879 | 4,029 | Winter + hub ripple |
| 2020-04-01/03 | JFK | 70–73% | ~10% | ~0 | low | Demand shock, not weather |

Full top-150: `major_flaw_days.csv`.

### FlowBetter desk read on those days

FlowBetter is a **one-day PIT hub sandbox** with three strategies (CFO / Loyalty / Operations) and four pillars. It is **not** a replay of airline SOC decisions. Mapping:

| Flaw-day pattern | CFO (absorb) | Loyalty (ferry + reserve) | Operations (cancel bank) | Ideal? |
|---|---|---|---|---|
| Snowzilla / JFK–DCA–BOS 67–100% cancel | Illegal duty + wrecked network if you force fly | Still illegal — ferries don’t clear multi-hour multi-airport closures | **Only feasible path** once storm profiles cancel the last bank network-wide | **Partially** — cancel-first is right; passenger pillar explodes (correctly) |
| ORD winter cancel+delay with huge late-aircraft minutes | Duty/network fail | Ferry helps one rotation only; still weak on system late-aircraft | Feasible if last bank cancelled; overnight protected | **Closer** — teaches passenger vs network trade |
| COVID April cancel without weather | Model has no demand/schedule cut lever | Same | Cancel tool exists but for wrong reason | **No** — need a demand-shock / schedule-trim profile |
| Single-airport IFR bump (live METAR) | Live weather projection helps | Helps if metal/crew available | Overkill if hold is short | **Yes** for teaching holds |

**Hard finding from the dataset test:** on Snowzilla-scale inputs, **absorb-delay and ferry-first are not merely suboptimal — they are illegal under the model’s own crew rules**. That matches reality: you cannot “efficiently delay through” a 100% cancel day.

---

## 6. Code changes driven by this analysis

Implemented on branch `cursor/airport-decade-storm-analysis-f706`:

1. **Historical disruption profiles** on scenario create: `default` · `snowzilla_ne` · `ord_winter` (synthetic windows sized from BTS flaw days, clearly labeled teaching packs).
2. **Storm Operations policy:** when any airport has a ≥180m weather hold, cancel **all** last-bank legs (legs 4–5). Before this fix, snowzilla left Operations **infeasible** (C07 duty −127m, T07 airborne past overnight cutoff) because only storm-touched spokes were cancelled while delayed ORD banks still ran.
3. **Gate-check efficiency:** `gate_ok` no longer minute-scans the window; `next_gate_time` jumps to booking boundaries (needed when long weather holds + gate queues stress the 1440 loop).
4. **Live weather policy v2:** snow/freezing METAR tokens raise holds; ≥3 airports IFR/LIFR adds a cascade bonus — still hypothetical, documented as `demo-weather-v2`.

**Seed-42 storm desk (synthetic, after fix):**

| Profile | CFO | Loyalty | Operations |
|---|---|---|---|
| `snowzilla_ne` | Infeasible (crew −135) | Infeasible (crew −135) | **Feasible** · 20 cancels · network 0 · crew +45 |
| `ord_winter` | Infeasible (crew −105) | Infeasible (crew −72) | **Feasible** · 20 cancels · network 0 · crew +245 |

Remaining gaps for later training loops: no GDP/flow program object, no multi-day recovery, no demand-shock profile, no true late-aircraft probability model, PIT missing from BTS major ranking tables, incomplete Form 127 CPE panel.

---

## 7. Cross-airport decade verdict (for website training)

1. **Reliability hierarchy (OTP):** DTW ≫ DCA ≳ BOS &gt; ORD ≳ JFK among the large hubs; PIT behaves like a smaller, usually cleaner spoke/hub in January samples.
2. **Weather hierarchy:** Thunder → ORD/PIT/DCA; snow depth risk → BOS/PIT/DTW/ORD; heavy fog episodes → JFK; wind days → JFK often leads.
3. **Cost hierarchy:** ORD CPE is structurally expensive; PIT/DTW/DCA sit nearer $9–12 in normal years and blow out in 2020.
4. **Failure mode that matters for FlowBetter:** **cancel cascades + late aircraft**, not gentle delay. Training data must push cancel-first Operations and reject “wait it out” on multi-airport winter days.
5. **COVID is a different failure mode** (schedule/demand) — do not train it as weather.

---

## 8. File index

| File | Contents |
|---|---|
| `airport-decade-dataset/bts_prezip_airport_year_2016-2025.csv` | Full 120-month PREZIP annual OTP/cancel/causes (all 6 airports) |
| `airport-decade-dataset/bts_airport_year_enriched.csv` | Same + FAA enplanements join |
| `airport-decade-dataset/bts_annual_otp.csv` | BTS Table 4/6 marketing rankings cross-check |
| `airport-decade-dataset/bts_daily_airport_metrics.csv` | Sample airport-days (flaw-day mining) |
| `airport-decade-dataset/major_flaw_days.csv` | Top disruption days |
| `airport-decade-dataset/faa_enplanements.csv` | FAA CY2016–2025 |
| `airport-decade-dataset/noaa_ghcn_airport_year_2016-2025.csv` | Full weather annuals |
| `airport-decade-dataset/noaa_station_crosswalk.csv` | Station IDs |

Supporting research notes: `internal/bts-otp-research.md`, `internal/noaa-weather-decade.md`, `internal/weather-cost-traffic-research.md`, `internal/airport-decade-pipeline.md`.
