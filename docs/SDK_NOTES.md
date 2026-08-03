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

**Status:** ✅ WIRED (real Iggy log, load-bearing) — 2026-08-03
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

~~STILL TO CONFIRM AT TABLE (2 things)~~ — **BOTH QUESTIONS WERE MOOT.**

We are both sides of this feed: the house's sensors publish, the orchestrator
subscribes. So we choose the stream/topic names ("home"/"sensors") and we know
the record fields because we write them. Nothing to ask.

The API came from the SDK's OWN shipped type stub — the most authoritative
source available, and not a guess:
```
.venv/lib/python3.14/site-packages/laser_sdk/__init__.pyi   # 3,433 lines
```

VERIFIED WORKING against the local stack:
```python
async with await ls.Laser.connect(os.environ["LASER_CONNECTION_STRING"]) as laser:
    stream = laser.stream("home")
    await stream.ensure()                            # NOTE: no args
    topic = stream.topic("sensors", cls=SensorEvent) # cls= => typed decode
    await topic.ensure(1)                            # partitions is positional
    await topic.publish(ev).send()                   # ev = a SensorEvent
    reader = topic.records("orchestrator")
    while (rec := await reader.next()) is not None:
        rec.value                                    # a real SensorEvent back
```

Two gotchas that cost real time — worth knowing:
  1. `.next()` returns None when **caught up**, NOT when the stream ends. A
     `while ... is not None` loop exits the moment it drains, it does not block.
  2. Consumer offsets **persist in the log between runs**. A fresh reader would
     replay every previous run's events into the demo. `_pump()` drains to the
     live edge first, then publishes. Do not remove that drain.
  3. `cls=SensorEvent` round-trips the dict-valued `value` field
     (`{"thermostat": 68}`), `None` person, floats and bools. All tested.

Panic switch: `LASER_LIVE=0 python src/main.py` forces the fallback.

Mentor said teams get wrong:

Mentor said would impress:

---

## RocketRide.ai — motion / orchestration layer

**Status:** ✅ WIRED AND PROVEN LIVE — every decision executes on their server
**API key:**  <-- GET THIS. Put it in .env as ROCKETRIDE_APIKEY=<key>
**Install:** `pip install rocketride` (v1.3.0, installed into `.venv`)

**Identity CONFIRMED** — it's the right vendor, from the package's own metadata:
```
Name: rocketride                    Version: 1.3.0
Summary: RocketRide Pipeline Python Client SDK
Author-email: "RocketRide, Inc." <dev@rocketride.ai>
Copyright (c) 2026 Aparavi Software AG
Docs: https://docs.rocketride.ai
```
The `.ai` address settles the earlier `.org` vs `.ai` worry. Same company.

The API below came from the SDK's OWN shipped source (it ships full source +
a `py.typed` marker, ~4,000 lines across `client.py`, `mixins/execution.py`,
`mixins/data.py`). Not guessed, not from a blog:
```python
from rocketride import RocketRideClient

client = RocketRideClient(uri='', auth=api_key)   # uri='' => their cloud
await client.connect(api_key)                     # -> ConnectResult
started = await client.use(pipeline={...})        # or filepath='x.pipe'
token   = started['token']
result  = await client.send(token, payload_str)   # -> PIPELINE_RESULT
await client.disconnect()
```

Env vars the client reads on its own: `ROCKETRIDE_APIKEY`, `ROCKETRIDE_URI`
(defaults to `https://api.rocketride.ai`; local server is `localhost:5565`).

Pipeline config shape, from their `types/pipeline.py`:
```python
{
  'project_id': '<guid>',
  'source': 'webhook_1',
  'components': [
    {'id': 'webhook_1', 'provider': 'webhook', 'config': {}},
    {'id': 'ai_chat_1', 'provider': 'ai_chat', 'config': {'model': 'gpt-4'},
     'input': [{'from': 'webhook_1', 'lane': 'output'}]},
    {'id': 'response_1', 'provider': 'response', 'config': {},
     'input': [{'from': 'ai_chat_1', 'lane': 'answer'}]},
  ],
}
```

