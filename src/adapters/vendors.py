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
    Real-time layer. Fallback = the fake sensor stream. Real = LaserData.

    STATUS: the real path is PREPPED but UNTESTED. It uses LaserData's real
    methods (copied from their official quickstart) but has never actually run,
    because we don't have the connection string yet.

    To turn it on when you have the string:
        1. export LASER_CONNECTION_STRING="<from the LaserData console>"
        2. confirm the 2 items marked TODO(sponsor table) below
        3. in main.py, build the feed with LiveFeed(use_real=True) and read
           its .events() instead of the scripted demo
    Until all that happens it stays in fallback and the demo is untouched.
    """

    def __init__(self, use_real=False, stream_name="home", topic_name="sensors", **cfg):
        self.use_real = use_real
        # TODO(sponsor table): confirm the real stream + topic names for the
        # sensor feed. Their quickstart example used "shop" / "orders".
        self.stream_name = stream_name
        self.topic_name = topic_name
        if use_real and not os.getenv("LASER_CONNECTION_STRING"):
            raise RuntimeError(
                "LaserData needs a connection string. Get it from the LaserData "
                'console, then: export LASER_CONNECTION_STRING="..."'
            )

    def events(self):
        """Yield SensorEvents. Same shape whether real or fake -- the rest of
        the pipeline can't tell the difference. That's the whole point."""
        if not self.use_real:
            from sim.sensors import stream
            yield from stream()
            return
        yield from self._laser_events()

    # -- real path --------------------------------------------------------
    def _laser_events(self):
        """
        Bridge LaserData's async feed into our sync pipeline.

        The `async with ... records.next()` block below is copied VERBATIM from
        LaserData's official quickstart -- do not "fix" it. The thread+queue
        around it is plain Python that lets a sync `for` loop read an async
        source. The only thing to fill in is _to_event().
        """
        import asyncio
        import queue
        import threading

        import laser_sdk as ls

        conn = os.environ["LASER_CONNECTION_STRING"]
        out = queue.Queue(maxsize=100)
        DONE = object()  # marker that the stream ended

        async def _consume():
            async with await ls.Laser.connect(conn) as laser:
                topic = laser.stream(self.stream_name).topic(self.topic_name)
                records = topic.records("orchestrator")
                while (record := await records.next()) is not None:
                    ev = self._to_event(record.value)
                    if ev is not None:
                        out.put(ev)
            out.put(DONE)

        threading.Thread(target=lambda: asyncio.run(_consume()), daemon=True).start()

        while True:
            item = out.get()
            if item is DONE:
                break
            yield item

    @staticmethod
    def _to_event(payload):
        """
        Turn ONE LaserData record into our SensorEvent.

        TODO(sponsor table): this is the ONE piece we can't know until you ask
        "what fields does each record carry?". Once you know, fill in the map
        below. The commented example shows the SHAPE -- the field names are a
        guess, so confirm them before trusting them.

            from sim.sensors import SensorEvent
            return SensorEvent(
                kind=payload["kind"],        # "motion" | "temperature" | "request"
                room=payload["room"],
                value=payload["value"],
                person=payload.get("person"),
            )
        """
        raise NotImplementedError(
            "Confirm LaserData record fields at the table, then map them to "
            "SensorEvent here (see the example in this function's docstring)."
        )


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
