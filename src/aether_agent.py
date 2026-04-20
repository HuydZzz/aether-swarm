"""
AetherAgent — composes the three live pillars (Ghost Twin, Stigmergic Market,
Empathic Safety) into a single role-aware swarm node.

Run with:
    VERTEX_USER=<u> VERTEX_PASS=<p> \
        python -m src.aether_agent --agent-id drone-01 --role drone --x 10 --y 5

Roles ship out of the box:
    drone        — observes; can also seed tasks at observed survivor sites
    amr          — moves to grid points and fulfils "reach" tasks
    iot_sensor   — fixed location; emits anomaly observations
    coordinator  — does no physical work; observes mesh, optionally triggers chaos
"""

from __future__ import annotations

import argparse
import math
import os
import random
import sys
import time
from dataclasses import dataclass
from typing import List, Tuple

from .vertex_adapter import VertexAdapter, Envelope, TOPIC_CHAOS
from .ghost_twin import GhostTwin
from .stigmergic_market import StigmergicMarket
from .empathic_safety import EmpathicSafety


# ANSI color helpers
class C:
    R = "\033[0m"
    DIM = "\033[2m"
    B = "\033[1m"
    RED = "\033[31m"
    GRN = "\033[32m"
    YEL = "\033[33m"
    BLU = "\033[34m"
    MAG = "\033[35m"
    CYN = "\033[36m"


ROLE_COLORS = {
    "drone": C.CYN,
    "amr": C.YEL,
    "iot_sensor": C.MAG,
    "coordinator": C.BLU,
}

ROLE_CAPS = {
    "drone": ["aerial_observe", "scout"],
    "amr": ["ground_move", "carry_payload"],
    "iot_sensor": ["fixed_observe"],
    "coordinator": ["reason"],
}


@dataclass
class AgentConfig:
    agent_id: str
    role: str
    x: float
    y: float
    seed_tasks: int = 0   # for the coordinator: seed N tasks into the market on startup
    byzantine: bool = False


