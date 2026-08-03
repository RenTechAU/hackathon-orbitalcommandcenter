"""
A simulated 24 hours over the constellation.

WHY THIS EXISTS
---------------
The scripted demo proves the broker WORKS. It does not prove it is BETTER than
what ground segments do today. This does.

It runs the same 24 hours twice, changing only the scheduling policy:

    priority   the status quo. A fixed table: highest urgency wins, ties
               broken by a fixed satellite order. This is how real ground
               segments schedule, and its failure mode is STARVATION -- the
               satellite at the bottom of the table never gets a window.

    broker     ours. Whoever has yielded most often at this station wins,
               and a safety rule can still overrule that for an emergency.

Everything else is identical: same orbits, same passes, same emergencies, same
data arriving. So any difference in the results is caused by the policy alone.

HONESTY NOTES -- read these before quoting any number
-----------------------------------------------------
1. The satellites are invented. The orbit model is a crude circular
   approximation (see telemetry.py). This shows the SHAPE of the problem, not
   a real mission plan.
2. This runs the fairness rules DETERMINISTICALLY, not through the live Guild
   agents. Hundreds of contentions at ~8 seconds per agent call is hours of
   wall time. The live demo uses the real agents; this measures the policy.
3. The baseline is implemented as a genuine fixed-priority scheduler, not a
   straw man. If it wins, the deck says it wins.

Run it:  python src/sim/day.py
"""

import json
import itertools
from collections import defaultdict

from telemetry import STATIONS, visible_station


# ----------------------------------------------------------------- the fleet
# `priority` is the satellite's rank in the status-quo table, 1 = highest.
# That ranking is what starves the bottom of the fleet.
FLEET = {
    "SAT-1": {"mission": "imaging",  "payload": "surface-imagery", "priority": 3},
    "SAT-2": {"mission": "comms",    "payload": "relay-traffic",   "priority": 2},
    "SAT-3": {"mission": "weather",  "payload": "storm-imagery",   "priority": 1},
    "SAT-4": {"mission": "science",  "payload": "field-survey",    "priority": 4},
    "SAT-5": {"mission": "imaging",  "payload": "coastal-survey",  "priority": 5},
    "SAT-6": {"mission": "research", "payload": "particle-counts", "priority": 6},
}

# How fast each satellite fills its buffer, in GB per minute.
GB_PER_MIN = {"SAT-1": 0.9, "SAT-2": 0.6, "SAT-3": 1.4,
              "SAT-4": 0.5, "SAT-5": 0.8, "SAT-6": 0.4}

SLOT_MIN = 5       # decisions are made every 5 simulated minutes
WINDOW_GB = 12.0   # how much a satellite can downlink in one window
DAY_MIN = 24 * 60

# --------------------------------------------------------------- the events
# Emergencies are EPISODIC. This matters: if a satellite were permanently
# critical, the safety veto would fire constantly and the fairness rule would
# stop meaning anything. A conjunction warning arrives, gets downlinked, and
# is over.
#
# (start_minute, duration_minutes, satellite, what)
EMERGENCIES = [
    (6 * 60,  45, "SAT-4", "conjunction-warning"),   # collision alert
    (14 * 60, 45, "SAT-2", "conjunction-warning"),
    (22 * 60, 45, "SAT-5", "conjunction-warning"),
]

# A ground station going offline -- weather closes Svalbard for two hours.
# Fewer dishes, same demand: contention gets sharper.
OUTAGES = [(11 * 60, 120, "Svalbard")]

# A solar storm: SAT-3's weather imagery becomes urgent and its buffer fills
# three times as fast. Not an emergency, but a sustained surge.
STORM = (19 * 60, 90, "SAT-3")


def urgency_at(sat, minute):
    """What is this satellite carrying right now?"""
    for start, dur, who, _what in EMERGENCIES:
        if who == sat and start <= minute < start + dur:
            return "critical"
    start, dur, who = STORM
    if who == sat and start <= minute < start + dur:
        return "high"
    return "routine"


def station_up(station, minute):
    for start, dur, who in OUTAGES:
        if who == station and start <= minute < start + dur:
            return False
    return True


def inflow(sat, minute):
    start, dur, who = STORM
    rate = GB_PER_MIN[sat]
    if who == sat and start <= minute < start + dur:
        rate *= 3.0
    return rate * SLOT_MIN


# ------------------------------------------------------------- the policies
def pick_priority(candidates, state, station, minute):
    """
    THE STATUS QUO. Highest urgency first, then the fixed priority table.

    Deliberately implemented properly. It is not a bad scheduler -- it always
    serves emergencies instantly, which is exactly what it is designed to do.
    Its blind spot is that it has no memory, so the same satellites win every
    single time and the bottom of the table never gets served.
    """
    rank = {"critical": 0, "high": 1, "routine": 2}
    return min(candidates,
               key=lambda s: (rank[urgency_at(s, minute)], FLEET[s]["priority"]))


def pick_broker(candidates, state, station, minute):
    """
    OURS. Whoever has yielded most often AT THIS STATION wins. A safety rule
    can still overrule that when someone is carrying an emergency.

    This is the same logic as Council.resolve(), applied deterministically.
    """
    # Safety first, and it is an override, not a tie-break: an emergency wins
    # outright regardless of whose turn it is.
    critical = [s for s in candidates if urgency_at(s, minute) == "critical"]
    if critical:
        return min(critical, key=lambda s: FLEET[s]["priority"]), True

    # Otherwise: whoever has given way most often here. This is the memory --
    # in the real system it is a graph traversal over YIELDED edges.
    return max(candidates, key=lambda s: (state["yielded"][(s, station)],
                                          state["backlog"][s])), False


