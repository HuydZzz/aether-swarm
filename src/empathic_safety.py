"""
Empathic Safety Contagion — Pillar 4.

A single node detecting a fault triggers a mesh-wide FREEZE. Signals ride the
fast channel, agents enter safe state immediately on receipt, and ack via
sync so the origin can measure end-to-end propagation latency.

Target: p99 mesh-wide freeze latency under 100 ms for a 10-node mesh.
"""

from __future__ import annotations

import time
import uuid
from typing import Dict

from .vertex_adapter import VertexAdapter, Envelope, TOPIC_FAST, TOPIC_SYNC


class EmpathicSafety:
    def __init__(self, agent_id: str, adapter: VertexAdapter, log):
        self.agent_id = agent_id
        self.adapter = adapter
        self.log = log
        self.frozen = False
        self.last_freeze_id: str = ""
        # latency measurement (origin side)
        self._pending_acks: Dict[str, float] = {}  # freeze_id -> origin_t0
        self._observed_latencies_ms: list = []
        adapter.subscribe(TOPIC_FAST, self._on_fast)
        adapter.subscribe(TOPIC_SYNC, self._on_sync)

    def emit_freeze(self, cause: str) -> str:
        """Local fault detected: trigger mesh-wide freeze. Returns freeze_id."""
        freeze_id = uuid.uuid4().hex[:8]
        t0 = time.time()
        self._pending_acks[freeze_id] = t0
        self.adapter.publish_fast({
            "kind": "FREEZE",
            "freeze_id": freeze_id,
            "origin": self.agent_id,
            "cause": cause,
            "origin_t0": t0,
        })
        # We freeze ourselves too
        self._enter_safe(freeze_id, cause, origin=True)
        return freeze_id

    def emit_unfreeze(self) -> None:
        self.adapter.publish_fast({
            "kind": "UNFREEZE",
            "origin": self.agent_id,
        })
        self.frozen = False
        self.log("SAFETY", "UNFREEZE issued — swarm resuming")

    def _on_fast(self, env: Envelope) -> None:
        p = env.payload
        kind = p.get("kind")
        if kind == "FREEZE":
            self._enter_safe(p["freeze_id"], p.get("cause", "?"),
                             origin=False, origin_t0=p.get("origin_t0"),
                             origin_id=p.get("origin"))
        elif kind == "UNFREEZE":
            if self.frozen:
                self.frozen = False
                self.log("SAFETY", f"UNFREEZE received from {p.get('origin')} — resuming")

    def _on_sync(self, env: Envelope) -> None:
        p = env.payload
        if p.get("kind") != "FREEZE_ACK":
            return
        if p.get("origin") != self.agent_id:
            return
        fid = p.get("freeze_id")
        if fid in self._pending_acks:
            t0 = self._pending_acks[fid]
            latency_ms = (time.time() - t0) * 1000
            self._observed_latencies_ms.append(latency_ms)
            self.log("SAFETY",
                     f"FREEZE {fid} ack from {env.sender_id} → "
                     f"propagation {latency_ms:.1f}ms")

    def _enter_safe(self, freeze_id: str, cause: str, origin: bool,
                    origin_t0: float = None, origin_id: str = None) -> None:
        if self.frozen and freeze_id == self.last_freeze_id:
            return
        self.frozen = True
        self.last_freeze_id = freeze_id
        if origin:
            self.log("SAFETY",
                     f"!! LOCAL FAULT [{cause}] → emitting FREEZE {freeze_id} mesh-wide")
        else:
            local_latency_ms = (time.time() - origin_t0) * 1000 if origin_t0 else -1
            self.log("SAFETY",
                     f"!! FREEZE {freeze_id} received (cause={cause}, "
                     f"origin={origin_id}, t={local_latency_ms:.1f}ms) → entering safe state")
            # Ack back to origin so they can measure end-to-end
            self.adapter.publish_sync({
                "kind": "FREEZE_ACK",
                "freeze_id": freeze_id,
                "origin": origin_id,
            })

    def latency_summary(self) -> str:
        if not self._observed_latencies_ms:
            return "no FREEZE emitted yet"
        s = sorted(self._observed_latencies_ms)
        n = len(s)
        p50 = s[n // 2]
        p99 = s[min(n - 1, int(n * 0.99))]
        return f"FREEZE acks={n} p50={p50:.1f}ms p99={p99:.1f}ms"
