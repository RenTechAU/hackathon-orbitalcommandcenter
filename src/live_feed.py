"""
Drive the dashboard from the REAL Guild.ai agents.

The published dashboard replays the broker's logic in JavaScript, because a
sandboxed page cannot call Guild and each agent call takes ~8 seconds. Running
locally there is no such limit, so this writes genuine agent decisions to a
file the dashboard polls.

    terminal 1:  python src/live_feed.py
    terminal 2:  python -m http.server 8080 --directory docs
    browser:     http://127.0.0.1:8080/mission-control.html?live=1

Every entry it writes came back from an agent on app.guild.ai. Nothing here is
scripted -- if Guild is down, the file stops growing and the dashboard says so
rather than inventing a decision.
"""

import json
import pathlib
import random
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from adapters.vendors import Council
from memory.constellation import ConstellationMemory

OUT = pathlib.Path("docs/live_decisions.json")
POLL_SECONDS = 2

# Four constituencies with genuinely incompatible ideas of "urgent", using real
# satellite names pulled from the CelesTrak catalogue.
CONSTITUENCIES = {
    "COMMERCIAL":  {"urgency": "routine",  "payload": "relay-traffic"},
    "EARTH OBS":   {"urgency": "high",     "payload": "storm-imagery"},
    "SCIENCE":     {"urgency": "routine",  "payload": "transient-event"},
    "CUBESAT/EDU": {"urgency": "routine",  "payload": "student-telemetry"},
}
CRITICAL_PAYLOAD = "conjunction-warning"


def load_names():
    try:
        sats = json.loads(pathlib.Path("docs/sat_names.json").read_text())
        dishes = json.loads(pathlib.Path("docs/dish_names.json").read_text())
    except FileNotFoundError:
        sys.exit("Run src/sim/realsky.py first -- docs/sat_names.json is missing.")
    key = {"COMMERCIAL": "commercial", "EARTH OBS": "earth-obs",
           "SCIENCE": "science", "CUBESAT/EDU": "cubesat"}
    return {k: sats[v] for k, v in key.items()}, dishes


def main():
    council = Council(use_real=True)
    memory = ConstellationMemory(graph_name="live_dashboard")
    memory.reset()

    sat_names, dishes = load_names()
    rng = random.Random(11)
    decisions = []

    print("[live] Guild agents driving the dashboard. Ctrl-C to stop.")
    print(f"[live] writing {OUT}")

    while True:
        dish = rng.choice(dishes)["name"]
        pair = rng.sample(list(CONSTITUENCIES), 2)

        # occasionally one of them is carrying an emergency, so the safety
        # officer has something real to overrule
        emergency = rng.random() < 0.25
        crit_side = rng.choice(pair) if emergency else None

        entrants = {}
        for side in pair:
            spec = CONSTITUENCIES[side]
            sat = rng.choice(sat_names[side])
            memory.sees_station(side, dish)
            if side == crit_side:
                memory.set_payload(side, CRITICAL_PAYLOAD, "critical")
            else:
                memory.set_payload(side, spec["payload"], spec["urgency"])
            entrants[side] = rng.randint(4, 90)   # backlog GB
            decisions and None
            sat_names.setdefault(side, [])
            spec["_last_sat"] = sat

        t0 = time.time()
        winner, loser, why = council.resolve(entrants, memory, dish)
        took = round(time.time() - t0, 1)

        entry = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "dish": dish,
            "winner": winner,
            "loser": loser,
            "why": why,
            "veto": why.startswith("SAFETY VETO"),
            "backlogs": entrants,
            "sats": {s: CONSTITUENCIES[s].get("_last_sat", "") for s in pair},
            "seconds": took,
            "source": "guild.ai",
        }
        decisions.insert(0, entry)
        del decisions[40:]

        OUT.write_text(json.dumps({
            "updated": entry["ts"],
            "live": True,
            "decisions": decisions,
        }, indent=1))

        flag = "VETO " if entry["veto"] else ""
        print(f"[live] {flag}{dish:22} {winner:12} beat {loser:12} ({took}s)  {why[:60]}")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[live] stopped")
