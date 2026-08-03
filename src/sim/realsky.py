"""
Real satellites. Real ground stations. Real pass geometry.

Everything here comes from public data, fetched live:

  CelesTrak   https://celestrak.org/NORAD/elements/gp.php
              Two-Line Elements (TLEs) -- the orbital elements for essentially
              every tracked object. No account, no key. This is the source
              everyone uses.

  SatNOGS     https://network.satnogs.org/api/stations/
              An open, volunteer-run network of 4,400+ real ground stations,
              with coordinates and live online/offline status. People really
              do compete for time on these dishes, which is exactly the
              problem this project is about.

  sgp4        The standard orbit propagator. Given a TLE and a time, it says
              where the satellite is. Well-established library, not a guess.

So the orbits and the dish locations are not invented. What we simulate is the
SCHEDULING POLICY -- who gets the dish when two satellites want it at once.

Run it:  python src/sim/realsky.py     (writes docs/real_passes.json)
"""

import json
import math
import pathlib
import urllib.request
from datetime import datetime, timedelta, timezone

from sgp4.api import Satrec, jday

CACHE = pathlib.Path("docs/real_passes.json")

# Civilian Earth-observation satellites, publicly tracked. Weather and
# resource birds genuinely downlink imagery through ground stations on every
# pass, which makes the scenario honest rather than decorative.
#
# Taken from the group listings rather than a hardcoded name list: names drift
# (NOAA 20 is listed as JPSS-1 some days) and a stale list silently returns
# three satellites, which produces no contention and a pointless simulation.
GROUPS = ["weather", "resource"]
FLEET_SIZE = 12
MAX_PERIOD_MIN = 130.0   # LEO only -- a geostationary bird never sets, so it
                         # is always "in view" and creates fake contention

ELEVATION_MASK_DEG = 10.0   # below this a dish cannot usefully see a satellite


# ------------------------------------------------------------------ fetching
def fetch_tles():
    """
    Pull live TLEs from CelesTrak and keep the low-orbit ones.

    Field 8 of TLE line 2 is mean motion -- orbits per day. Dividing 1440 by it
    gives the period in minutes, which is how we filter out geostationary
    satellites that would sit permanently in view.
    """
    out = {}
    for group in GROUPS:
        url = f"https://celestrak.org/NORAD/elements/gp.php?GROUP={group}&FORMAT=tle"
        with urllib.request.urlopen(url, timeout=30) as r:
            lines = r.read().decode().splitlines()

        for i in range(0, len(lines) - 2, 3):
            name = lines[i].strip()
            l1, l2 = lines[i + 1].strip(), lines[i + 2].strip()
            if not l2.startswith("2 "):
                continue
            try:
                revs_per_day = float(l2[52:63])
            except ValueError:
                continue
            if revs_per_day <= 0 or 1440.0 / revs_per_day > MAX_PERIOD_MIN:
                continue
            out.setdefault(name, (l1, l2))
            if len(out) >= FLEET_SIZE:
                return out
    return out


