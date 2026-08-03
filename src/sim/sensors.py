"""
Fake sensor stream. Zero dependencies, works offline, works right now.

This is your safety net: if LaserData fights you at 11am, you keep building
against this and swap the source later. Nobody is grading your data source
at 6pm -- they are watching your demo.

Run standalone to eyeball it:  python sim/sensors.py
"""

import itertools
import random
import time
from dataclasses import dataclass, asdict


PEOPLE = ["jeremy", "sam"]
ROOMS = ["living_room", "bedroom", "kitchen"]


@dataclass
class SensorEvent:
    kind: str          # motion | temperature | door | request
    room: str
    value: object
    person: str | None = None
    ts: float = 0.0

    def dict(self):
        return asdict(self)


def stream(seed: int = 7, delay: float = 0.5):
    """Yield sensor events forever. Deterministic-ish so demos repeat."""
    rng = random.Random(seed)
    for i in itertools.count():
        r = rng.random()
        if r < 0.35:
            ev = SensorEvent("motion", rng.choice(ROOMS), True, rng.choice(PEOPLE))
        elif r < 0.7:
            ev = SensorEvent("temperature", rng.choice(ROOMS), round(rng.uniform(66, 76), 1))
        else:
            ev = SensorEvent("door", rng.choice(ROOMS), rng.choice(["open", "closed"]))
        ev.ts = time.time()
        yield ev
        time.sleep(delay)


def demo_script():
    """
    The scripted sequence you actually demo. Do NOT demo the random stream --
    you want the conflict to happen on cue, twice, so the memory payoff lands.

    Beat 1: both people enter the living room
    Beat 2: they request incompatible temperatures  -> system has no history, picks one
    Beat 3: (later) same conflict again             -> system remembers who conceded
    """
    now = time.time()
    return [
        SensorEvent("motion", "living_room", True, "jeremy", now),
        SensorEvent("motion", "living_room", True, "sam", now + 1),
        SensorEvent("request", "living_room", {"thermostat": 68}, "jeremy", now + 2),
        SensorEvent("request", "living_room", {"thermostat": 74}, "sam", now + 3),
        # --- narrate the graph here, then replay the conflict ---
        SensorEvent("request", "living_room", {"thermostat": 68}, "jeremy", now + 60),
        SensorEvent("request", "living_room", {"thermostat": 74}, "sam", now + 61),
    ]


if __name__ == "__main__":
    for ev in itertools.islice(stream(), 10):
        print(ev.dict())
