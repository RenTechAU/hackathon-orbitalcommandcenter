"""
Walking skeleton -- the whole pipeline, end to end, in one file.

    LaserData  ->  FalkorDB  ->  Guild.ai  ->  RocketRide
    (now)          (ever)        (decide)      (do)

Run it:   python main.py

It works with ZERO sponsor SDKs installed. That is deliberate. Get this green
first, then replace one adapter at a time. Never be in a state where nothing runs.
"""

import os
import pathlib
from collections import defaultdict

from sim.sensors import demo_script
from memory.graph import HouseholdMemory
from adapters.vendors import Actuator, Council, LiveFeed


def run(events, memory, council, actuator):
    pending = defaultdict(dict)  # room -> {person: requested_value}

    for ev in events:
        if ev.kind == "motion" and ev.person:
            memory.enters_room(ev.person, ev.room)
            print(f"[SEE] {ev.person} entered {ev.room}")

        elif ev.kind == "temperature":
            print(f"[SEE] {ev.room} is {ev.value}F")

        elif ev.kind == "request" and ev.person:
            device, value = next(iter(ev.value.items()))
            memory.set_preference(ev.person, device, value)
            pending[ev.room][ev.person] = value
            print(f"[ASK] {ev.person} wants {device} = {value} in {ev.room}")

            occupants = memory.who_is_in(ev.room)
            reqs = {p: v for p, v in pending[ev.room].items() if p in occupants}

            if len(reqs) > 1:
                winner, value, why = council.resolve(reqs, memory, ev.room, topic=device)
                print(f"[HMM] conflict in {ev.room}: {reqs}")
                print(f"[WHY] {why}")
                actuator.act(device, value, because=f"{winner} won: {why}")
                pending[ev.room].clear()


def load_env(path=".env"):
    """Read .env into os.environ. Hand-rolled so we add no dependency."""
    p = pathlib.Path(__file__).resolve().parent.parent / path
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def build_feed():
    """
    Use the real LaserData stream when it's available, the plain generator when
    it isn't -- and SAY WHICH, out loud, every run.

    Force the fallback with LASER_LIVE=0. Do that if the stack misbehaves during
    the demo: a working fallback beats a broken integration at 6 PM.
    """
    if os.getenv("LASER_LIVE") == "0":
        print("[feed] LASER_LIVE=0 -- forced fallback (no LaserData)")
        return LiveFeed(use_real=False)
    try:
        import laser_sdk  # noqa: F401
        feed = LiveFeed(use_real=True)
        print("[feed] LaserData: REAL (events go through the Iggy log)")
        return feed
    except Exception as exc:
        print(f"[feed] LaserData unavailable ({exc}) -- falling back")
        return LiveFeed(use_real=False)


if __name__ == "__main__":
    load_env()

    memory = HouseholdMemory()
    memory.reset()  # clean slate so the two-conflict demo lands every run
    feed = build_feed()
    council = Council(use_real=False)
    actuator = Actuator(use_real=False)

    print("=" * 62)
    print("SMART HOME ORCHESTRATOR -- scripted demo")
    print("=" * 62)
    run(feed.events(demo_script()), memory, council, actuator)
    print("=" * 62)
    print("Note the second conflict: same inputs, different outcome.")
    print("That difference IS the memory. Point at the graph when you say it.")
