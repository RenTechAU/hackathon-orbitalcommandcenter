# Prompt for Guild.ai chat (The Smith)

Paste the block below into `guild chat` or the chat box on app.guild.ai.
(A longer version with full reasoning is in this file's git history.)

---

Build me two agents for a satellite downlink broker. Satellites compete for
scarce ground-station time. Fairness decides — whoever gave up their window
most often wins — but safety can overrule it.

Both must return **only** JSON, no preamble, no code fences.

**Agent 1: `advocate`** — argues ONE satellite's case. Not the judge. I run it
once per satellite so two instances argue against each other.

In:
```json
{"satellite":"SAT-3","station":"Kiruna","backlog_gb":80,"payload":"storm-imagery",
 "urgency":"high","times_yielded_here":2,
 "opponent":{"satellite":"SAT-1","backlog_gb":20,"urgency":"routine"}}
```
Out:
```json
{"satellite":"SAT-3","claim_strength":0.72,"argument":"under 25 words"}
```
Weigh, most important first: how often it already yielded here; then urgency
(`critical` > `high` > `routine`); then backlog size. Be honest — return a low
score for a weak case. An advocate that always claims 0.9 is useless. Never
argue for the opponent, never pick a winner.

**Agent 2: `mission-safety`** — reviews the fairness verdict and CAN overrule it.

In:
```json
{"station":"Kiruna",
 "proposed_winner":{"satellite":"SAT-1","urgency":"routine"},
 "proposed_loser":{"satellite":"SAT-4","payload":"conjunction-warning","urgency":"critical"},
 "reason":"SAT-1 yielded more at Kiruna"}
```
Out:
```json
{"veto":true,"winner":"SAT-4","reason":"under 25 words"}
```
Veto ONLY when the loser is `critical` and the winner isn't — e.g. a collision
warning that can't wait an orbit. Do NOT veto for big backlogs, for `high`
urgency, or because you dislike the fairness maths. When in doubt, don't veto.
A system that always vetoes is just a priority table.

**Also tell me:**
1. How to call each agent from a script and get just the JSON back.
2. Why `guild workspace chat --agent rentechau~advocate --once "..."` says
   "The workspace doesn't exist" — the workspace exists and is my CLI default.
   Do agents need attaching to it first?
3. How to make `mission-safety` a sub-agent of `advocate`, so the handoff
   happens inside Guild.

Keep answers short, I'm on a hackathon clock.