⚠️ **What is NOT yet proven:** with no API key I could not run a single live
call. The client init, `use()` and `send()` signatures are certain (read off
their source). What's unverified is whether our `ANNOUNCER_PIPELINE` config is
accepted by their server, and the exact key the announcement text comes back
under — `_read_answer()` checks several and shrugs if none match. Expect ~15
minutes of fixing once a key exists.

Panic switch: `ROCKETRIDE_LIVE=0 python src/main.py` forces the fallback.
Also: if RocketRide throws mid-demo, `act()` catches it, prints the action
anyway and keeps going. The demo cannot die from a vendor outage.

Ask at the table: *"cheapest pipeline that just echoes a payload back?"* — if
`ai_chat` needs model credits we don't have, swap to `webhook -> response`.

Mentor said teams get wrong:

Mentor said would impress:

---

## Guild.ai — multi-agent layer

**Status:** ⬜ BLOCKED — still no real package. This is the last blocker.
**Workspace:**
**API key:**
  - homepage: https://www.guild.ai/  ("The Control Plane for AI Agents")

❌ **`pip install guildai` is the WRONG package — do not install it.**
Checked its wheel metadata directly, 2026-08-03:
```
Name: guildai            Version: 0.9.0
Summary: Experiment tracking, ML developer tools
Home-page: https://guild.ai
Requires-Dist: tensorboard, scikit-learn, numpy, protobuf (<5)
```
It IS their domain, so it's their project — but it's an old ML experiment
tracker (TensorBoard wrapper), not the agent control plane. Almost certainly
pre-pivot. Their own AI chat suggested it anyway; it was wrong.

**Still to ask:**
  1. "`guildai` on PyPI is 0.9.0, ML experiment tracking, depends on
     TensorBoard. Is that pre-pivot? What's the CURRENT agent package?"
  2. "Is there a Python SDK at all, or is it TypeScript / HTTP API only?"
  3. "Smallest runnable two-agent handoff example?"

Ask: *"minimum viable two agents that hand off to each other?"*

```python
# paste working agent definition + handoff here
```

Mentor said teams get wrong:

Mentor said would impress:


---

## RocketRide — solved: "Pipeline is already running."

Hit this when a previous run (or a second terminal) left a pipeline alive on
their server. The error comes from THEIR server, not the SDK — it is not in the
package source anywhere.

Fix, read off `mixins/execution.py`, `use()` signature:

```python
await client.use(pipeline=cfg, use_existing=True, ttl=600)
```

- `use_existing=True` — reattach to the running pipeline instead of erroring.
- `ttl=600` — idle pipelines expire after 10 min, so runs stop piling up.
  `ttl=0` means never expire, which is what caused the jam in the first place.

There is also `await client.terminate(token)` to stop one deliberately.

**What comes back depends on whether ANTHROPIC_API_KEY is set**, because
RocketRide passes YOUR key through to Anthropic — their platform key does not
cover model calls.

| ANTHROPIC_API_KEY | pipeline | `send()` returns |
|---|---|---|
| set | webhook → prompt → llm_anthropic → response_answers | prose sentence |
| not set | webhook → response_text | `{'name', 'path', 'objectId'}` receipt |

Both are real executions. Verified live: with no Anthropic key we get a fresh
`objectId` per action, which the demo now prints as `[RR ]`. Staying silent
made RocketRide LOOK unwired even though it ran — do not go back to that.

**To get the spoken announcement:** add `ANTHROPIC_API_KEY=<key>` to `.env`.
Nothing else changes; `announcer_pipeline()` picks the richer form on its own.

### Gotcha: use_existing=True IGNORES your pipeline config

Tested live 2026-08-03. `use(use_existing=True)` reattaches to whatever is
already running and silently discards the config you passed -- you get the OLD
pipeline back, same token. If you start with it, then later add an
ANTHROPIC_API_KEY expecting spoken announcements, you keep reattaching to the
echo-only pipeline and never see prose.

So `_connect()` now tries `use_existing=False` FIRST and only reattaches if the
server refuses, printing a warning that the live pipeline may be stale.

