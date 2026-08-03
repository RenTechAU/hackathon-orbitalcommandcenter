"""
The 24-hour policy comparison, run over REAL pass geometry.

Same experiment as day.py, but nothing about the sky is invented:

  orbits          real TLEs from CelesTrak, propagated with sgp4
  ground stations real sites from the SatNOGS open network
  passes          real visibility, 10 degree elevation mask

The only thing simulated is the SCHEDULING POLICY -- who gets the dish when
two satellites are overhead at once. That is the thing we are actually
proposing, so it is the thing that should be simulated.

Two policies, same sky, same data arriving, same emergencies:

  priority   the status quo. Fixed table: urgency first, then a fixed rank.
             Always serves emergencies instantly. Has no memory, so the same
             satellites win every time and the bottom of the table starves.

  broker     ours. Whoever has yielded most at this station wins, and safety
             can still overrule that.

Run it:  python src/sim/real_day.py
"""

import json
import pathlib
from collections import defaultdict

import realsky

SLOT_MIN = 1
WINDOW_GB = 4.0     # a one-minute slot moves less than a full pass
DAY_MIN = 24 * 60


def build_fleet(names):
    """
    Give each real satellite a rank and a data rate.

    Assigned by position in the list, not cherry-picked: the point is to show
    what a fixed ranking does to whoever sits at the bottom of it, and any
    fixed ranking has a bottom.
    """
    fleet = {}
    for i, name in enumerate(names):
        fleet[name] = {
            "priority": i + 1,                    # 1 = top of the table
            "gb_per_min": 0.35 + 0.05 * (i % 5),  # spread, not random
        }
    return fleet


def emergencies_for(names):
    """
    Episodic emergencies -- a conjunction warning arrives, is downlinked, and
    is over. If a satellite were permanently critical the veto would fire
    constantly and the fairness rule would stop meaning anything.

    (start_minute, duration, satellite)
    """
    picks = [names[2], names[7], names[-1]] if len(names) >= 8 else names[:1]
    return [(5 * 60 + 20, 40, picks[0]),
            (13 * 60 + 45, 40, picks[1]),
            (20 * 60 + 10, 40, picks[2])]


def run(policy, passes, fleet, emergencies):
    backlog = defaultdict(float)
    yielded = defaultdict(int)
    windows = defaultdict(int)
    delivered = defaultdict(float)
    last_seen = {s: 0 for s in fleet}
    max_gap = defaultdict(int)
    stats = {"contentions": 0, "vetoes": 0, "critical_waits": []}
    pending = {}

    def urgency(sat, minute):
        for start, dur, who in emergencies:
            if who == sat and start <= minute < start + dur:
                return "critical"
        return "routine"

    for minute in range(DAY_MIN):
        for sat in fleet:
            backlog[sat] += fleet[sat]["gb_per_min"] * SLOT_MIN
            if urgency(sat, minute) == "critical" and sat not in pending:
                pending[sat] = minute

        slot = passes.get(str(minute), {})
        if not slot:
            continue

        # who is competing for each dish this minute
        at_station = defaultdict(list)
        for sat, stations in slot.items():
            if backlog[sat] < 0.5:
                continue
            for st in stations:
                at_station[st].append(sat)

        # a dish serves one satellite at a time
        for station, candidates in at_station.items():
            if len(candidates) > 1:
                stats["contentions"] += 1

            if policy == "priority":
                rank = {"critical": 0, "routine": 1}
                winner = min(candidates, key=lambda s: (rank[urgency(s, minute)],
                                                        fleet[s]["priority"]))
            else:
                critical = [s for s in candidates if urgency(s, minute) == "critical"]
                if critical:
                    winner = min(critical, key=lambda s: fleet[s]["priority"])
                    if len(candidates) > 1:
                        stats["vetoes"] += 1
                else:
                    # THE MEMORY: whoever has given way most often here
                    winner = max(candidates,
                                 key=lambda s: (yielded[(s, station)], backlog[s]))

            sent = min(WINDOW_GB, backlog[winner])
            backlog[winner] -= sent
            delivered[winner] += sent
            windows[winner] += 1
            max_gap[winner] = max(max_gap[winner], minute - last_seen[winner])
            last_seen[winner] = minute
            if winner in pending:
                stats["critical_waits"].append(minute - pending.pop(winner))

            for loser in candidates:
                if loser != winner:
                    yielded[(loser, station)] += 1

    for sat in fleet:
        max_gap[sat] = max(max_gap[sat], DAY_MIN - last_seen[sat])

    w = [windows[s] for s in fleet]
    return {
        "windows": {s: windows[s] for s in fleet},
        "delivered_gb": {s: round(delivered[s], 1) for s in fleet},
        "max_gap_h": {s: round(max_gap[s] / 60, 1) for s in fleet},
        "total_gb": round(sum(delivered.values()), 1),
        "starved": sum(1 for x in w if x == 0),
        "worst_gap_h": round(max(max_gap.values()) / 60, 1),
        "busiest_quietest_ratio": (round(max(w) / min(w), 1) if min(w) else None),
        "contentions": stats["contentions"],
        "vetoes": stats["vetoes"],
        "critical_served": len(stats["critical_waits"]),
        "critical_max_wait_min": max(stats["critical_waits"]) if stats["critical_waits"] else 0,
    }


if __name__ == "__main__":
    sky = realsky.build()
    names = sky["satellites"]
    fleet = build_fleet(names)
    emerg = emergencies_for(names)

    results = {p: run(p, sky["timeline"], fleet, emerg) for p in ("priority", "broker")}

    print("=" * 74)
    print("24 HOURS OVER REAL ORBITS -- same sky, same data, two policies")
    print("=" * 74)
    print(f"satellites : {len(names)} real (CelesTrak TLEs, sgp4)")
    print(f"stations   : {len(sky['stations'])} real (SatNOGS open network)")
    print(f"emergencies: {len(emerg)} conjunction warnings")

    for key, r in results.items():
        label = "FIXED PRIORITY (status quo)" if key == "priority" else "ORBITAL BROKER (ours)"
        print(f"\n{label}")
        print(f"  satellites never served : {r['starved']} of {len(names)}")
        print(f"  worst wait for a dish   : {r['worst_gap_h']} h")
        print(f"  busiest:quietest ratio  : {r['busiest_quietest_ratio']}")
        print(f"  total downlinked        : {r['total_gb']} GB")
        print(f"  emergencies served      : {r['critical_served']}"
              f" (worst wait {r['critical_max_wait_min']} min)")

    p, b = results["priority"], results["broker"]
    print("\n" + "=" * 74)
    print(f"contentions      : {b['contentions']}      safety overrides: {b['vetoes']}")
    print(f"starved          : {p['starved']} -> {b['starved']}")
    print(f"worst wait       : {p['worst_gap_h']}h -> {b['worst_gap_h']}h")
    print(f"emergency wait   : {p['critical_max_wait_min']}min -> {b['critical_max_wait_min']}min")
    print("=" * 74)

    out = {
        "generated_utc": sky["generated_utc"],
        "window_start_utc": sky["window_start_utc"],
        "satellites": names,
        "stations": sky["stations"],
        "sources": sky["sources"],
        "emergencies": [{"minute": m, "duration": d, "satellite": s} for m, d, s in emerg],
        "results": results,
    }
    pathlib.Path("docs/real_day_results.json").write_text(json.dumps(out, indent=1))
    print("wrote docs/real_day_results.json")
