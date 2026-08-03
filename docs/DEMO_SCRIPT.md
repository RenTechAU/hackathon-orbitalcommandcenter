# Demo script — 90 seconds

Lock this by 2 PM. Build backwards from it: anything not in this script is
optional.

---

**[0:00–0:10] The problem — one sentence, no preamble**

> "Every smart home assumes one person lives there. Mine has two people who
> want different things, and it has to decide."

Don't say "so basically". Don't explain the hackathon. Start here.

---

**[0:10–0:35] The conflict**

Screen: the room panel. Both people walk in. Both make a request.

> "Jeremy wants 68. Sam wants 74. Same room. The system has never seen this
> before — so it picks one, arbitrarily. Sam wins."

> "But watch what it writes down."

Point at the graph. A `CONCEDED` edge animates in.

---

**[0:35–0:55] The payoff — this is the whole demo**

Replay the exact same conflict.

> "Same two people. Same two requests. Nothing else changed."

> "*Jeremy conceded last time — their turn.*"

Pause. Let it land. **This is the moment the judges remember.** Don't talk over it.

> "It didn't get smarter. It got *fairer*. That's what memory buys you."

---

**[0:55–1:15] Architecture — name all four, explicitly**

Judges are ticking a checklist. Make it trivially easy.

> "**LaserData** streams the live sensor events — motion, temperature, who's in
> the room. **FalkorDB** is the memory: people, rooms, devices, and the history
> of who gave way to whom — and deciding fairness is a multi-hop graph query, so
> it genuinely has to be a graph. **Guild.ai** runs one advocate agent per person
> plus a safety agent that can veto — nobody sets the heat to 95. And
> **RocketRide** actually executes it on the thermostat."

---

**[1:15–1:30] What's next — one sentence**

> "Right now it arbitrates temperature. The same graph handles music, lights,
> and who gets the TV — every household argument is the same shape."

Stop. Don't trail off. Don't add "yeah, so...".

---

## Rules

- **Record this the moment it works.** Talk over the recording if wifi is bad.
- Dry-run out loud **twice** before judging. Out loud — not in your head.
- Time it. 90 seconds is shorter than it feels.
- If something breaks mid-demo, keep talking and switch to the recording. Never
  debug in front of judges.
- Have the FalkorDB graph browser open in a second tab as backup visual.

## The one-liner

If you only get ten seconds with someone:

> "A smart home where two people want different things — and it gets fairer
> over time because it remembers who gave way last."