To force a clean slate: reattach to get the token, `terminate(token)`, then
`use(use_existing=False)`.

### The Anthropic key is NOT optional for the LLM leg

Tested live: sending the `llm_anthropic` component WITHOUT an apikey in its
config is rejected outright --

    RuntimeError: Invalid Anthropic API key format, please check your API key.

Connecting an integration/extension in the RocketRide console does NOT satisfy
this. Their server wants YOUR key inside the pipeline config; their platform
key does not cover model calls. Put `ANTHROPIC_API_KEY=<key>` in `.env` and
`announcer_pipeline()` picks the richer form automatically.

### SETTLED: there is no way to avoid supplying your own model key

Checked against the server's own service catalogue (`await client.get_services()`
-> `{'services': {...140 providers...}, 'version': int}`).

`llm_anthropic` offers 20 profiles. **All 20 list `apikey` as required:**

    claude-sonnet-5, claude-opus-latest, claude-sonnet-4-6, claude-haiku-4-5,
    claude-opus-4-8, claude-fable-5, ... (and `custom`, which additionally
    requires `model` and `modelTotalTokens`)

So connecting an integration in the RocketRide console does NOT feed credentials
to a pipeline. Stop trying -- it is their design, not a misconfiguration.
Put `ANTHROPIC_API_KEY=<key>` in `.env`.

98 of the 140 providers need no apikey at all (`chat`, `agent_rocketride`,
`answer_documents`, the db_* nodes...). If you ever want prose without paying
for a model, one of those is where to look -- but the receipt path we already
have is enough to make RocketRide load-bearing.

Profile updated 4-6 -> `claude-sonnet-5` (newer, and on their supported list).


---

## Guild.ai — how it actually works (verified 2026-08-03)

**It is a CLI, not a Python SDK.** That is why searching for Python docs kept
failing. Installed via Homebrew at `/opt/homebrew/bin/guild`, v0.17.0.

Workspace: `rentechau/orbital-contact-broker`, set as CLI default.
Agents: `rentechau~advocate`, `rentechau~mission-safety` (both PUBLISHED).

### Creating an agent

```bash
guild --non-interactive agent init \
  --name advocate --agent-type GUILD_NATIVE --category other \
  --directory src/agents/advocate
```

`GUILD_NATIVE` = prompt-based (what we want). Others are `GUILD_TYPESCRIPT`
and `GOOSE`. `--template` is NOT accepted with GUILD_NATIVE. `--category` is
required in non-interactive mode; list them with `guild agent categories`.

Scaffolds `PROMPT.md` (the agent's brief) + `guild.yaml` (tools it may use)
+ `guild.json` (id and name). No code for a native agent.

### Publishing — two gotchas that cost time

1. **A `package.json` is required.** `agent save --bump` fails without one, and
   `agent publish` then fails with "Version number is required for publishing".
   GUILD_NATIVE does not scaffold one. Add a minimal
   `{"name": "...", "version": "0.1.0", "private": true}` and it works.
2. **Each agent dir is its OWN git repo** with a remote on app.guild.ai. The
   outer project repo will try to embed them as broken submodules. Gitignore
   them; prompt backups live in `docs/guild-agents/`.

```bash
guild --non-interactive agent save --wait --publish
```

### Calling an agent from a script

Agents must be attached to the workspace first, or you get the misleading
error **"The workspace doesn't exist"** even though it does:

```bash
guild --non-interactive workspace agent list      # confirm they're attached
guild --non-interactive workspace chat --agent rentechau~advocate \
      --once '<json payload>'
```

`--once` = one-shot, non-interactive. Output is progress chatter plus the
agent's reply; `Council._ask()` scans backwards for the last line that parses
as a JSON object rather than assuming a position.

**Budget ~8 seconds per call.** The two advocates are run in parallel threads
to halve it. A full four-beat demo with live agents takes ~35s, ~50s with
LaserData and RocketRide live too.

Panic switch: `GUILD_LIVE=0` forces deterministic logic.
