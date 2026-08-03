"""
FalkorDB household memory.

The graph IS the product here -- keep it on screen during the demo.

Schema
------
(:Person {name})
(:Room   {name})
(:Device {name, kind})
(:Person)-[:OCCUPIES {since}]->(:Room)
(:Device)-[:IN]->(:Room)
(:Person)-[:PREFERS {value}]->(:Device)
(:Person)-[:CONCEDED {topic, ts}]->(:Person)   <-- the memory that makes it fair

That CONCEDED edge is the whole demo. It is what makes run 2 smarter than run 1.
"""

import os
import time

try:
    from falkordb import FalkorDB
except ImportError:  # keep the skeleton runnable before the SDK is installed
    FalkorDB = None


class HouseholdMemory:
    def __init__(self, host=None, port=None, graph_name="household"):
        self.enabled = FalkorDB is not None
        if not self.enabled:
            print("[memory] falkordb not installed -- using in-process fallback")
            self._rooms = {}        # person -> room
            self._concessions = []  # (loser, winner, topic)
            return
        host = host or os.getenv("FALKOR_HOST", "localhost")
        port = int(port or os.getenv("FALKOR_PORT", 6379))
        self.db = FalkorDB(host=host, port=port)
        self.g = self.db.select_graph(graph_name)

    # ---------- demo hygiene ----------

    def reset(self):
        """
        Wipe the graph so the demo starts with a clean slate.

        The in-process fallback forgot everything between runs, but the real
        FalkorDB remembers. Without this, the second run already has history
        and the "no history yet" beat becomes false. Call once at startup.
        """
        if not self.enabled:
            self._rooms = {}
            self._concessions = []
            return
        self.q("MATCH (n) DETACH DELETE n")

    # ---------- writes ----------

    def q(self, cypher, params=None):
        if not self.enabled:
            return []
        return self.g.query(cypher, params or {}).result_set

    def enters_room(self, person, room):
        """
        Move `person` into `room`. A person is in exactly ONE room at a time.

        The DELETE matters: entering a room means leaving the last one. Without
        it, MERGE just bolts on another OCCUPIES edge and people slowly come to
        occupy the whole house, so who_is_in() returns everyone everywhere and
        every room looks like it has a conflict in it.
        """
        if not self.enabled:
            self._rooms[person] = room   # a dict already replaces; nothing to do
            return
        self.q("""
            MERGE (p:Person {name:$p})
            MERGE (r:Room {name:$r})
            WITH p, r
            OPTIONAL MATCH (p)-[old:OCCUPIES]->(:Room)
            DELETE old
            WITH p, r
            MERGE (p)-[o:OCCUPIES]->(r)
            SET o.since = $ts
        """, {"p": person, "r": room, "ts": time.time()})

    def set_preference(self, person, device, value):
        self.q("""
            MERGE (p:Person {name:$p})
            MERGE (d:Device {name:$d})
            MERGE (p)-[pref:PREFERS]->(d)
            SET pref.value = $v
        """, {"p": person, "d": device, "v": value})

    def record_concession(self, loser, winner, topic):
        """The memory that compounds. Call this every time a conflict resolves."""
        if not self.enabled:
            self._concessions.append((loser, winner, topic))
            return
        self.q("""
            MERGE (a:Person {name:$l})
            MERGE (b:Person {name:$w})
            CREATE (a)-[:CONCEDED {topic:$t, ts:$ts}]->(b)
        """, {"l": loser, "w": winner, "t": topic, "ts": time.time()})

    # ---------- reads (the multi-hop bit judges care about) ----------

    def who_is_in(self, room):
        if not self.enabled:
            return [p for p, r in self._rooms.items() if r == room]
        rows = self.q("""
            MATCH (p:Person)-[:OCCUPIES]->(r:Room {name:$r})
            RETURN p.name
        """, {"r": room})
        return [row[0] for row in rows]

    def concession_ledger(self, room, topic):
        """
        Who has given way to whom, among the people *currently in this room*.

        Returns {(giver, receiver): count}.

        THIS IS THE MULTI-HOP QUERY. Read the Cypher below as a walk:

            start at the Room
              -> hop 1: who occupies it
              -> hop 2: which of them conceded to whom, on this topic
              -> hop 3: is the receiver *also* still in this room

        Three relationship hops, and the walk starts and ends at the same Room
        node. That last constraint is the point: we only care about history
        between people who are in the argument *right now*. Jeremy conceding to
        Sam last week is irrelevant if Sam is out. A join table can express this,
        but only by re-joining occupancy twice and self-joining the history --
        the graph says it in one line, and it stays one line when the household
        grows to five people.

        Say the walk out loud in the pitch. "Room, occupants, history between
        them" is the sentence that earns the graph database.
        """
        if not self.enabled:
            here = {p for p, r in self._rooms.items() if r == room}
            led = {}
            for giver, receiver, t in self._concessions:
                if t == topic and giver in here and receiver in here:
                    led[(giver, receiver)] = led.get((giver, receiver), 0) + 1
            return led
        rows = self.q("""
            MATCH (r:Room {name:$room})<-[:OCCUPIES]-(giver:Person)
                  -[c:CONCEDED {topic:$t}]->
                  (receiver:Person)-[:OCCUPIES]->(r)
            RETURN giver.name, receiver.name, count(c)
        """, {"room": room, "t": topic})
        return {(g, rcv): n for g, rcv, n in rows}

    def concession_balance(self, room, a, b, topic):
        """
        Net fairness score for this room. Positive => `a` has given way more
        often than `b`, so `a` should win this round.

        Thin wrapper over concession_ledger -- the graph does the work.
        """
        led = self.concession_ledger(room, topic)
        return led.get((a, b), 0) - led.get((b, a), 0)

    def context_for(self, room):
        """Everything an agent needs to reason about this room, in one hop-set."""
        return {
            "room": room,
            "occupants": self.who_is_in(room),
        }
