# Prompt for Guild.ai chat (The Smith)

Paste everything below the line into Guild.ai's chat — either `guild chat` in
the terminal, or the chat box on app.guild.ai.

It asks for two agents that genuinely disagree, which is what the hackathon
judges are looking for. Ask for both in one go; The Smith can build them
together and wire the handoff.

---

I'm building a **satellite downlink broker** for a hackathon. I need two agents
that work together but can disagree with each other.

## The situation

Satellites in orbit collect data. To send it to the ground they need a
"downlink window" — a few minutes when a ground station's dish is pointed at
them. Ground stations are scarce and satellite passes overlap, so two
satellites often want the same dish at the same time.

My system resolves this by fairness: it remembers which satellite gave up its
window last time, and gives the next one to whoever has yielded most. But
fairness must sometimes be overruled, because some data cannot wait.

## Agent 1 — `advocate`

Argues one satellite's case for a downlink window. It is **not** the judge. It
makes the strongest honest case for its own satellite and nothing else. I run
it once per satellite, so two instances argue against each other.

**Input** — a single JSON object:

```json
{
  "satellite": "SAT-3",
  "station": "Kiruna",
  "backlog_gb": 80,
  "payload": "storm-imagery",
  "urgency": "high",
  "times_yielded_here": 2,
  "opponent": {"satellite": "SAT-1", "backlog_gb": 20, "urgency": "routine"}
}
```

`times_yielded_here` = how often this satellite has already given up its window
at this station.

**Output** — only a JSON object, no preamble and no code fences:

```json
{"satellite": "SAT-3", "claim_strength": 0.72, "argument": "one sentence under 25 words"}
```

`claim_strength` is 0.0 to 1.0.

**How it should weigh a claim**, most important first:

1. How often it has already yielded here. This matters most — a satellite that
   always loses never gets its data down at all.
2. Payload urgency: `critical` beats `high` beats `routine`.
3. Backlog size. More data at risk, but a weaker argument than being
   repeatedly passed over.

**It must be honest.** If its satellite has a weak case, it should say so and
return a low `claim_strength`. An advocate that always claims 0.9 is useless.
It must never argue for the opponent, never declare a winner, and never invent
facts that aren't in the input.

## Agent 2 — `mission-safety`

Reviews the decision after fairness has picked a winner, and **can overrule
it**. This is the important part: I want a real veto, not a rubber stamp.

**Input** — a single JSON object:

```json
{
  "station": "Kiruna",
  "proposed_winner": {"satellite": "SAT-1", "payload": "surface-imagery", "urgency": "routine"},
  "proposed_loser":  {"satellite": "SAT-4", "payload": "conjunction-warning", "urgency": "critical"},
  "reason": "SAT-1 yielded 1 more time at Kiruna -- its turn"
}
```

**Output** — only a JSON object, no preamble and no code fences:

```json
{"veto": true, "winner": "SAT-4", "reason": "one sentence under 25 words"}
```

If `veto` is false, `winner` stays the proposed winner.

**It should veto only** when the losing satellite carries something that cannot
wait for another orbit. Specifically when its `urgency` is `critical` and the
winner's is not. A `conjunction-warning` is a collision alert — if it doesn't
reach the ground on this pass, an operator can't act, and the satellite may not
be there next orbit.

**It should NOT veto** for a large backlog (delay is not loss), for `high`
urgency (that survives another orbit), or because it disagrees with the
fairness maths. If both satellites are `routine`, or both `critical`, it has no
safety grounds and should let the decision stand.

Fairness is the default rule and a good one. Safety is the exception to it, not
a second opinion on it. A system that vetoes constantly is just a priority
table. **When in doubt, don't veto.**

## What I need from you

1. Build both agents.
2. Show me how to call each one from outside Guild and get **just the JSON
   back**, so a Python script can parse it. A one-shot, non-interactive command
   or an HTTP call — whichever is the normal way.
3. Tell me whether the agents need to be added to a workspace before they can
   be called, and the command to do that if so. I created a workspace called
   `orbital-contact-broker` and set it as my CLI default, but
   `guild workspace chat --agent <name> --once "..."` returns "The workspace
   doesn't exist."
4. Show me how `mission-safety` can be called as a **sub-agent** of another
   agent, so the handoff happens inside Guild rather than in my Python.

Keep responses short — I'm on a hackathon clock.