class AetherAgent:
    def __init__(self, cfg: AgentConfig):
        self.cfg = cfg
        self.adapter = VertexAdapter(cfg.agent_id)
        self.alive = True
        self.killed = False
        self.byzantine = cfg.byzantine

        capabilities = ROLE_CAPS.get(cfg.role, [])
        self.ghost = GhostTwin(cfg.agent_id, cfg.role, capabilities, self.adapter, self.log)
        self.market = StigmergicMarket(cfg.agent_id, capabilities, (cfg.x, cfg.y), self.adapter, self.log)
        self.safety = EmpathicSafety(cfg.agent_id, self.adapter, self.log)

        self.adapter.subscribe(TOPIC_CHAOS, self._on_chaos)

    # ---- core loop ---------------------------------------------------------

    def run(self) -> None:
        self.adapter.start()
        self.log("BOOT", f"online — role={self.cfg.role} pos=({self.cfg.x},{self.cfg.y})"
                 f"{' [BYZANTINE]' if self.byzantine else ''}")

        # Coordinator seeds tasks into the market
        if self.cfg.role == "coordinator" and self.cfg.seed_tasks > 0:
            self._seed_tasks(self.cfg.seed_tasks)

        try:
            tick_n = 0
            while self.alive:
                tick_n += 1
                if not self.killed:
                    self._tick(tick_n)
                time.sleep(0.5)
        except KeyboardInterrupt:
            self.log("BOOT", "KeyboardInterrupt — graceful shutdown")
        finally:
            self.adapter.stop()

    def _tick(self, n: int) -> None:
        # Always heartbeat (unless killed)
        self.ghost.tick()

        # Don't do work while frozen
        if self.safety.frozen:
            if n % 6 == 0:
                self.log("SAFETY", f"frozen ({self.safety.last_freeze_id}) — waiting for UNFREEZE")
            return

        if self.byzantine:
            self._byzantine_tick(n)
            return

        # Role-specific behavior
        if self.cfg.role in ("drone", "amr"):
            self.market.tick()
            if self.market.my_task and self.cfg.role == "amr":
                # Move toward the task; complete when within 1.0 unit
                ph = self.market.field.get(self.market.my_task)
                if ph and self._move_toward(ph.location):
                    self.market.complete_my_task()

            elif self.market.my_task and self.cfg.role == "drone":
                # Drone "observes" the task — finishes faster
                if random.random() < 0.3:
                    self.market.complete_my_task()

        elif self.cfg.role == "iot_sensor":
            # Periodically emit an anomaly observation that creates a task
            if n % 10 == 0 and random.random() < 0.4:
                tid = f"anomaly-{self.cfg.agent_id}-{n}"
                cap = random.choice(["ground_move", "scout"])
                self.market.deposit(
                    task_id=tid,
                    location=(self.cfg.x + random.uniform(-2, 2),
                              self.cfg.y + random.uniform(-2, 2)),
                    capability=cap,
                    intensity=1.0 + random.random(),
                )

        elif self.cfg.role == "coordinator":
            if n % 30 == 0:
                self.log("INFO",
                         f"mesh: {len(self.ghost.alive_peers)} alive, "
                         f"{len(self.ghost.ghost_peers)} ghost, "
                         f"committed={len(self.market.committed_by)} "
                         f"completed={len(self.market.completed)} "
                         f"| {self.safety.latency_summary()}")

    # ---- byzantine harness -------------------------------------------------

    def _byzantine_tick(self, n: int) -> None:
        # Still heartbeats so it stays in mesh, but spams false pheromones
        if n % 4 == 0:
            tid = f"FAKE-{self.cfg.agent_id}-{n}"
            self.adapter.publish_pheromone({
                "kind": "PHEROMONE",
                "task_id": tid,
                "location": [random.uniform(-50, 50), random.uniform(-50, 50)],
                "capability": "ground_move",
                "intensity": 5.0,   # dangerously attractive
                "deposited_at": time.time(),
                "deposited_by": self.cfg.agent_id,
            })

    # ---- chaos handling ----------------------------------------------------

    def _on_chaos(self, env: Envelope) -> None:
        p = env.payload
        kind = p.get("kind")
        target = p.get("target")
        if target and target != self.cfg.agent_id:
            return
        if kind == "KILL":
            self.killed = True
            self.log("CHAOS", "KILL received → going silent (heartbeats stop)")
            self.market.release_my_task("killed")
        elif kind == "REVIVE":
            self.killed = False
            self.log("CHAOS", "REVIVE received → resuming")
        elif kind == "FAULT":
            self.safety.emit_freeze(p.get("cause", "manual_fault"))
        elif kind == "RESUME":
            self.safety.emit_unfreeze()
        elif kind == "BYZANTINE_ON":
            self.byzantine = True
            self.log("CHAOS", "BYZANTINE_ON → broadcasting fabricated pheromones")
        elif kind == "BYZANTINE_OFF":
            self.byzantine = False
            self.log("CHAOS", "BYZANTINE_OFF")

    # ---- helpers -----------------------------------------------------------

    def _move_toward(self, target: Tuple[float, float]) -> bool:
        dx = target[0] - self.cfg.x
        dy = target[1] - self.cfg.y
        d = math.hypot(dx, dy)
        if d < 1.0:
            return True
        step = min(1.5, d)
        self.cfg.x += step * dx / d
        self.cfg.y += step * dy / d
        self.market.update_location((self.cfg.x, self.cfg.y))
        return False

    def _seed_tasks(self, n: int) -> None:
        for i in range(n):
            cap = random.choice(["ground_move", "scout"])
            self.market.deposit(
                task_id=f"survivor-{i:02d}",
                location=(random.uniform(-15, 15), random.uniform(-15, 15)),
                capability=cap,
                intensity=1.0 + random.random() * 0.5,
            )
            time.sleep(0.05)

    def log(self, tag: str, msg: str) -> None:
        color = ROLE_COLORS.get(self.cfg.role, "")
        ts = time.strftime("%H:%M:%S")
        print(f"{C.DIM}{ts}{C.R} {color}[{self.cfg.agent_id:14s}]{C.R} "
              f"{C.B}{tag:6s}{C.R} {msg}", flush=True)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--agent-id", required=True)
    p.add_argument("--role", choices=list(ROLE_CAPS.keys()), required=True)
    p.add_argument("--x", type=float, default=0.0)
    p.add_argument("--y", type=float, default=0.0)
    p.add_argument("--seed-tasks", type=int, default=0)
    p.add_argument("--byzantine", action="store_true")
    args = p.parse_args()

    if not os.getenv("VERTEX_USER"):
        print("ERROR: VERTEX_USER env var is required (FoxMQ credentials).",
              file=sys.stderr)
        sys.exit(2)

    cfg = AgentConfig(
        agent_id=args.agent_id,
        role=args.role,
        x=args.x, y=args.y,
        seed_tasks=args.seed_tasks,
        byzantine=args.byzantine,
    )
    AetherAgent(cfg).run()


if __name__ == "__main__":
    main()