def fetch_stations(limit=6):
    """
    Pull real ground stations from SatNOGS and pick a globally spread handful.

    Spread matters: stations clustered in Europe would all see the same passes,
    so there would be no interesting contention. We bucket by longitude and
    take one online station from each bucket.
    """
    url = "https://network.satnogs.org/api/stations/?format=json"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        stations = json.load(r)

    online = [s for s in stations
              if s.get("status") == "Online"
              and isinstance(s.get("lat"), (int, float))
              and isinstance(s.get("lng"), (int, float))]

    picked, seen = [], set()
    for s in sorted(online, key=lambda s: s["lng"]):
        bucket = int((s["lng"] + 180) // (360 / limit))
        if bucket in seen:
            continue
        seen.add(bucket)
        picked.append({"name": s["name"].strip()[:24] or f"station-{s['id']}",
                       "lat": float(s["lat"]), "lon": float(s["lng"])})
        if len(picked) == limit:
            break
    return picked


# ------------------------------------------------------------ pass geometry
def _gmst(jd, fr):
    """
    Greenwich Mean Sidereal Time -- how far the Earth has turned.

    Needed because sgp4 gives a position in a frame fixed to the STARS, but
    ground stations rotate with the Earth. Standard IAU polynomial.
    """
    t = ((jd - 2451545.0) + fr) / 36525.0
    s = (280.46061837 + 360.98564736629 * ((jd - 2451545.0) + fr)
         + 0.000387933 * t * t - t * t * t / 38710000.0)
    return math.radians(s % 360.0)


def _elevation_deg(sat_teme_km, jd, fr, lat_deg, lon_deg):
    """How high above the horizon is this satellite, seen from this station?"""
    theta = _gmst(jd, fr)
    x, y, z = sat_teme_km
    # rotate the satellite into an Earth-fixed frame
    xe = x * math.cos(theta) + y * math.sin(theta)
    ye = -x * math.sin(theta) + y * math.cos(theta)
    ze = z

    re = 6378.137
    lat, lon = math.radians(lat_deg), math.radians(lon_deg)
    sx = re * math.cos(lat) * math.cos(lon)
    sy = re * math.cos(lat) * math.sin(lon)
    sz = re * math.sin(lat)

    dx, dy, dz = xe - sx, ye - sy, ze - sz
    # project onto the station's local "up"
    up = (math.cos(lat) * math.cos(lon),
          math.cos(lat) * math.sin(lon),
          math.sin(lat))
    rng = math.sqrt(dx * dx + dy * dy + dz * dz)
    if rng == 0:
        return -90.0
    sin_el = (dx * up[0] + dy * up[1] + dz * up[2]) / rng
    return math.degrees(math.asin(max(-1.0, min(1.0, sin_el))))


def compute_passes(tles, stations, start=None, minutes=24 * 60, step=1):
    """
    Walk 24 hours a minute at a time and record, for each satellite, which
    stations could actually see it.

    Returns {minute: {satellite: [station names in view]}}.
    """
    start = start or datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0)

    sats = {name: Satrec.twoline2rv(l1, l2) for name, (l1, l2) in tles.items()}
    timeline = {}

    for m in range(0, minutes, step):
        t = start + timedelta(minutes=m)
        jd, fr = jday(t.year, t.month, t.day, t.hour, t.minute, t.second)
        slot = {}
        for name, sat in sats.items():
            err, pos, _vel = sat.sgp4(jd, fr)
            if err != 0:
                continue
            visible = [st["name"] for st in stations
                       if _elevation_deg(pos, jd, fr, st["lat"], st["lon"])
                       > ELEVATION_MASK_DEG]
            if visible:
                slot[name] = visible
        if slot:
            timeline[m] = slot

    return timeline, start


def build(force=False):
    """Fetch everything and cache it, so the demo never depends on the wifi."""
    if CACHE.exists() and not force:
        return json.loads(CACHE.read_text())

    print("[realsky] fetching TLEs from CelesTrak...")
    tles = fetch_tles()
    print(f"[realsky]   got {len(tles)}: {', '.join(tles)}")

    print("[realsky] fetching ground stations from SatNOGS...")
    stations = fetch_stations()
    for s in stations:
        print(f"[realsky]   {s['name']:26} {s['lat']:+7.2f} {s['lon']:+8.2f}")

    print("[realsky] propagating 24h of real orbits (sgp4)...")
    timeline, start = compute_passes(tles, stations)

    contended = sum(1 for slot in timeline.values()
                    for st in {s for v in slot.values() for s in v}
                    if sum(1 for sat in slot if st in slot[sat]) > 1)

    data = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "window_start_utc": start.isoformat(),
        "satellites": list(tles),
        "stations": stations,
        "timeline": {str(k): v for k, v in timeline.items()},
        "minutes_with_any_pass": len(timeline),
        "contended_station_minutes": contended,
        "sources": {
            "orbits": "CelesTrak GP/TLE (public, no auth)",
            "ground_stations": "SatNOGS Network API (open volunteer network)",
            "propagator": "sgp4",
        },
    }
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(data, indent=1))
    return data


if __name__ == "__main__":
    d = build(force=True)
    print()
    print("=" * 66)
    print("REAL SKY -- 24 hours of genuine pass geometry")
    print("=" * 66)
    print(f"satellites            : {', '.join(d['satellites'])}")
    print(f"ground stations       : {len(d['stations'])} real SatNOGS sites")
    print(f"minutes with a pass   : {d['minutes_with_any_pass']} of 1440")
    print(f"contended dish-minutes: {d['contended_station_minutes']}")
    print(f"cached to             : {CACHE}")
