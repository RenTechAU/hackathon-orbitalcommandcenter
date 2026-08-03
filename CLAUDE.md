# CLAUDE.md

Project context for Claude Code. Read this before making changes.

## What this is

**Orbital Contact Broker** — hackathon project for *Memory Meets Motion*
(Frontier Tower SF, Aug 3 2026, 8-hour sprint, judging ~6:30 PM).

A satellite constellation that **negotiates for airtime**. Ground stations are
scarce and satellite passes overlap. When two satellites want the same dish,
advocate agents argue it out — and the system gets *fairer over time* because
it remembers who gave up their window last.

(Pivoted from a smart-home version at ~12:00. The negotiation engine is the
same; `git log main` has the original if you ever need it back.)

## The one thing that matters

The demo is two identical contentions with different outcomes:

```
contention 1  ->  no history, picks arbitrarily, RECORDS who yielded
contention 2  ->  "SAT-1 yielded at Svalbard last pass -- its turn"
```

That difference is the memory. **Every change must preserve this.** If a
refactor breaks the two-contention demo, revert it. Nothing else is as
important.

## Hard constraints from the judges

All four sponsor tools must be **load-bearing**. The problem statement says
verbatim: *"A one-line SDK import that's never called again will not count."*

| Layer | Tool | Role here | Status |
|---|---|---|---|
| Real-time | LaserData | Live orbital telemetry | ✅ real (local Laser Stack) |
| Memory | FalkorDB | Constellation graph + yield history | ✅ real (Docker, localhost:6379) |
| Multi-agent | Guild.ai | Advocate agents + mission-safety veto | ⬜ fallback (workspace ready) |
| Motion | RocketRide.ai | Issues the tasking command | ✅ real (live pipeline, receipt per action) |

Update the status column as each is wired. All four must be green before judging.

## Critical rule: do not invent SDK syntax

LaserData, RocketRide.ai and Guild.ai are new tools **not in your training
data**. Do NOT guess at their client init, method names, or auth flow. Plausible
-looking-but-fake API calls have already been identified as the single biggest
time sink for this project.

If a real code sample is not in `docs/SDK_NOTES.md`, stop and tell Jeremy to get
it from the sponsor's table. Adding a `TODO(sponsor table)` marker is the
correct action — writing a guess is not.

**One legitimate exception: the SDK's own shipped files.** `laser-sdk` installs
a complete type stub at `.venv/lib/python3.*/site-packages/laser_sdk/__init__.pyi`
(3,400 lines, every class and signature). Reading that is not guessing — it is
the most authoritative source there is, better than docs. Check for a `.pyi`,
`__init__.py`, or `--help` before declaring a vendor blocked. That is how
LaserData got wired without waiting for the table.

FalkorDB is different: it's an established Redis-based graph DB with real Cypher.
You may write Cypher freely.

## Architecture

```
LaserData  ->  FalkorDB  ->  Guild.ai  ->  RocketRide.ai
 (now)         (ever)        (decide)      (do)
```

Everything vendor-specific lives behind an adapter in `src/adapters/vendors.py`.
Three classes — `LiveFeed`, `Actuator`, `Council` — each with a `use_real` flag.
**Swap one adapter at a time. Never change more than one at once.**

## Graph schema (FalkorDB)

```cypher
(:Satellite     {name})
(:GroundStation {name})
(:Payload       {name, urgency})
(:Satellite)-[:IN_VIEW_OF {since}]->(:GroundStation)
(:Satellite)-[:LINKS_TO   {bandwidth_gbps}]->(:Satellite)  // the relay mesh
(:Satellite)-[:CARRIES]->(:Payload)
(:Satellite)-[:YIELDED    {station, ts}]->(:Satellite)     // memory that compounds
```

Two queries earn the graph database, for different reasons. **Preserve both.**

`yield_ledger()` — three hops, starting and ending at the same station node:
station → who sees it now → who yielded to whom → is the receiver still in
view. This is the memory that makes run 2 smarter than run 1.

`relay_path()` — `[:LINKS_TO*1..5]`, **variable-depth** traversal. A satellite
over open ocean sees no station, so it must bounce through the laser mesh, and
you don't know how many hops until you look. This is the one a SQL table
genuinely cannot do. Say "variable depth" out loud in the pitch.

## Layout

```
src/main.py             pipeline end to end
src/sim/telemetry.py    orbit sim + scripted demo beats
src/memory/constellation.py  FalkorDB schema, Cypher, fairness + relay queries
src/adapters/vendors.py the three SDK slots
src/agents/             Guild.ai agent definitions (empty until wired)
web/                    dashboard UI (see docs/CLAUDE_DESIGN_BRIEF.md)
docs/                   setup, architecture, demo script, SDK notes
```

## Working agreements

- **Always keep `python3 src/main.py` runnable with zero SDKs installed.** The
  fallback path is the safety net. If it breaks, the demo is at risk all day.
- Run it after every change. It takes one second.
- Small commits, push often. Laptops die at hackathons.
- Prefer editing the fallback logic over deleting it — it's the reference
  behaviour and the backup demo if a vendor SDK fails at 5 PM.
- No auth, no user accounts, no persistence layer beyond FalkorDB. Not scored.
- **Code freeze 5:00 PM.** After that: demo recording, README, pitch only.

## Context on the developer

Jeremy is early in his coding journey and working primarily through AI tools.
Bias toward: explaining *why* before *what*, small reviewable diffs, and running
the code to prove a change worked rather than asserting it. Don't produce large
refactors he can't review. If something fails, say so plainly rather than
patching around it.

**Use simple plain English.** Avoid jargon; when a technical term is
unavoidable, define it in one short phrase. Short sentences. Explain things the
way you would to a smart person who is new to coding.

## Timeline

| Time | Milestone |
|---|---|
| 10:00–11:00 | Skeleton green ✅ + all four mentor tables visited |
| 11:00–13:00 | FalkorDB real ✅ · LaserData real ✅ · pivot to orbital ✅ |
| 13:00–14:00 | Guild.ai agents + unblock RocketRide |
| 14:00–15:00 | Demo script locked |
| 15:00–17:00 | Dashboard UI, graph viz, seeded memory |
| 17:00–17:30 | **Record demo. Code freeze.** |
| 17:30–18:30 | Dry-run pitch twice, README, submit |
