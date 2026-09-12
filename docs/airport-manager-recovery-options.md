# PIT hub recovery desk — airport manager briefing (v2)

**Scenario:** synthetic seed 42 · 60 flights · four connected disruptions (T01 maintenance late, ORD de-icing signal, C01 duty squeeze, overnight PIT slot)  
**Lens:** airport / ops manager comparing **three strategies** on **four independent pillars** (no single weighted winner)  
**Scope:** FlowBetter simulation only — illustrative scores, not a live airline quote or FAA finding

## How the desk reads the pillars

| Pillar | What it measures (lower is better, except crew buffer) | Desk use |
|---|---|---|
| Financial cost | Delay × $100 + ferries × $10k + cancellations × $15k + reserve crews × $3k | Cash today |
| Passenger impact | Passenger-delay minutes + 250 × missed connections (cancellations assume 1,440m/pax) | Hub reputation / re-accommodation load |
| Network health | Soft overnight-position penalty ($20k pts per out-of-place tail at cutoff) | Tomorrow’s first bank |
| Crew buffer | Minutes remaining under modeled duty (hard gate if negative) | Approve / reject |

Feasible = every **hard** check passes (including crew). Pareto labels mark undominated feasible trade-offs. There is **no** combined score.

---

## Option scorecard (seed 42)

| Status | Strategy | Financial | Passenger pts | Network pts | Crew buffer | Desk verdict |
|---|---|---:|---:|---:|---:|---|
| REJECTED | The CFO Choice | **$31,500** (best cash) | 33,845 | 20,000 | **−95m illegal** | **Reject** — duty breach |
| FEASIBLE · Pareto · best passenger | The Loyalty Choice | $37,000 | **12,635** | 20,000 | +50m | **Approve if today matters** |
| FEASIBLE · Pareto · best network | The Operations Choice | $37,000 | 305,015 | **0** | +50m | **Approve if tomorrow matters** |

---

## Reasoning, option by option

### The CFO Choice — reject

**Move:** Wait for T01 maintenance; keep original metal and crew.  
**Why it looks good:** Lowest financial cost ($31.5k); no ferry or reserve spend.  
**Why the desk kills it:** Modeled crew duty overruns by ~95 minutes. An illegal plan is not a bargain. Soft network hit remains because the late recovery still leaves overnight position messy.

### The Loyalty Choice — passenger-first approve

**Move:** Ferry spare R01 PIT←DTW, reserve crew, operate the bank, ferry home.  
**Why pick it:** Best passenger pillar by a wide margin (12.6k vs 33.8k / 305k). Keeps the ORD bank flying; zero missed connections in this seed.  
**Cost of that choice:** Same $37k cash as Operations, but spent on ferries ($20k) + reserve crew ($3k) + residual delay ($14k). Network soft-penalty stays at 20k because the spare’s overnight story is imperfect.  
**Airport-manager framing:** Buy today’s passenger product and connection integrity when the terminal/rebooking desk cannot absorb a double cancellation.

### The Operations Choice — network-first approve

**Move:** Cancel the final ORD round trip; park the aircraft at PIT for tomorrow.  
**Why pick it:** Best network pillar (0). Crew stays legal. Cash matches Loyalty at $37k, but the spend is cancellation ($30k) + light delay ($7k) instead of ferries.  
**Cost of that choice:** Passenger pillar explodes (~305k) from assumed overnight delay on cancelled booked loads plus missed connections (CN17’s 20 pax in this seed).  
**Airport-manager framing:** Choose this when protecting tomorrow’s PIT departure bank / gate plan matters more than today’s ORD passenger hit.

---

## Decision rule

1. **Discard** any plan with a failed hard check (CFO here).  
2. Among feasible Pareto options, **do not average the pillars**—pick the hub priority:  
   - **Loyalty** → protect today’s passengers and connections.  
   - **Operations** → protect tomorrow’s aircraft position.  
3. Same financial ballpark ($37k) is intentional: the hard choice is passenger vs network, not “who is cheaper.”

Scores are simulator outputs for the three bounded strategies, not a claim of global optimum or real airline savings.
