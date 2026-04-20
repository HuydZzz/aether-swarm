"""
AETHER live dashboard — a Vertex subscriber, no privileged access.

Renders a periodically-refreshing terminal view of:
  - peers (alive / ghost)
  - committed / completed tasks
  - last safety events + measured propagation latency
  - chaos events received
"""

from __future__ import annotations

import os
import sys
import time
from collections import deque
from threading import Lock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.vertex_adapter import (  # noqa: E402
    VertexAdapter, Envelope,
    TOPIC_SYNC, TOPIC_GOSSIP, TOPIC_FAST, TOPIC_PHEROMONE, TOPIC_CHAOS,
)


CLEAR = "\033[2J\033[H"
DIM = "\033[2m"
B = "\033[1m"
R = "\033[0m"
RED = "\033[31m"
GRN = "\033[32m"
YEL = "\033[33m"
CYN = "\033[36m"
MAG = "\033[35m"
BLU = "\033[34m"


class Dashboard:
    def __init__(self):
        self.adapter = VertexAdapter("dashboard")
        self.lock = Lock()
        self.peers = {}              # agent_id -> {role, last_seen, state}
        self.committed = {}          # task_id -> agent_id
        self.completed = set()
        self.pheromones = {}         # task_id -> dict
        self.events = deque(maxlen=15)
        self.freezes = []            # list of (origin, freeze_id, t0)
        self.freeze_acks = {}        # freeze_id -> [(acker, latency_ms)]

        self.adapter.subscribe(TOPIC_SYNC, self._on_sync)
        self.adapter.subscribe(TOPIC_GOSSIP, self._on_gossip)
        self.adapter.subscribe(TOPIC_FAST, self._on_fast)
        self.adapter.subscribe(TOPIC_PHEROMONE, self._on_pheromone)
        self.adapter.subscribe(TOPIC_CHAOS, self._on_chaos)

    def run(self):
        self.adapter.start()
        try:
            while True:
                self._render()
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
        finally:
            self.adapter.stop()

    # ---- handlers ----------------------------------------------------------

    def _on_sync(self, env: Envelope):
        p = env.payload
        kind = p.get("kind")
        with self.lock:
            if kind == "HEARTBEAT":
                pid = p["agent_id"]
                self.peers.setdefault(pid, {})
                self.peers[pid].update(role=p.get("role", "?"),
                                       last_seen=time.time(),
                                       state="alive")
            elif kind == "GHOST_PROMOTE":
                pid = p["agent_id"]
                if pid in self.peers:
                    self.peers[pid]["state"] = "ghost"
                self.events.append(("GHOST", f"{pid} promoted to ghost (by {p.get('promoted_by')})"))
            elif kind == "TASK_COMMIT":
                self.committed[p["task_id"]] = p["agent_id"]
                self.events.append(("MARKET", f"COMMIT {p['task_id']} -> {p['agent_id']}"))
            elif kind == "FREEZE_ACK":
                fid = p["freeze_id"]
                acker = env.sender_id
                # Find origin t0 from our records
                t0 = None
                for o, f, t in self.freezes:
                    if f == fid:
                        t0 = t
                        break
                if t0:
                    latency_ms = (time.time() - t0) * 1000
                    self.freeze_acks.setdefault(fid, []).append((acker, latency_ms))

    def _on_gossip(self, env: Envelope):
        p = env.payload
        with self.lock:
            if p.get("kind") == "TASK_COMPLETE":
                self.completed.add(p["task_id"])
                self.events.append(("MARKET", f"DONE {p['task_id']} by {p.get('by')}"))

    def _on_fast(self, env: Envelope):
        p = env.payload
        with self.lock:
            if p.get("kind") == "FREEZE":
                self.freezes.append((p.get("origin"), p["freeze_id"], p.get("origin_t0", time.time())))
                self.events.append(("SAFETY", f"FREEZE {p['freeze_id']} from {p.get('origin')} cause={p.get('cause')}"))
            elif p.get("kind") == "UNFREEZE":
                self.events.append(("SAFETY", f"UNFREEZE from {p.get('origin')}"))

    def _on_pheromone(self, env: Envelope):
        p = env.payload
        if p.get("kind") != "PHEROMONE":
            return
        with self.lock:
            self.pheromones[p["task_id"]] = p

    def _on_chaos(self, env: Envelope):
        p = env.payload
        with self.lock:
            self.events.append(("CHAOS", f"{p.get('kind')} -> {p.get('target')}"))

    # ---- render ------------------------------------------------------------

    def _render(self):
        with self.lock:
            now = time.time()
            alive = [pid for pid, m in self.peers.items() if m.get("state") == "alive"]
            ghost = [pid for pid, m in self.peers.items() if m.get("state") == "ghost"]
            # Reap totally-silent peers from display after 30s
            for pid in list(self.peers.keys()):
                if now - self.peers[pid].get("last_seen", 0) > 30:
                    del self.peers[pid]

            out = [CLEAR]
            out.append(f"{B}AETHER SWARM — Live Mesh{R} {DIM}(Vertex / FoxMQ subscriber){R}")
            out.append("=" * 78)
            out.append(f"{B}Peers:{R} {GRN}{len(alive)} alive{R}  {YEL}{len(ghost)} ghost{R}  {MAG}{len(self.pheromones)} pheromones{R}  "
                       f"{CYN}{len(self.committed)} committed{R}  {GRN}{len(self.completed)} completed{R}")
            out.append("")
            out.append(f"{B}Roster:{R}")
            for pid, m in sorted(self.peers.items()):
                color = GRN if m.get("state") == "alive" else YEL
                age = now - m.get("last_seen", now)
                out.append(f"  {color}{m.get('state', '?'):>5s}{R} {pid:14s} role={m.get('role','?'):12s} last_seen={age:.1f}s")
            out.append("")
            out.append(f"{B}Tasks:{R}")
            shown = 0
            for tid, ph in sorted(self.pheromones.items()):
                if tid in self.completed:
                    state = f"{GRN}DONE{R}"
                elif tid in self.committed:
                    state = f"{CYN}{self.committed[tid]:14s}{R}"
                else:
                    state = f"{DIM}open{R}"
                out.append(f"  {state}  {tid:32s} need={ph.get('capability','?'):14s} loc=({ph.get('location',[0,0])[0]:5.1f},{ph.get('location',[0,0])[1]:5.1f})")
                shown += 1
                if shown >= 12:
                    out.append(f"  {DIM}... +{len(self.pheromones) - shown} more{R}")
                    break
            out.append("")
            out.append(f"{B}Safety:{R}")
            if not self.freezes:
                out.append(f"  {DIM}no freeze events yet{R}")
            else:
                for origin, fid, t0 in self.freezes[-3:]:
                    acks = self.freeze_acks.get(fid, [])
                    if acks:
                        latencies = [l for _, l in acks]
                        p99 = sorted(latencies)[min(len(latencies)-1, int(len(latencies)*0.99))]
                        out.append(f"  FREEZE {fid} origin={origin} acks={len(acks)} p99={p99:.1f}ms")
                    else:
                        out.append(f"  FREEZE {fid} origin={origin} (no acks yet)")
            out.append("")
            out.append(f"{B}Recent events:{R}")
            for tag, msg in list(self.events)[-10:]:
                out.append(f"  {DIM}{tag:6s}{R} {msg}")
            out.append("")
            out.append(f"{DIM}refresh 2Hz · Ctrl-C to exit{R}")
            print("\n".join(out), flush=True)


if __name__ == "__main__":
    Dashboard().run()
