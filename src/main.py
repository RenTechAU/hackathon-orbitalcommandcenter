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

from sim.telemetry import demo_script
from memory.constellation import ConstellationMemory
from adapters.vendors import Actuator, Council, LiveFeed


def run(events, memory, council, actuator):
    pending = defaultdict(dict)  # station -> {satellite: backlog_gb}

    for ev in events:
        # --- the constellation describing itself --------------------------
        if ev.kind == "payload":
            memory.set_payload(ev.satellite, ev.value["name"], ev.value["urgency"])

        elif ev.kind == "link":
            memory.add_link(ev.satellite, ev.value["to"], ev.value["bandwidth_gbps"])

        elif ev.kind == "history":
            # An outcome from an earlier orbit, before today's run.
            memory.record_yield(ev.satellite, ev.value["yielded_to"], ev.station)
            print(f"[MEM] seeded: {ev.satellite} yielded to "
                  f"{ev.value['yielded_to']} at {ev.station} on an earlier orbit")

        # --- live position telemetry --------------------------------------
        elif ev.kind == "view":
            memory.sees_station(ev.satellite, ev.station)
            if ev.station:
                print(f"[SEE] {ev.satellite} acquired {ev.station}")
            else:
                print(f"[SEE] {ev.satellite} lost its ground station")

        # --- a satellite asks for airtime ---------------------------------
        elif ev.kind == "request":
            gb = ev.value["backlog_gb"]

            # No station in view. Its only route home is through the laser
            # mesh -- this is the variable-depth graph query.
            if ev.station is None:
                print(f"[ASK] {ev.satellite} has {gb}GB queued but sees no station")
                path, hops = memory.relay_path(ev.satellite)
                if path:
                    print(f"[HOP] relay found in {hops} hops: {' -> '.join(path)}")
                    actuator.act("relay", path[-1],
                                 because=f"{ev.satellite} routed via {' -> '.join(path[1:-1])}")
                else:
                    print(f"[HOP] no relay path -- {ev.satellite} must wait for a pass")
                continue

            pending[ev.station][ev.satellite] = gb
            print(f"[ASK] {ev.satellite} wants {ev.station}, {gb}GB queued")

            # Only satellites that can actually see the station get a say.
            in_view = memory.who_sees(ev.station)
            reqs = {s: g for s, g in pending[ev.station].items() if s in in_view}

            if len(reqs) > 1:
                print(f"[HMM] contention at {ev.station}: {reqs}")
                winner, loser, why = council.resolve(reqs, memory, ev.station)
                print(f"[WHY] {why}")
                actuator.act("downlink", winner,
                             because=f"{winner} got {ev.station} over {loser}: {why}")
                pending[ev.station].clear()


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


def build_actuator():
    """
    Same deal as build_feed: real RocketRide when we can, prints when we can't,
    and it says which out loud so you're never guessing during the demo.

    Force the fallback with ROCKETRIDE_LIVE=0.
    """
    if os.getenv("ROCKETRIDE_LIVE") == "0":
        print("[act] ROCKETRIDE_LIVE=0 -- forced fallback (prints only)")
        return Actuator(use_real=False)
    try:
        import rocketride  # noqa: F401
        actuator = Actuator(use_real=True)
        actuator.start()  # fail fast, before the judges are watching
        print("[act] RocketRide: REAL (actions run through a live pipeline)")
        return actuator
    except Exception as exc:
        print(f"[act] RocketRide unavailable ({exc}) -- falling back")
        return Actuator(use_real=False)


def build_council():
    """
    Real Guild.ai agents when the CLI is there and logged in, deterministic
    logic when it isn't -- and it says which, out loud, every run.

    Force the fallback with GUILD_LIVE=0. Do that if the agents are slow or
    flaky during the demo: each call takes several seconds, and a fast correct
    answer beats a slow broken one at 6 PM.
    """
    import shutil
    import subprocess

    if os.getenv("GUILD_LIVE") == "0":
        print("[council] GUILD_LIVE=0 -- forced fallback (deterministic logic)")
        return Council(use_real=False)
    if not shutil.which("guild"):
        print("[council] guild CLI not installed -- falling back")
        return Council(use_real=False)
    try:
        # Fail fast, before the judges are watching.
        done = subprocess.run(["guild", "--non-interactive", "auth", "status"],
                              capture_output=True, text=True, timeout=20)
        if done.returncode != 0:
            raise RuntimeError("not authenticated -- run: guild auth login")
        print("[council] Guild.ai: REAL (advocate + mission-safety agents)")
        return Council(use_real=True)
    except Exception as exc:
        print(f"[council] Guild unavailable ({exc}) -- falling back")
        return Council(use_real=False)


if __name__ == "__main__":
    load_env()

    memory = ConstellationMemory()
    memory.reset()  # clean slate so the two-conflict demo lands every run
    feed = build_feed()
    council = build_council()
    actuator = build_actuator()

    print("=" * 62)
    print("ORBITAL CONTACT BROKER -- scripted demo")
    print("=" * 62)
    try:
        run(feed.events(demo_script()), memory, council, actuator)
    finally:
        actuator.close()
    print("=" * 62)
    print("Note the two contentions at Svalbard: same inputs, different winner.")
    print("That difference IS the memory. Point at the graph when you say it.")