# ------------------------------------------------------------------ the run
def run_day(policy):
    """Simulate 24 hours under one policy and return what happened."""
    state = {
        "backlog": defaultdict(float),
        "yielded": defaultdict(int),          # (sat, station) -> times given way
        "windows": defaultdict(int),          # sat -> windows granted
        "delivered": defaultdict(float),      # sat -> GB downlinked
        "last_window": {s: 0 for s in FLEET},  # sat -> minute of last window
        "max_gap": defaultdict(int),          # sat -> longest wait, minutes
        "vetoes": 0,
        "contentions": 0,
        "critical_waits": [],                 # minutes an emergency waited
    }
    pending_critical = {}   # sat -> minute the emergency began

    for minute in range(0, DAY_MIN, SLOT_MIN):
        # data arrives
        for sat in FLEET:
            state["backlog"][sat] += inflow(sat, minute)
            if urgency_at(sat, minute) == "critical" and sat not in pending_critical:
                pending_critical[sat] = minute

        # who can see what
        wants = defaultdict(list)
        for i, sat in enumerate(FLEET):
            if state["backlog"][sat] < 1.0:
                continue
            station = visible_station(i, minute * 60)
            if station and station_up(station, minute):
                wants[station].append(sat)

        # one dish per station, so someone has to lose
        for station, candidates in wants.items():
            if len(candidates) > 1:
                state["contentions"] += 1

            if policy == "priority":
                winner = pick_priority(candidates, state, station, minute)
            else:
                winner, vetoed = pick_broker(candidates, state, station, minute)
                if vetoed and len(candidates) > 1:
                    state["vetoes"] += 1

            # the winner downlinks
            sent = min(WINDOW_GB, state["backlog"][winner])
            state["backlog"][winner] -= sent
            state["delivered"][winner] += sent
            state["windows"][winner] += 1
            gap = minute - state["last_window"][winner]
            state["max_gap"][winner] = max(state["max_gap"][winner], gap)
            state["last_window"][winner] = minute

            if winner in pending_critical:
                state["critical_waits"].append(minute - pending_critical.pop(winner))

            # everyone else gave way -- THIS is the memory being written
            for loser in candidates:
                if loser != winner:
                    state["yielded"][(loser, station)] += 1

    # satellites that never got served at all still have a gap to the end
    for sat in FLEET:
        gap = DAY_MIN - state["last_window"][sat]
        state["max_gap"][sat] = max(state["max_gap"][sat], gap)

    return state


def summarise(state):
    windows = [state["windows"][s] for s in FLEET]
    delivered = [state["delivered"][s] for s in FLEET]
    return {
        "windows": {s: state["windows"][s] for s in FLEET},
        "delivered": {s: round(state["delivered"][s], 1) for s in FLEET},
        "max_gap_min": {s: state["max_gap"][s] for s in FLEET},
        "total_windows": sum(windows),
        "total_gb": round(sum(delivered), 1),
        "starved": sum(1 for w in windows if w == 0),
        "worst_gap_h": round(max(state["max_gap"].values()) / 60, 1),
        "fairness_ratio": (round(max(windows) / min(windows), 1)
                           if min(windows) else None),
        "contentions": state["contentions"],
        "vetoes": state["vetoes"],
        "critical_max_wait_min": (max(state["critical_waits"])
                                  if state["critical_waits"] else 0),
        "critical_served": len(state["critical_waits"]),
    }


if __name__ == "__main__":
    results = {p: summarise(run_day(p)) for p in ("priority", "broker")}

    print("=" * 72)
    print("24 SIMULATED HOURS -- same orbits, same data, same emergencies")
    print("=" * 72)

    for name, r in results.items():
        label = "FIXED PRIORITY (status quo)" if name == "priority" else "ORBITAL BROKER (ours)"
        print(f"\n{label}")
        print(f"  windows per satellite : {r['windows']}")
        print(f"  GB delivered          : {r['delivered']}")
        print(f"  satellites starved    : {r['starved']}")
        print(f"  worst wait for a dish : {r['worst_gap_h']} h")
        print(f"  busiest/quietest ratio: {r['fairness_ratio']}")
        print(f"  total GB downlinked   : {r['total_gb']}")
        print(f"  emergencies served    : {r['critical_served']}"
              f"  (worst wait {r['critical_max_wait_min']} min)")

    print("\n" + "=" * 72)
    p, b = results["priority"], results["broker"]
    print(f"contentions resolved: {b['contentions']}   safety vetoes: {b['vetoes']}")
    print(f"starved satellites : {p['starved']} -> {b['starved']}")
    print(f"worst wait         : {p['worst_gap_h']}h -> {b['worst_gap_h']}h")
    print(f"emergency max wait : {p['critical_max_wait_min']}min -> "
          f"{b['critical_max_wait_min']}min")
    print("=" * 72)

    with open("docs/day_results.json", "w") as fh:
        json.dump(results, fh, indent=2)
    print("wrote docs/day_results.json")
