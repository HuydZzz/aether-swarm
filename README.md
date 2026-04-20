<div align="center">

<img src="logo.png" alt="Aether Swarm" width="120" />

# AETHER SWARM

### The Ghost Protocol — a Vertex-native coordination substrate for heterogeneous machine swarms

[![Vertex 2.0](https://img.shields.io/badge/Tashi_Vertex-FoxMQ-38bdf8?style=flat-square)](https://docs.tashi.network/)
[![No Cloud](https://img.shields.io/badge/Cloud_Calls-ZERO-ef4444?style=flat-square)](/)
[![Track 1](https://img.shields.io/badge/Vertex_Swarm_2026-Track_1-6366f1?style=flat-square)](https://tashi.network/)

**Vertex Swarm Challenge 2026 · Track 1 · "Ghost in the Machine"**

</div>

---

## What this is

AETHER SWARM is a peer-to-peer coordination substrate built on **Tashi Vertex 2.0** (via FoxMQ) where heterogeneous agents — drones, AMRs, IoT sensors, coordinators — discover each other, allocate tasks via emergent stigmergy, propagate safety signals mesh-wide in milliseconds, and survive node failures via persistent **Ghost Twins**. No broker. No orchestrator. No cloud.

This is the same Vertex/FoxMQ integration that backs my Warm-up submission ([`vertex-handshake`](https://github.com/HuydZzz/vertex-handshake)) — extended into a full Track 1 swarm.

## Three pillars, all live

| Pillar | What it does | Vertex channel |
|---|---|---|
| **Ghost Twin** | When an agent stops heartbeating, peers promote its twin to "ghost" mode and its tasks return to the market. When the agent revives, its twin reactivates. | `aether/sync` |
| **Stigmergic Task Market** | Tasks broadcast as decaying pheromones. Agents self-allocate based on capability + distance + intensity. No auctioneer. | `aether/pheromone` + `aether/sync` |
| **Empathic Safety Contagion** | Any agent detecting a fault triggers a mesh-wide FREEZE on a fast-path channel. End-to-end propagation latency is measured and logged live. | `aether/fast` + `aether/sync` |

All three plug into a **single Vertex Adapter** ([`src/vertex_adapter.py`](src/vertex_adapter.py)). Grep the codebase for `paho` or `mqtt` — they appear only in that file.

## Why Track 1 — competitive edge

I reviewed the three strongest public Track 1 submissions. Their gaps:

| Gap | drone-swarm | xops | vertex_swarn | **AETHER** |
|---|---|---|---|---|
| Heterogeneous agent classes on one mesh | 1 | 1 | 2 | **4** (drone, AMR, IoT, coordinator) |
| Vertex used for more than position broadcast | no | partial | no (MQTT wrapper) | **yes — Ghost Twin promotion + task commit + safety FREEZE all consensus-gated** |
| Live chaos triggerable by judges | no | no | partial | **yes — `python -m demo.chaos kill <id>` mid-demo** |
| Measured safety propagation latency | no | no | no | **yes — p50/p99 logged live** |
| Recoverable Byzantine harness | no | no | no | **yes — `byzantine-on / byzantine-off` per-agent** |

Full teardown: [`docs/COMPETITIVE_EDGE.md`](docs/COMPETITIVE_EDGE.md).

## Live visual demo (no install)

Open **[`public/index.html`](public/index.html)** in a browser — that's it. You'll see the mesh animate, agents discover each other, tasks get self-allocated via stigmergic affinity, and you get chaos buttons (`Kill`, `Revive`, `Fault`, `Byzantine`, `Auto-run`) to break the swarm live while recording.

The demo is deployed to Vercel the same way as the warm-up (see `vercel.json`) — deploy with one click, or just open the file directly.

Keyboard shortcuts while the demo has focus:

| Key | Action |
|-----|--------|
| `K` | Kill target agent |
| `R` | Revive target agent |
| `F` | Trigger mesh-wide FREEZE from target |
| `U` | UNFREEZE the mesh |
| `B` | Turn target Byzantine (broadcast fake pheromones) |
| `N` | Turn Byzantine off |
| `A` | Auto-run the full chaos script end-to-end |
| `Esc` | Reset simulation |

The visual demo is a faithful simulation of the Python implementation's behaviour — same agent roles, same three pillars, same chaos actions. The **real Vertex integration** lives in the Python source; the HTML demo is designed for judge-friendly demonstration and video recording.

## For developers — run the real Vertex-backed mesh

If you want to see the actual Vertex integration running (not the visual sim), spin up the Python mesh:

```bash
pip install -r requirements.txt

export VERTEX_USER=demo
export VERTEX_PASS=demo            # or your hackathon-issued credentials
export VERTEX_HOST=127.0.0.1
export VERTEX_PORT=1883

# Terminal 1: spawn 8 heterogeneous agents
./demo/run_mesh.sh

# Terminal 2: live dashboard (Vertex subscriber)
python3 -m demo.dashboard

# Terminal 3: chaos trigger CLI
python3 -m demo.chaos kill drone-01
python3 -m demo.chaos fault iot-01 thermal_anomaly
python3 -m demo.chaos byzantine-on amr-02
```

All Python code is Vertex-native — every pillar publishes/subscribes through [`src/vertex_adapter.py`](src/vertex_adapter.py), the single seam to FoxMQ. Grep for `paho` or `mqtt`: one file only.

## Architecture

```
+----------------+   +----------------+   +----------------+
|  AetherAgent   |   |  AetherAgent   |   |  AetherAgent   |
|  (drone-01)    |   |  (amr-02)      |   |  (iot-01)      |
| +------------+ |   | +------------+ |   | +------------+ |
| | GhostTwin  | |   | | GhostTwin  | |   | | GhostTwin  | |
| | Market     | |   | | Market     | |   | | Market     | |
| | Safety     | |   | | Safety     | |   | | Safety     | |
| +-----+------+ |   | +-----+------+ |   | +-----+------+ |
|       |        |   |       |        |   |       |        |
| +-----v------+ |   | +-----v------+ |   | +-----v------+ |
| |VertexAdptr | |   | |VertexAdptr | |   | |VertexAdptr | |
| +-----+------+ |   | +-----+------+ |   | +-----+------+ |
+-------|--------+   +-------|--------+   +-------|--------+
        |                    |                    |
        +--------------------+--------------------+
                             |
              +--------------v---------------+
              |   Tashi Vertex 2.0 (FoxMQ)   |
              |   topics: sync gossip fast   |
              |           pheromone chaos    |
              +------------------------------+
```

Detailed architecture, sequence diagrams, and the full Vertex-channel mapping are in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and [`docs/VERTEX_INTEGRATION.md`](docs/VERTEX_INTEGRATION.md).

## Repo layout

```
aether-swarm/
├── src/
│   ├── vertex_adapter.py     The single seam to Tashi Vertex (FoxMQ)
│   ├── aether_agent.py       AetherAgent — composes all three pillars
│   ├── ghost_twin.py         Pillar 1: heartbeats + ghost promotion
│   ├── stigmergic_market.py  Pillar 3: pheromones + task self-allocation
│   └── empathic_safety.py    Pillar 4: mesh-wide FREEZE with measured latency
├── demo/
│   ├── run_mesh.sh           Spawn 8 heterogeneous agents
│   ├── dashboard.py          Live mesh viewer (Vertex subscriber)
│   └── chaos.py              Judge-facing chaos trigger CLI
├── docs/
│   ├── ARCHITECTURE.md       Full design
│   ├── VERTEX_INTEGRATION.md Per-pillar Vertex primitive mapping
│   ├── COMPETITIVE_EDGE.md   Teardown of competitor repos
│   ├── DEMO_SCENARIOS.md     Three demo scenarios (Blackout Rescue + 2)
│   └── ROADMAP.md            Future scale plan (50+ agents, BFT, CRDT memory)
├── public/
│   └── index.html            Interactive visual demo (open in browser)
├── PITCH.md                  Hackathon pitch
├── vercel.json               One-click Vercel deployment
├── requirements.txt
└── LICENSE
```

## What's in scope vs. roadmap

**In this submission (working, runnable):**

- Vertex Adapter over FoxMQ with 5 logical channels (sync / gossip / fast / pheromone / chaos).
- Ghost Twin pillar: heartbeats, ghost promotion on missed heartbeats, revival on rejoin, task release back to market.
- Stigmergic Task Market pillar: pheromone deposit / decay / affinity / propose / commit with collision resolution.
- Empathic Safety pillar: mesh-wide FREEZE / UNFREEZE with end-to-end latency measurement.
- Heterogeneous agents (drone, AMR, IoT sensor, coordinator) on one mesh.
- Live chaos CLI: kill, revive, fault, resume, byzantine-on, byzantine-off.
- Live terminal dashboard.

**Roadmap (after submission, see [`docs/ROADMAP.md`](docs/ROADMAP.md)):**

- Adversarial Guard pillar — automatic Byzantine quarantine via consensus voting (today the Byzantine harness exists but quarantine is a human-triggered `byzantine-off`).
- Collective Memory Genome — CRDT-based distributed knowledge.
- Scale-out to 50+ agents with measured benchmarks.
- WebGL visualization.

This scope was chosen for the 24-hour finalisation window. Every claim above has running code behind it.

## Built by

HuyNguyen — for the Vertex Swarm Challenge 2026.

Warm-up submission: <https://github.com/HuydZzz/vertex-handshake>
