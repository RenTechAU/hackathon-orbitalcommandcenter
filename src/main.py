"""
Walking skeleton -- the whole pipeline, end to end, in one file.

    LaserData  ->  FalkorDB  ->  Guild.ai  ->  RocketRide
    (now)          (ever)        (decide)      (do)

Run it:   python main.py

It works with ZERO sponsor SDKs installed. That is deliberate. Get this green
first, then replace one adapter at a time. Never be in a state where nothing runs.
"""

from collections import defaultdict

from sim.sensors import demo_script
from memory.graph import HouseholdMemory
from adapters.vendors import Actuator, Council


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


if __name__ == "__main__":
    memory = HouseholdMemory()
    memory.reset()  # clean slate so the two-conflict demo lands every run
    council = Council(use_real=False)
    actuator = Actuator(use_real=False)

    print("=" * 62)
    print("SMART HOME ORCHESTRATOR -- scripted demo")
    print("=" * 62)
    run(demo_script(), memory, council, actuator)
    print("=" * 62)
    print("Note the second conflict: same inputs, different outcome.")
    print("That difference IS the memory. Point at the graph when you say it.")
