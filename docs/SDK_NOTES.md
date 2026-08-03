# SDK Notes — fill these in AT the sponsor tables

**This file is the source of truth for vendor syntax.** Claude Code is
instructed not to invent SDK calls — if the snippet isn't here, it stops and
asks. So paste what you get, verbatim, even if it's messy.

Ask every mentor these two questions:

1. *"What's the thing teams always get wrong with your SDK?"* — saves ~90 min
2. *"What would make you say 'that's the best use of this I've seen today'?"*
   — this is the judging rubric, spoken aloud, for free. Write the answer down.

---

## FalkorDB — memory layer

**Status:** ✅ WIRED (real graph, load-bearing) — 2026-08-03
**Connection:** localhost:6379 (FalkorDB running in Docker)
**Install:** `pip install falkordb` (installed into `.venv`)

How it runs:
```bash
# 1. start the database (once per boot; Docker Desktop must be running)
docker run -d --name falkordb -p 6379:6379 falkordb/falkordb
# 2. run the app with the venv python (has falkordb installed)
.venv/bin/python src/main.py
```

Proven working: the app writes CONCEDED edges to the real graph and the
fairness query reads them back. Verified with:
```python
from falkordb import FalkorDB
g = FalkorDB(host="localhost", port=6379).select_graph("household")
g.query("MATCH (a)-[c:CONCEDED]->(b) RETURN a.name, b.name, c.topic").result_set
```

NOTE: the real DB persists between runs (the fallback didn't). `memory.reset()`
is called at startup in main.py to keep the two-conflict demo honest.

Mentor said teams get wrong:

Mentor said would impress:

---

## LaserData — real-time layer

**Status:** 🟡 code ready — ONLY the connection string is missing
**Free tier:** https://laserdata.cloud/?source=sf-memory-motion-hackthon-2026
**Local:** https://github.com/laserdata/laser-stack
**Quickstart:** https://docs.laserdata.com/laser-sdk/quickstart
**Discord:** https://discord.gg/QXVbqWxHHb
**Install:** `pip install laser-sdk` (needs Python 3.10+)
**Connection string:**  <-- GET THIS: Cloud Console → Credentials tab, or Laser Stack locally
  then run:  export LASER_CONNECTION_STRING="<the-string-they-give-you>"

Ask: *"simplest way to subscribe to a topic and get a callback?"*

REAL snippet (pulled from their official quickstart docs, 2026-08-03):
```python
import asyncio, os
from dataclasses import dataclass
import laser_sdk as ls

@dataclass
class Order:
    id: int
    total: int

async def main():
    async with await ls.Laser.connect(os.environ["LASER_CONNECTION_STRING"]) as laser:
        topic = laser.stream("shop").topic("orders", cls=Order)
        await topic.ensure(partitions=2)
        records = topic.records("log-reader")
        while (record := await records.next()) is not None:
            print(record.value.total)

asyncio.run(main())
```

STILL TO CONFIRM AT TABLE (2 things, so we map their data to our SensorEvent):
  1. Real stream/topic name for the sensor feed? (their example uses "shop"/"orders")
  2. What fields does each record carry? (so we build SensorEvent(kind, room, value, person))

Mentor said teams get wrong:

Mentor said would impress:

---

## RocketRide.ai — motion / orchestration layer

**Status:** ⬜ not wired — need to confirm this is the right product first
**API key:**
**CANDIDATE (unverified) found via web search 2026-08-03 — CONFIRM AT TABLE:**
  - homepage: https://rocketride.org/   (note: .org, but our notes say RocketRide.ai)
  - docs:     https://docs.rocketride.org/
  - github:   https://github.com/rocketride-org
  - has Python + TypeScript + MCP SDKs; "AI pipeline engine"
  ⚠️ Could be a DIFFERENT product with a similar name. First question at table:
     "Is your docs site docs.rocketride.org?" If yes, I'll go read it and wire it in.

Ask: *"how do I register a tool and trigger one execution?"*

```python
# paste working client init + tool call here
```

Mentor said teams get wrong:

Mentor said would impress:

---

## Guild.ai — multi-agent layer

**Status:** ⬜ not wired — homepage found, but NO real code yet
**Workspace:**
**API key:**
**CANDIDATE (unverified) found via web search 2026-08-03 — CONFIRM AT TABLE:**
  - homepage: https://www.guild.ai/  ("The Control Plane for AI Agents")
  ⚠️ Search could NOT find their Python SDK docs (kept returning OpenAI's tools
     instead). So I have a homepage but no working snippet. At the table ask:
     "Where's your Python quickstart / a two-agent handoff example?" then paste it here.

Ask: *"minimum viable two agents that hand off to each other?"*

```python
# paste working agent definition + handoff here
```

Mentor said teams get wrong:

Mentor said would impress:
