"""
FalkorDB constellation memory.

The graph IS the product here -- keep it on screen during the demo.

Schema
------
(:Satellite     {name})
(:GroundStation {name})
(:Payload       {name, urgency})
(:Satellite)-[:IN_VIEW_OF {since}]->(:GroundStation)
(:Satellite)-[:LINKS_TO   {bandwidth_gbps}]->(:Satellite)   <-- the relay mesh
(:Satellite)-[:CARRIES]->(:Payload)
(:Satellite)-[:YIELDED    {station, ts}]->(:Satellite)      <-- the memory

Two queries earn the graph database, and they earn it for different reasons:

  yield_ledger()  three hops, starts and ends at the same station node.
                  This is the MEMORY -- it makes run 2 smarter than run 1.

  relay_path()    VARIABLE-DEPTH traversal, one to five hops, depth unknown
                  in advance. This is the one a SQL table genuinely cannot do.

Say "variable depth" out loud in the pitch.
"""

import os
import time

try:
    from falkordb import FalkorDB
except ImportError:  # keep the pipeline runnable before the SDK is installed
    FalkorDB = None


class ConstellationMemory:
    def __init__(self, host=None, port=None, graph_name="constellation"):
        self.enabled = FalkorDB is not None
        if not self.enabled:
            print("[memory] falkordb not installed -- using in-process fallback")
            self._reset_fallback()
            return
        host = host or os.getenv("FALKOR_HOST", "localhost")
        port = int(port or os.getenv("FALKOR_PORT", 6379))
        self.db = FalkorDB(host=host, port=port)
        self.g = self.db.select_graph(graph_name)

    def _reset_fallback(self):
        self._view = {}      # satellite -> station (or None)
        self._links = {}     # satellite -> {satellite: bandwidth}
        self._payloads = {}  # satellite -> (payload_name, urgency)
        self._yields = []    # (giver, receiver, station)

    # ---------- demo hygiene ----------

    def reset(self):
        """
        Wipe the graph so the demo starts clean.

        The in-process fallback forgets everything between runs, but the real
        FalkorDB does not. Without this, the second run already has history and
        the "no history yet" beat becomes a lie. Called once at startup.
        """
        if not self.enabled:
            self._reset_fallback()
            return
        self.q("MATCH (n) DETACH DELETE n")

    def q(self, cypher, params=None):
        if not self.enabled:
            return []
        return self.g.query(cypher, params or {}).result_set

    # ---------- writes ----------

    def sees_station(self, satellite, station):
        """
        Record that `satellite` can now talk to `station` -- or to nothing,
        if station is None (it just went over the horizon).

        The DELETE matters. Coming into view of one station means losing the
        last one. Without it, MERGE bolts on another IN_VIEW_OF edge and
        satellites slowly come to see every station at once, so who_sees()
        returns everything and every station looks contended.
        """
        if not self.enabled:
            self._view[satellite] = station
            return

        self.q("""
            MERGE (s:Satellite {name:$s})
            WITH s
            OPTIONAL MATCH (s)-[old:IN_VIEW_OF]->(:GroundStation)
            DELETE old
        """, {"s": satellite})

        if station is None:
            return  # out of view of everything -- this is the relay case

        self.q("""
            MERGE (s:Satellite {name:$s})
            MERGE (g:GroundStation {name:$g})
            MERGE (s)-[v:IN_VIEW_OF]->(g)
            SET v.since = $ts
        """, {"s": satellite, "g": station, "ts": time.time()})

    def add_link(self, a, b, bandwidth_gbps):
        """
        A laser link between two satellites. Created in BOTH directions,
        because a laser link is two-way and the relay search must be able to
        walk it either way.
        """
        if not self.enabled:
            self._links.setdefault(a, {})[b] = bandwidth_gbps
            self._links.setdefault(b, {})[a] = bandwidth_gbps
            return
        self.q("""
            MERGE (x:Satellite {name:$a})
            MERGE (y:Satellite {name:$b})
            MERGE (x)-[l1:LINKS_TO]->(y)
            MERGE (y)-[l2:LINKS_TO]->(x)
            SET l1.bandwidth_gbps = $bw, l2.bandwidth_gbps = $bw
        """, {"a": a, "b": b, "bw": bandwidth_gbps})

    def set_payload(self, satellite, payload, urgency):
        """What this satellite is carrying. `urgency` is what the safety agent reads."""
        if not self.enabled:
            self._payloads[satellite] = (payload, urgency)
            return
        self.q("""
            MERGE (s:Satellite {name:$s})
            MERGE (p:Payload {name:$p})
            SET p.urgency = $u
            MERGE (s)-[:CARRIES]->(p)
        """, {"s": satellite, "p": payload, "u": urgency})

    def record_yield(self, giver, receiver, station):
        """The memory that compounds. Called every time contention resolves."""
        if not self.enabled:
            self._yields.append((giver, receiver, station))
            return
        self.q("""
            MERGE (a:Satellite {name:$g})
            MERGE (b:Satellite {name:$r})
            CREATE (a)-[:YIELDED {station:$s, ts:$ts}]->(b)
        """, {"g": giver, "r": receiver, "s": station, "ts": time.time()})

    # ---------- reads ----------

    def who_sees(self, station):
        """Which satellites can talk to this station right now."""
        if not self.enabled:
            return [s for s, g in self._view.items() if g == station]
        rows = self.q("""
            MATCH (s:Satellite)-[:IN_VIEW_OF]->(:GroundStation {name:$g})
            RETURN s.name
        """, {"g": station})
        return [r[0] for r in rows]

    def payload_of(self, satellite):
        """What this satellite is carrying. The advocates quote it by name."""
        if not self.enabled:
            return self._payloads.get(satellite, ("unknown", "routine"))[0]
        rows = self.q("""
            MATCH (:Satellite {name:$s})-[:CARRIES]->(p:Payload)
            RETURN p.name
        """, {"s": satellite})
        return rows[0][0] if rows else "unknown"

    def urgency_of(self, satellite):
        """What the safety agent reads before it decides whether to veto."""
        if not self.enabled:
            return self._payloads.get(satellite, (None, "routine"))[1]
        rows = self.q("""
            MATCH (:Satellite {name:$s})-[:CARRIES]->(p:Payload)
            RETURN p.urgency
        """, {"s": satellite})
        return rows[0][0] if rows else "routine"

    def yield_ledger(self, station):
        """
        Who has given way to whom, among satellites *currently in view of this
        station*. Returns {(giver, receiver): count}.

        THIS IS THE MEMORY QUERY. Read the Cypher as a walk:

            start at the GroundStation
              -> hop 1: which satellites can see it right now
              -> hop 2: which of those yielded to whom, at this station
              -> hop 3: is that receiver ALSO still in view

        Three hops, starting and ending at the same node. That last constraint
        is the whole point: history only counts between satellites contending
        *right now*. SAT-1 yielding to SAT-9 last week is irrelevant if SAT-9
        is currently over the far side of the planet.
        """
        if not self.enabled:
            here = {s for s, g in self._view.items() if g == station}
            led = {}
            for giver, receiver, st in self._yields:
                if st == station and giver in here and receiver in here:
                    led[(giver, receiver)] = led.get((giver, receiver), 0) + 1
            return led
        rows = self.q("""
            MATCH (g:GroundStation {name:$g})<-[:IN_VIEW_OF]-(giver:Satellite)
                  -[y:YIELDED {station:$g}]->
                  (receiver:Satellite)-[:IN_VIEW_OF]->(g)
            RETURN giver.name, receiver.name, count(y)
        """, {"g": station})
        return {(a, b): n for a, b, n in rows}

    def yield_balance(self, station, a, b):
        """
        Net fairness score. Positive => `a` has yielded more often than `b`,
        so `a` should win this round. Thin wrapper -- the graph does the work.
        """
        led = self.yield_ledger(station)
        return led.get((a, b), 0) - led.get((b, a), 0)

    def relay_path(self, satellite, max_hops=5):
        """
        This satellite can see no ground station. Find the shortest chain of
        laser links that reaches one that can.

        THIS IS THE QUERY THAT EARNS A GRAPH DATABASE.

        `[:LINKS_TO*1..$max]` means "follow the link between one and five
        times" -- and you do not know how many hops until you look. SQL needs
        five self-joins or a recursive CTE to express this, and it breaks the
        moment the constellation grows. Here it is one line, and it stays one
        line at forty satellites.

        Returns (["SAT-3", "SAT-2", "Kiruna"], hop_count) or (None, 0).
        """
        if not self.enabled:
            return self._relay_path_fallback(satellite, max_hops)

        # max_hops is interpolated, not a parameter: FalkorDB needs the bound
        # on a variable-length pattern to be a literal at parse time. It is an
        # int we control, never user input, so there is nothing to inject.
        rows = self.q(f"""
            MATCH path = (s:Satellite {{name:$s}})-[:LINKS_TO*1..{int(max_hops)}]->
                         (relay:Satellite)-[:IN_VIEW_OF]->(g:GroundStation)
            RETURN [n IN nodes(path) | n.name] AS hops, length(path) AS len
            ORDER BY len
            LIMIT 1
        """, {"s": satellite})
        if not rows:
            return None, 0
        hops, length = rows[0]
        return hops, int(length)

    def _relay_path_fallback(self, satellite, max_hops):
        """Same search, plain Python breadth-first, for when FalkorDB is absent."""
        from collections import deque

        queue = deque([(satellite, [satellite])])
        seen = {satellite}
        while queue:
            node, path = queue.popleft()
            if len(path) > max_hops:
                continue
            station = self._view.get(node)
            if station and node != satellite:
                return path + [station], len(path)
            for nxt in self._links.get(node, {}):
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append((nxt, path + [nxt]))
        return None, 0
