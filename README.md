# Smart Home Orchestrator

**Memory Meets Motion** · Frontier Tower SF · Aug 3, 2026

An AI household that **negotiates**. When two people in the same room want
different things, agents argue it out — and the system gets *fairer over time*
because it remembers who gave way last.

## Run it

```bash
python3 src/main.py
```

No SDKs, no keys, no internet. Two conflicts, identical inputs, different
outcomes — that difference is the memory.

## Architecture

```
LaserData  ->  FalkorDB  ->  Guild.ai  ->  RocketRide.ai
 (now)         (ever)        (decide)      (do)
```

| Tool | Role | Why load-bearing |
|---|---|---|
| **LaserData** | Live sensor stream | Nothing to react to without it |
| **FalkorDB** | People, rooms, devices, **who conceded to whom** | Fairness = multi-hop: room → occupants → history between them |
| **Guild.ai** | Advocate agent per person + safety veto | Real disagreement, real handoff |
| **RocketRide.ai** | Executes the decision | Something happens in the world |

## Docs

| File | What it's for |
|---|---|
| `CLAUDE.md` | Project context for Claude Code — read first |
| `docs/SETUP.md` | Getting running, in order |
| `docs/SDK_NOTES.md` | **Fill in at the sponsor tables** — source of truth for vendor syntax |
| `docs/CLAUDE_DESIGN_BRIEF.md` | Prompt for generating the dashboard |
| `docs/DEMO_SCRIPT.md` | The 90-second pitch |

## Layout

```
CLAUDE.md               project context for Claude Code
src/main.py             pipeline end to end
src/sim/sensors.py      fake stream + scripted demo beats
src/memory/graph.py     FalkorDB schema, Cypher, fairness query
src/adapters/vendors.py the three SDK slots
src/agents/             Guild.ai agent definitions
web/                    dashboard UI
docs/                   guides
```

## Status

- [x] Walking skeleton green
- [ ] FalkorDB wired
- [ ] LaserData wired
- [ ] RocketRide wired
- [ ] Guild.ai wired
- [ ] Dashboard
- [ ] Demo recorded
