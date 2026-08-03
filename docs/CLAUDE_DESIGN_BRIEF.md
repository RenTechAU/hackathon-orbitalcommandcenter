# Claude Design Brief — the dashboard

Paste the block below into Claude Design (or Claude.ai artifacts) to generate
the UI. Output goes in `web/`.

**Do this at ~3 PM, not before.** The backend has to work first. A beautiful UI
over a broken pipeline scores nothing; an ugly UI over a working pipeline wins.

---

## The prompt

> Build a single-file HTML dashboard for a smart-home AI that negotiates
> between household members. Everything inline — CSS and JS in the one file,
> no build step, no external requests except a CDN script tag if needed.
>
> **The story the screen has to tell:** two people in the same room want
> different thermostat settings. The system decides — and it gets *fairer over
> time* because it remembers who gave way last.
>
> **Layout, three panels:**
>
> 1. **Live feed** (left, narrow) — scrolling stream of sensor events, newest
>    on top, fading in. Lines like `jeremy entered living_room`,
>    `living_room is 71°F`. Monospace, timestamps, subtle.
>
> 2. **The room** (centre, hero) — a floor-plan-ish card for the living room
>    showing who's currently in it as avatar chips, the current thermostat
>    value large, and the device state. When a conflict fires, this panel is
>    where the drama happens: show both requested values side by side in
>    tension, then resolve to the winner with a short animation.
>
> 3. **Memory** (right) — a force-directed graph of people, rooms, devices and
>    `CONCEDED` edges. Nodes coloured by type. **New edges must visibly animate
>    in** when a concession is recorded — this is the single most important
>    visual in the app. Below it, a running "fairness ledger": `jeremy 2 — sam 1`.
>
> **The money moment:** when the second conflict resolves differently from the
> first, surface a banner reading something like *"Jeremy conceded last time —
> their turn"* with the relevant graph edge highlighted. This is what the judges
> need to understand in one glance.
>
> **Style:** dark, calm, high contrast. Think a premium home-automation console,
> not a developer tool. Generous spacing, one accent colour, restrained motion —
> animation only where it carries meaning. Legible from three metres away
> because it's being demoed on a projector.
>
> **Data:** drive it from a hardcoded JS array of events replaying on a timer,
> with a "Replay demo" button and a speed control. Do not fetch anything — it
> must work with no backend and no wifi.

---

## Why hardcoded data

Same reason as the Python fallback: the demo must survive a dead network. Wire
it to the live backend only if there's time after the recording is safe.

A `/events` endpoint returning the same JSON shape is the integration path —
one `fetch` swap, nothing else.

## Checklist before you call it done

- [ ] Readable on a projector from across the room
- [ ] Runs with wifi off
- [ ] The `CONCEDED` edge animating in is unmissable
- [ ] Replay button works — you will demo it more than once
- [ ] The second conflict's explanation text is legible in the recording
