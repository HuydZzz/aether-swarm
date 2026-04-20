"""
Stigmergic Task Market — Pillar 3.

Tasks are advertised as "pheromone deposits" on the pheromone channel. Each
agent computes a local affinity score (capability_match * intensity / distance)
and commits to the highest-affinity task it sees, with consensus-style
collision avoidance via a sync commitment.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .vertex_adapter import (
    VertexAdapter, Envelope, TOPIC_PHEROMONE, TOPIC_SYNC, TOPIC_GOSSIP,
)


PHEROMONE_DECAY_PER_S = 0.05
COMMIT_BACKOFF_S = 0.5    # window for collision detection


@dataclass
class Pheromone:
    task_id: str
    location: Tuple[float, float]
    capability: str
    intensity: float
    deposited_at: float
    deposited_by: str

    def current_intensity(self, now: float) -> float:
        elapsed = max(0.0, now - self.deposited_at)
        decayed = self.intensity * math.exp(-PHEROMONE_DECAY_PER_S * elapsed)
        return decayed


class StigmergicMarket:
    def __init__(self, agent_id: str, capabilities: List[str],
                 location: Tuple[float, float],
                 adapter: VertexAdapter, log):
        self.agent_id = agent_id
        self.capabilities = capabilities
        self.location = location
        self.adapter = adapter
        self.log = log
        self.field: Dict[str, Pheromone] = {}        # task_id -> pheromone
        self.committed_by: Dict[str, str] = {}       # task_id -> agent_id (who committed)
        self.completed: set = set()
        self._proposed_at: Dict[str, float] = {}     # local proposals
        self.my_task: Optional[str] = None
        adapter.subscribe(TOPIC_PHEROMONE, self._on_pheromone)
        adapter.subscribe(TOPIC_SYNC, self._on_sync)
        adapter.subscribe(TOPIC_GOSSIP, self._on_gossip)

    def deposit(self, task_id: str, location: Tuple[float, float],
                capability: str, intensity: float = 1.0) -> None:
        self.adapter.publish_pheromone({
            "kind": "PHEROMONE",
            "task_id": task_id,
            "location": list(location),
            "capability": capability,
            "intensity": intensity,
            "deposited_at": time.time(),
            "deposited_by": self.agent_id,
        })
        self.log("MARKET", f"deposited task {task_id} at {location} need={capability}")

    def update_location(self, location: Tuple[float, float]) -> None:
        self.location = location

    def tick(self) -> None:
        """Pick the most attractive uncommitted task we can do, propose it."""
        if self.my_task is not None:
            return  # already busy

        now = time.time()
        best: Optional[Tuple[float, str]] = None
        for task_id, ph in list(self.field.items()):
            if task_id in self.completed or task_id in self.committed_by:
                continue
            if ph.capability not in self.capabilities:
                continue
            score = self._affinity(ph, now)
            if score <= 0.05:
                continue
            if best is None or score > best[0]:
                best = (score, task_id)

        if best is None:
            return

        score, task_id = best
        # Tentative propose via sync — collisions resolved by simple winner rule.
        if task_id not in self._proposed_at:
            self._proposed_at[task_id] = now
            self.adapter.publish_sync({
                "kind": "TASK_PROPOSE",
                "task_id": task_id,
                "agent_id": self.agent_id,
                "affinity": score,
            })
            self.log("MARKET", f"proposing task {task_id} (affinity={score:.2f})")

        # If our proposal is older than COMMIT_BACKOFF_S and unchallenged → commit
        elif now - self._proposed_at[task_id] > COMMIT_BACKOFF_S:
            if task_id not in self.committed_by:
                self.adapter.publish_sync({
                    "kind": "TASK_COMMIT",
                    "task_id": task_id,
                    "agent_id": self.agent_id,
                })
                self.committed_by[task_id] = self.agent_id
                self.my_task = task_id
                self.log("MARKET", f"COMMIT task {task_id}")

    def complete_my_task(self) -> None:
        if self.my_task is None:
            return
        tid = self.my_task
        self.adapter.publish_gossip({
            "kind": "TASK_COMPLETE",
            "task_id": tid,
            "by": self.agent_id,
        })
        self.completed.add(tid)
        self.my_task = None
        self.log("MARKET", f"COMPLETED task {tid}")

    def release_my_task(self, reason: str) -> None:
        """Used when the agent dies / goes ghost — task returns to market."""
        if self.my_task is None:
            return
        tid = self.my_task
        self.committed_by.pop(tid, None)
        self.my_task = None
        self.log("MARKET", f"released task {tid} ({reason})")

    # ---- handlers ----------------------------------------------------------

    def _on_pheromone(self, env: Envelope) -> None:
        p = env.payload
        if p.get("kind") != "PHEROMONE":
            return
        ph = Pheromone(
            task_id=p["task_id"],
            location=tuple(p["location"]),
            capability=p["capability"],
            intensity=float(p.get("intensity", 1.0)),
            deposited_at=float(p.get("deposited_at", time.time())),
            deposited_by=p.get("deposited_by", env.sender_id),
        )
        # latest wins (ok for demo); production would use CRDT
        self.field[ph.task_id] = ph

    def _on_sync(self, env: Envelope) -> None:
        p = env.payload
        kind = p.get("kind")
        if kind == "TASK_COMMIT":
            tid = p["task_id"]
            who = p["agent_id"]
            prior = self.committed_by.get(tid)
            if prior and prior != who:
                # collision — earlier finalizer wins; but for demo, lowest agent_id wins
                winner = min(prior, who)
                self.committed_by[tid] = winner
                if winner != self.agent_id and self.my_task == tid:
                    self.my_task = None
                    self.log("MARKET",
                             f"yielded {tid} → collision winner {winner}")
            else:
                self.committed_by[tid] = who
                if who != self.agent_id and self.my_task == tid:
                    # Someone else committed first
                    self.my_task = None
        elif kind == "TASK_PROPOSE":
            tid = p["task_id"]
            other_aff = p.get("affinity", 0)
            mine = self._proposed_at.get(tid)
            if mine is not None:
                # If their affinity is higher OR equal but agent_id smaller, yield
                my_score = self._affinity(self.field.get(tid), time.time()) if tid in self.field else 0
                their_better = other_aff > my_score or (
                    other_aff == my_score and p["agent_id"] < self.agent_id
                )
                if their_better:
                    self._proposed_at.pop(tid, None)

    def _on_gossip(self, env: Envelope) -> None:
        p = env.payload
        if p.get("kind") == "TASK_COMPLETE":
            self.completed.add(p["task_id"])

    # ---- helpers -----------------------------------------------------------

    def _affinity(self, ph: Optional[Pheromone], now: float) -> float:
        if ph is None:
            return 0.0
        if ph.capability not in self.capabilities:
            return 0.0
        intensity = ph.current_intensity(now)
        dx = ph.location[0] - self.location[0]
        dy = ph.location[1] - self.location[1]
        dist = max(1.0, math.sqrt(dx * dx + dy * dy))
        return intensity / dist
