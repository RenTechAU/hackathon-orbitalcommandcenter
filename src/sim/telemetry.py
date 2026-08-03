"""
Fake satellite telemetry. Zero dependencies, works offline, works right now.

This is the safety net: if LaserData fights you at 3pm, you keep building
against this and swap the source back later. Nobody is grading your data
source at 6pm -- they are watching your demo.

Run standalone to eyeball it:  python src/sim/telemetry.py
"""

import itertools
import math
import time
from dataclasses import dataclass, asdict


# Real ground stations, real coordinates. Free authenticity -- costs nothing,
# and "Svalbard" sounds a lot better in a pitch than "station_1".
STATIONS = {
    "Svalbard":  (78.23, 15.39),
    "Kiruna":    (67.86, 20.96),
    "Fairbanks": (64.86, -147.85),
    "Santiago":  (-33.15, -70.67),
    "Hawaii":    (22.13, -159.66),
}

# mission, and what it is carrying. `urgency` drives the safety veto.
SATELLITES = {
    "SAT-1": ("imaging",  "surface-imagery",     "routine"),
    "SAT-2": ("comms",    "relay-traffic",       "routine"),
    "SAT-3": ("weather",  "storm-imagery",       "high"),
    "SAT-4": ("science",  "conjunction-warning", "critical"),
}

# Which satellites can shoot a laser at which. This mesh is what makes the
# relay query possible -- a satellite over open ocean has no ground station,
# so its only route home is through a neighbour.
LASER_LINKS = [
    ("SAT-3", "SAT-2", 1.2),
    ("SAT-2", "SAT-1", 2.4),
    ("SAT-1", "SAT-4", 0.8),
]


@dataclass
class TelemetryEvent:
    """
    One thing that happened in orbit.

    kind:
      view     -- satellite came into view of a station (or lost it, station=None)
      link     -- a laser link exists between two satellites
      payload  -- what a satellite is carrying, and how urgent it is
      request  -- a satellite is asking for a downlink window
    """
    kind: str
    satellite: str | None = None
    station: str | None = None
    value: object = None
    ts: float = 0.0

    def dict(self):
        return asdict(self)


# ---------------------------------------------------------------- orbit maths
def _subpoint(sat_index, t, period_s=5400.0, inclination=97.0):
    """
    Where on Earth is this satellite right now?

    Deliberately crude: a circular orbit, ignoring Earth's rotation and orbital
    mechanics beyond the basics. It is plausible enough to drive a dashboard
    and it needs no dependencies. Returns (latitude, longitude) in degrees.
    """
    # how far around one orbit we are, 0..2pi. Satellites are spaced out so
    # they do not all sit on top of each other.
    angle = 2 * math.pi * ((t / period_s) + sat_index * 0.25)
    inc = math.radians(inclination)
    lat = math.degrees(math.asin(math.sin(inc) * math.sin(angle)))
    lon = (math.degrees(angle) % 360) - 180
    return lat, lon


def _great_circle_km(a, b):
    """Distance over the Earth's surface between two (lat, lon) points."""
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    d = math.acos(
        max(-1.0, min(1.0,
            math.sin(lat1) * math.sin(lat2)
            + math.cos(lat1) * math.cos(lat2) * math.cos(lon2 - lon1)))
    )
    return 6371.0 * d


def visible_station(sat_index, t, horizon_km=2200.0):
    """
    Which station can this satellite talk to right now, if any?

    A satellite in low orbit can only see a circle of ground beneath it.
    `horizon_km` is the radius of that circle. Returns a station name or None
    -- and None is the interesting case, because that is when it needs a relay.
    """
    here = _subpoint(sat_index, t)
    best, best_km = None, horizon_km
    for name, coords in STATIONS.items():
        km = _great_circle_km(here, coords)
        if km < best_km:
            best, best_km = name, km
    return best


def stream(delay: float = 0.5, speed: float = 60.0):
    """
    Yield live telemetry forever, driven by the orbit maths above.

    Use this for the dashboard, NOT for the demo -- see demo_script() for why.
    `speed` compresses time so passes happen in seconds rather than minutes.
    """
    names = list(SATELLITES)
    in_view = {n: None for n in names}
    start = time.time()

    for _ in itertools.count():
        t = (time.time() - start) * speed
        for i, name in enumerate(names):
            station = visible_station(i, t)
            if station != in_view[name]:
                in_view[name] = station
                yield TelemetryEvent("view", name, station, None, time.time())
        time.sleep(delay)


# ------------------------------------------------------------------ the demo
def demo_script():
    """
    The scripted sequence you actually demo.

    Do NOT demo the live stream. You want each beat to fire on cue, in order,
    every single time -- especially the two conflicts, because the whole pitch
    is that they resolve differently.

    Beat 1  two satellites contend for Svalbard, no history  -> arbitrary, RECORDED
    Beat 2  the identical contention one orbit later         -> memory decides it
    Beat 3  a satellite with no station in view              -> relay path found
    Beat 4  fairness says preempt SAT-4, safety says no      -> agents disagree
    """
    now = time.time()
    ev = []
    n = itertools.count()

    def add(kind, sat=None, station=None, value=None):
        ev.append(TelemetryEvent(kind, sat, station, value, now + next(n)))

    # --- the constellation describes itself -------------------------------
    for sat, (_mission, payload, urgency) in SATELLITES.items():
        add("payload", sat, None, {"name": payload, "urgency": urgency})
    for a, b, bw in LASER_LINKS:
        add("link", a, None, {"to": b, "bandwidth_gbps": bw})

    # --- memory from earlier orbits ---------------------------------------
    # The broker has been running before today. Seeding one past outcome at
    # Kiruna is what sets up beat 4: it makes the fairness answer there
    # DEFINITE rather than a coin toss, so the safety veto has something real
    # to overrule. Svalbard is deliberately left blank -- beat 1 has to start
    # with genuinely no history or the "no history yet" line is a lie.
    add("history", "SAT-1", "Kiruna", {"yielded_to": "SAT-4"})

    # --- BEAT 1: first contention, no history -----------------------------
    add("view", "SAT-1", "Svalbard")
    add("view", "SAT-2", "Svalbard")
    add("request", "SAT-1", "Svalbard", {"backlog_gb": 40})
    add("request", "SAT-2", "Svalbard", {"backlog_gb": 35})

    # --- BEAT 2: same contention next orbit, memory decides ---------------
    add("request", "SAT-1", "Svalbard", {"backlog_gb": 40})
    add("request", "SAT-2", "Svalbard", {"backlog_gb": 35})

    # --- BEAT 3: no station in view, needs a relay ------------------------
    add("view", "SAT-3", None)                    # over the Pacific, blind
    add("request", "SAT-3", None, {"backlog_gb": 80})

    # --- BEAT 4: fairness loses to the safety agent -----------------------
    add("view", "SAT-1", "Kiruna")
    add("view", "SAT-4", "Kiruna")
    add("request", "SAT-1", "Kiruna", {"backlog_gb": 20})
    add("request", "SAT-4", "Kiruna", {"backlog_gb": 5})

    return ev


if __name__ == "__main__":
    print("--- scripted demo beats ---")
    for e in demo_script():
        print(e.dict())
    print("\n--- live orbit stream (first 6) ---")
    for e in itertools.islice(stream(delay=0.05, speed=4000), 6):
        print(e.dict())
