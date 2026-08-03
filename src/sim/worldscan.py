"""
Global contention scan: every online dish on Earth, the whole LEO population.

WHAT THIS DOES AND DOES NOT CLAIM
---------------------------------
Does:      measures real visibility between real satellites and real ground
           stations, for sampled 24-hour windows, using published orbital
           elements and the standard propagator.

Does not:  simulate a year minute by minute. That is not a compute limit, it
           is a physics one. A TLE is accurate for days to a couple of weeks;
           propagate one a year forward and the satellite is hundreds of km
           from where you say it is. Precise, confident, meaningless.

WHY SAMPLED DAYS ARE HONEST
---------------------------
Low-orbit ground tracks are quasi-repeating: a station sees roughly the same
pass pattern each day, drifting slowly as the orbit precesses. So a set of
sampled days spread over a year captures the real structure -- including the
seasonal drift -- without pretending to a precision the input data cannot
support. Every sampled day is propagated from elements at its own epoch.

Sources, all public and unauthenticated:
  CelesTrak  https://celestrak.org/NORAD/elements/gp.php?GROUP=active
  SatNOGS    https://network.satnogs.org/api/stations/

Run it:  python src/sim/worldscan.py
"""

import json
import math
import pathlib
import urllib.request
from datetime import datetime, timedelta, timezone

import numpy as np
from sgp4.api import SatrecArray, Satrec, jday

OUT = pathlib.Path("docs/worldscan.json")
CACHE_TLE = pathlib.Path("docs/active.tle")
EARTH_R = 6378.137
UA = "orbital-contact-broker/0.1 (hackathon research; contact via SatNOGS)"
MASK_DEG = 10.0          # a dish cannot usefully work below this elevation
STEP_MIN = 2             # 2-minute steps: a LEO pass lasts ~10 min, so this
                         # samples every pass several times
MAX_PERIOD_MIN = 130.0   # LEO only


# ---------------------------------------------------------------- ingestion
def load_leo_tles(limit=None):
    # Prefer the cached catalogue. CelesTrak rate-limits the bulk `active`
    # endpoint and starts returning 403 after a few pulls -- caching is the
    # polite thing to do anyway, and it means the demo never depends on wifi.
    if CACHE_TLE.exists():
        lines = CACHE_TLE.read_text(errors="replace").splitlines()
    else:
        url = "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle"
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=120) as r:
            body = r.read().decode(errors="replace")
        CACHE_TLE.write_text(body)
        lines = body.splitlines()

    names, sats = [], []
    for i in range(0, len(lines) - 2, 3):
        name = lines[i].strip()
        l1, l2 = lines[i + 1].strip(), lines[i + 2].strip()
        if not (l1.startswith("1 ") and l2.startswith("2 ")):
            continue
        try:
            revs = float(l2[52:63])
        except ValueError:
            continue
        if revs <= 0 or 1440.0 / revs > MAX_PERIOD_MIN:
            continue
        try:
            sats.append(Satrec.twoline2rv(l1, l2))
        except Exception:
            continue
        names.append(name)
        if limit and len(names) >= limit:
            break
    return names, sats


