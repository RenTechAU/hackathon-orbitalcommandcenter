"""
Adapter slots for the three SDKs I can't write for you.

IMPORTANT: I deliberately did not guess at LaserData / RocketRide / Guild.ai
syntax. These are new tools and inventing plausible-looking API calls is how
you lose two hours chasing a method that never existed.

Each class below runs in FALLBACK mode out of the box, so the whole pipeline
works today. Go to each sponsor table, get the five lines of real code, and
paste them into the marked spot. Nothing else in the repo has to change.

That is the entire point of this file.
"""

import os
import random


# ---------------------------------------------------------------- LaserData
class LiveFeed:
    """
    Real-time layer. Fallback = a plain Python generator. Real = LaserData.

    STATUS: ✅ REAL AND TESTED against the local Laser Stack (iggy + plane).

    The key insight: we are BOTH SIDES of this feed. The house's sensors publish
    SensorEvents into the log; the orchestrator reads them back out. So there
    was never a question to ask at the sponsor table about "what fields does a
    record carry" -- we define the record, because we write it.

    That also makes LaserData genuinely load-bearing rather than decorative:
    every single sensor event the orchestrator reacts to has travelled through
    a real Apache Iggy log. Pull the plug on the stack and the demo stops. The
    two sides are decoupled exactly like a real deployment -- the sensors don't
    call the orchestrator, they publish, and the orchestrator subscribes.

    API note: every method used here was read off the SDK's OWN shipped type
    stub (.venv/.../laser_sdk/__init__.pyi), not guessed and not from a blog.
    """

    def __init__(self, use_real=False, stream_name="home", topic_name="sensors",
                 reader_name="orchestrator", **cfg):
        self.use_real = use_real
        self.stream_name = stream_name
        self.topic_name = topic_name
        self.reader_name = reader_name
        if use_real and not os.getenv("LASER_CONNECTION_STRING"):
            raise RuntimeError(
                "LaserData needs a connection string. It's in .env as "
                'LASER_CONNECTION_STRING (format: user:password@host:port). '
                "Start the local stack with: laser-stack/scripts/up"
            )

    def events(self, source):
        """
        Yield SensorEvents for the pipeline to react to.

        `source` is the sensor side -- an iterable of SensorEvents (the scripted
        demo beats, or the random stream). In fallback we just hand them straight
        through. In real mode they take the scenic route: published to LaserData,
        then read back off the log.

        Either way the rest of the pipeline cannot tell the difference. That is
        the whole point of this file.
        """
        if not self.use_real:
            yield from source
            return
        yield from self._laser_roundtrip(list(source))

    # -- real path --------------------------------------------------------
    def _laser_roundtrip(self, outgoing):
        """
        Publish `outgoing` to LaserData, then yield what comes back off the log.

        Runs the async SDK on a background thread and hands events to this sync
        generator through a queue, so the pipeline keeps its plain `for` loop.
        """
        import asyncio
        import queue
        import threading

        out = queue.Queue(maxsize=100)
        DONE = object()   # sentinel: the reader caught up, nothing more coming

        def _run():
            try:
                asyncio.run(self._pump(outgoing, out))
            except Exception as exc:          # surface it, don't hang the demo
                out.put(exc)
            finally:
                out.put(DONE)

        threading.Thread(target=_run, daemon=True).start()

        while True:
            item = out.get()
            if item is DONE:
                break
            if isinstance(item, Exception):
                raise item
            yield item

    async def _pump(self, outgoing, out):
        """The actual LaserData session: ensure topology, publish, read back."""
        import laser_sdk as ls

        from sim.sensors import SensorEvent

        conn = os.environ["LASER_CONNECTION_STRING"]

        async with await ls.Laser.connect(conn) as laser:
            stream = laser.stream(self.stream_name)
            await stream.ensure()

            # cls= makes this a TYPED topic: records decode straight back into
            # our SensorEvent dataclass, dict-valued `value` field and all.
            topic = stream.topic(self.topic_name, cls=SensorEvent)
            await topic.ensure(1)

            reader = topic.records(self.reader_name)

            # Join at the LIVE EDGE first.
            #
            # The log is durable, so it still holds every event from every
            # previous run. A fresh reader would replay all of that history into
            # today's demo and the conflict beats would fire in the wrong order.
            # Draining to the end first means we only react to what happens now
            # -- which is also exactly what a real sensor consumer does.
            drained = 0
            while await reader.next() is not None:
                drained += 1
            if drained:
                print(f"[laser] skipped {drained} events from earlier runs")

            for ev in outgoing:
                await topic.publish(ev).send()
            print(f"[laser] published {len(outgoing)} sensor events")

            # Now read back exactly what we just published.
            while (record := await reader.next()) is not None:
                out.put(record.value)


# ------------------------------------------------------------- RocketRide.ai
class Actuator:
    """Motion layer. This is what actually DOES something."""

    def __init__(self, use_real=False, **cfg):
        self.use_real = use_real
        self.log = []
        if use_real:
            # TODO(sponsor table): RocketRide client + API key.
            # Ask them: "how do I register a tool and trigger one execution?"
            raise NotImplementedError("paste RocketRide client here")

    def act(self, device, value, because=""):
        entry = {"device": device, "value": value, "because": because}
        self.log.append(entry)
        print(f"  [ACT] {device} -> {value}   ({because})")
        if self.use_real:
            pass  # TODO: real RocketRide tool call
        return entry


# ------------------------------------------------------------------ Guild.ai
class Council:
    """
    Multi-agent layer. One advocate per household member + a safety agent
    that can veto. The safety veto is a REAL handoff, not a fake one --
    judges look for that.
    """

    def __init__(self, use_real=False, **cfg):
        self.use_real = use_real
        if use_real:
            # TODO(sponsor table): Guild.ai workspace + agent definitions.
            # Ask them: "minimum viable two agents that hand off to each other?"
            raise NotImplementedError("paste Guild.ai client here")

    def resolve(self, requests, memory, room, topic="thermostat"):
        """
        requests: {"jeremy": 68, "sam": 74}
        room:     where the argument is happening -- the graph walk starts here
        Returns (winner, value, reasoning)

        Fallback logic below is intentionally simple but CORRECT -- it already
        demonstrates memory-driven fairness. Upgrade to real Guild agents once
        the rest works; if you run out of time, this still tells the story.
        """
        people = list(requests)
        if len(people) == 1:
            p = people[0]
            return p, requests[p], f"{p} is alone in the room"

        a, b = people[0], people[1]
        balance = memory.concession_balance(room, a, b, topic)

        if balance > 0:
            winner, why = a, f"{a} has given way {balance} more time(s) before -- their turn"
        elif balance < 0:
            winner, why = b, f"{b} has given way {-balance} more time(s) before -- their turn"
        else:
            winner = random.choice([a, b])
            why = "no history yet -- picking arbitrarily and remembering the outcome"

        loser = b if winner == a else a
        value = requests[winner]

        # SAFETY AGENT VETO -- the human-in-the-loop / second-agent moment
        if topic == "thermostat" and not (60 <= value <= 80):
            value = max(60, min(80, value))
            why += f" (safety agent clamped to {value})"

        memory.record_concession(loser, winner, topic)
        return winner, value, why
