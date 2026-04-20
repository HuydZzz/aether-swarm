"""
Ghost Twin — Pillar 1.

Each agent broadcasts a Twin record (heartbeat) on the sync channel. Peers
track each other's twins; when an agent misses N consecutive heartbeats,
peers promote its twin to "ghost mode" and a successor inherits its tasks.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List

from .vertex_adapter import VertexAdapter, Envelope, TOPIC_SYNC


HEARTBEAT_INTERVAL_S = 1.5
GHOST_PROMOTE_AFTER_MISSED = 3   # missed heartbeats before promotion
GHOST_REAP_AFTER_S = 30.0        # ghost is removed entirely after this


@dataclass
class Twin:
    agent_id: str
    role: str
    capabilities: List[str]
    last_seen: float
    last_seq: int = 0
    state: str = "alive"   # "alive" | "ghost" | "reassigned"
    held_tasks: List[str] = field(default_factory=list)


class GhostTwin:
    def __init__(self, agent_id: str, role: str, capabilities: List[str],
                 adapter: VertexAdapter, log):
        self.agent_id = agent_id
        self.role = role
        self.capabilities = capabilities
        self.adapter = adapter
        self.log = log
        self.peers: Dict[str, Twin] = {}
        self._last_beat = 0.0
        self._seq = 0
        adapter.subscribe(TOPIC_SYNC, self._on_sync)

    def tick(self) -> None:
        now = time.time()
        # Send heartbeat
        if now - self._last_beat >= HEARTBEAT_INTERVAL_S:
            self._seq += 1
            self.adapter.publish_sync({
                "kind": "HEARTBEAT",
                "agent_id": self.agent_id,
                "role": self.role,
                "capabilities": self.capabilities,
                "seq": self._seq,
            })
            self._last_beat = now

        # Promote / reap
        miss_window = HEARTBEAT_INTERVAL_S * GHOST_PROMOTE_AFTER_MISSED
        for pid, twin in list(self.peers.items()):
            age = now - twin.last_seen
            if twin.state == "alive" and age > miss_window:
                twin.state = "ghost"
                self.log("GHOST", f"{pid} missed {GHOST_PROMOTE_AFTER_MISSED}+ heartbeats → promoting twin to ghost mode")
                # Announce promotion
                self.adapter.publish_sync({
                    "kind": "GHOST_PROMOTE",
                    "agent_id": pid,
                    "promoted_by": self.agent_id,
                })
            elif twin.state == "ghost" and age > GHOST_REAP_AFTER_S:
                self.log("GHOST", f"reaping ghost {pid} (gone {age:.0f}s)")
                del self.peers[pid]

    def _on_sync(self, env: Envelope) -> None:
        p = env.payload
        kind = p.get("kind")
        sender = p.get("agent_id", env.sender_id)
        now = time.time()
        if kind == "HEARTBEAT":
            existed = sender in self.peers
            twin = self.peers.get(sender) or Twin(
                agent_id=sender,
                role=p.get("role", "?"),
                capabilities=p.get("capabilities", []),
                last_seen=now,
            )
            was_ghost = twin.state == "ghost"
            twin.last_seen = now
            twin.last_seq = max(twin.last_seq, p.get("seq", 0))
            twin.state = "alive"
            self.peers[sender] = twin
            if not existed:
                self.log("MESH", f"discovered peer {sender} ({twin.role})")
            elif was_ghost:
                self.log("GHOST", f"{sender} resurrected — back online, twin returned to alive")

    @property
    def alive_peers(self) -> List[str]:
        return [pid for pid, t in self.peers.items() if t.state == "alive"]

    @property
    def ghost_peers(self) -> List[str]:
        return [pid for pid, t in self.peers.items() if t.state == "ghost"]