def load_stations(online_only=True):
    url = "https://network.satnogs.org/api/stations/?format=json"
    req = urllib.request.Request(url, headers={"Accept": "application/json",
                                               "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as r:
        raw = json.load(r)

    out = []
    for s in raw:
        lat, lon = s.get("lat"), s.get("lng")
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            continue
        if online_only and s.get("status") != "Online":
            continue
        out.append({"id": s.get("id"), "name": (s.get("name") or "").strip()[:28],
                    "lat": float(lat), "lon": float(lon),
                    "status": s.get("status")})
    return out


# ------------------------------------------------------------------ geometry
def station_ecef(stations):
    lat = np.radians([s["lat"] for s in stations])
    lon = np.radians([s["lon"] for s in stations])
    return np.stack([EARTH_R * np.cos(lat) * np.cos(lon),
                     EARTH_R * np.cos(lat) * np.sin(lon),
                     EARTH_R * np.sin(lat)], axis=1)          # (S,3)


def gmst(jd, fr):
    d = (jd - 2451545.0) + fr
    t = d / 36525.0
    deg = (280.46061837 + 360.98564736629 * d
           + 0.000387933 * t * t - t ** 3 / 38710000.0)
    return np.radians(deg % 360.0)


def scan_day(sats, stations, start, step_min=STEP_MIN):
    """
    One 24-hour window. Returns per-station pass-minutes and contention counts.

    Vectorised: sgp4's array API propagates every satellite at every timestep
    in one call, then the elevation test is a single matrix operation against
    all stations at once. Looping in Python would take hours.
    """
    n_steps = int(24 * 60 / step_min)
    times = [start + timedelta(minutes=step_min * k) for k in range(n_steps)]
    jds = np.array([jday(t.year, t.month, t.day, t.hour, t.minute, t.second)[0]
                    for t in times])
    frs = np.array([jday(t.year, t.month, t.day, t.hour, t.minute, t.second)[1]
                    for t in times])

    arr = SatrecArray(sats)
    err, pos, _vel = arr.sgp4(jds, frs)                       # (N, T, 3) km

    S = station_ecef(stations)                                # (S,3)
    up = S / np.linalg.norm(S, axis=1, keepdims=True)         # (S,3)

    sin_mask = math.sin(math.radians(MASK_DEG))
    pass_minutes = np.zeros(len(stations), dtype=np.int64)
    contended = np.zeros(len(stations), dtype=np.int64)
    sat_visible_steps = np.zeros(len(sats), dtype=np.int64)
    total_pairs = 0

    theta = gmst(jds, frs)                                    # (T,)
    cos_t, sin_t = np.cos(theta), np.sin(theta)

    # walk timesteps: one (N,S) matrix at a time keeps memory flat
    for k in range(n_steps):
        p = pos[:, k, :]                                      # (N,3) TEME
        ok = (err[:, k] == 0) & np.isfinite(p).all(axis=1)
        if not ok.any():
            continue
        p = p[ok]

        # rotate into an Earth-fixed frame
        xe = p[:, 0] * cos_t[k] + p[:, 1] * sin_t[k]
        ye = -p[:, 0] * sin_t[k] + p[:, 1] * cos_t[k]
        ze = p[:, 2]
        P = np.stack([xe, ye, ze], axis=1)                    # (n,3)

        # Two matmuls instead of an (n, S, 3) broadcast. Building that 3-D
        # array for 15,000 satellites x 4,000 dishes allocates gigabytes per
        # timestep; these identities give the same answer in (n,S):
        #     (P-S).up  = P.up - Re        (because S = Re * up)
        #     |P-S|^2   = |P|^2 - 2 P.S + Re^2
        Pup = P @ up.T                                        # (n,S)
        PS = P @ S.T                                          # (n,S)
        P2 = np.einsum("nd,nd->n", P, P)[:, None]             # (n,1)
        rng2 = np.maximum(P2 - 2 * PS + EARTH_R ** 2, 1e-9)
        with np.errstate(invalid="ignore", divide="ignore"):
            sin_el = (Pup - EARTH_R) / np.sqrt(rng2)
        vis = sin_el > sin_mask                               # (n,S)

        per_station = vis.sum(axis=0)                         # (S,)
        pass_minutes += per_station * step_min
        contended += (per_station > 1) * step_min
        total_pairs += int(per_station.sum())

        idx = np.flatnonzero(ok)
        sat_visible_steps[idx] += vis.any(axis=1)

    return {
        "pass_minutes": pass_minutes,
        "contended_minutes": contended,
        "sat_visible_steps": sat_visible_steps,
        "total_pair_minutes": total_pairs * step_min,
    }


# ---------------------------------------------------------------------- main
def sample_days(n=12, year_start=None):
    """One window per month, so a full year of precession is represented."""
    base = year_start or datetime.now(timezone.utc).replace(
        month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    return [base + timedelta(days=int(365 * i / n)) for i in range(n)]


if __name__ == "__main__":
    print("[worldscan] fetching the active satellite catalogue...")
    names, sats = load_leo_tles()
    print(f"[worldscan]   {len(sats)} LEO satellites")

    print("[worldscan] fetching SatNOGS ground stations...")
    online = load_stations(online_only=True)
    everything = load_stations(online_only=False)
    print(f"[worldscan]   {len(online)} online of {len(everything)} total")

    days = sample_days(6)
    print(f"[worldscan] scanning {len(days)} sampled 24h windows across a year")
    print(f"[worldscan]   {len(sats)} sats x {len(online)} dishes x "
          f"{int(24*60/STEP_MIN)} steps per window")

    totals = np.zeros(len(online), dtype=np.int64)
    contention = np.zeros(len(online), dtype=np.int64)
    sat_seen = np.zeros(len(sats), dtype=np.int64)
    pair_minutes = 0
    per_day = []

    for i, d in enumerate(days, 1):
        r = scan_day(sats, online, d)
        totals += r["pass_minutes"]
        contention += r["contended_minutes"]
        sat_seen += r["sat_visible_steps"]
        pair_minutes += r["total_pair_minutes"]
        per_day.append({"date": d.date().isoformat(),
                        "contended_dish_minutes": int(r["contended_minutes"].sum()),
                        "pass_dish_minutes": int(r["pass_minutes"].sum())})
        print(f"[worldscan]   {i:2}/{len(days)}  {d.date()}  "
              f"contended {int(r['contended_minutes'].sum()):>7} dish-min")

    for s, pm, cm in zip(online, totals, contention):
        s["pass_minutes"] = int(pm)
        s["contended_minutes"] = int(cm)
        s["contention_pct"] = round(100 * cm / pm, 1) if pm else 0.0

    busiest = sorted(online, key=lambda s: -s["contended_minutes"])[:15]
    never_used = sum(1 for s in online if s["pass_minutes"] == 0)
    reachable = int((sat_seen > 0).sum())

    data = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "method": {
            "windows": len(days),
            "window_hours": 24,
            "step_minutes": STEP_MIN,
            "elevation_mask_deg": MASK_DEG,
            "note": ("Sampled 24h windows spread across a year, NOT a continuous "
                     "year. TLEs are accurate for days to weeks; propagating one "
                     "a year forward is meaningless. LEO ground tracks are "
                     "quasi-repeating, so sampled days capture the structure "
                     "including seasonal precession."),
        },
        "sources": {
            "orbits": "CelesTrak GP/TLE, GROUP=active (public, no auth)",
            "ground_stations": "SatNOGS Network API (open volunteer network)",
            "propagator": "sgp4 (SatrecArray, vectorised)",
        },
        "scale": {
            "leo_satellites": len(sats),
            "stations_total": len(everything),
            "stations_online": len(online),
            "satellites_ever_visible": reachable,
            "satellites_never_visible": len(sats) - reachable,
            "stations_never_used": never_used,
            "total_pair_minutes": pair_minutes,
        },
        "per_day": per_day,
        "busiest": [{"name": s["name"], "lat": s["lat"], "lon": s["lon"],
                     "contended_minutes": s["contended_minutes"],
                     "contention_pct": s["contention_pct"]} for s in busiest],
        "stations": [{"name": s["name"], "lat": s["lat"], "lon": s["lon"],
                      "status": s["status"]} for s in everything],
        "online_detail": [{"name": s["name"], "lat": s["lat"], "lon": s["lon"],
                           "pass_minutes": s["pass_minutes"],
                           "contended_minutes": s["contended_minutes"],
                           "contention_pct": s["contention_pct"]} for s in online],
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=1))

    print()
    print("=" * 70)
    print("GLOBAL SCAN")
    print("=" * 70)
    print(f"LEO satellites          : {len(sats):,}")
    print(f"dishes online / total   : {len(online):,} / {len(everything):,}")
    print(f"satellite-dish minutes  : {pair_minutes:,}")
    print(f"contended dish-minutes  : {int(contention.sum()):,}")
    print(f"share of served time    : "
          f"{100*contention.sum()/max(totals.sum(),1):.1f}% contended")
    print(f"satellites never visible: {len(sats)-reachable:,}")
    print("\nbusiest dishes:")
    for s in busiest[:8]:
        print(f"  {s['name'][:26]:28} {s['lat']:+7.2f} {s['lon']:+8.2f}  "
              f"{s['contended_minutes']:>7,} min contended "
              f"({s['contention_pct']}%)")
    print(f"\nwrote {OUT}")
