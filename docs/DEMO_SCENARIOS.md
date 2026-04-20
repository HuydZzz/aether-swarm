# Demo Scenarios

Three scenarios, ordered by judge-facing impact. The demo day script runs scenario 1 live; 2 and 3 are backup / extended reel.

---

## Scenario 1 — "Blackout Rescue" (primary)

**The pitch:** 50 heterogeneous agents drop into a simulated disaster zone. Locate and reach all survivors, end-to-end, while the judges actively break the system.

### Swarm composition

| Count | Class | Capabilities |
|---|---|---|
| 20 | Drone sim | Aerial observation, fast mobility, low payload |
| 15 | AMR sim | Ground mobility, payload, local obstacle avoidance |
| 10 | IoT sensor sim | Fixed location, thermal / acoustic / vibration readings |
| 5 | LLM tactical agent | Reasoning over strands, plan proposals, no physical presence |

### Mission

Locate `N` simulated survivors scattered across a 1 km² grid. Success = every survivor has been both **located** (a signed observation strand committed to the Memory Genome) and **reached** (an AMR has arrived within 3 m).

### Live chaos actions (judges trigger these)

| Time | Action | Expected result |
|---|---|---|
| T+30s | Pull the simulated cloud link | Mission continues. (It never depended on the cloud.) |
| T+1m | Partition the mesh into 3 shards | Each shard progresses independently. On rejoin at T+3m, strands merge, no lost work. |
| T+2m | Kill 40% of agents at random | Ghost Twins hold state; pheromone market reassigns tasks; mission throughput dips ~20%, not 40%. |
| T+3m | Inject 3 Byzantine agents broadcasting false survivor coordinates | Trust scores drop within 3s; quarantine within 5s; false strands retracted mesh-wide. |

### Metrics graphed live

- Consensus latency (p50/p99) through each chaos event.
- Mesh-wide freeze latency on a simulated safety trigger.
- Survivors located / reached over time.
- Trust score distribution across peers, highlighting Byzantine agents turning red → quarantined.

### Demo duration

**~8 minutes live + ~2 minute walkthrough of the dashboard.** Fits any reasonable hackathon judging slot.

---

## Scenario 2 — "Warehouse Handshake" (backup / physical demo)

**The pitch:** Multi-vendor AMRs from three simulated vendors auto-discover each other on a warehouse floor and cooperatively fulfill orders, with no central WMS.

### Composition

- 12 AMR sims across 3 "vendors" (different capability profiles, different firmware signatures).
- 4 IoT shelf-weight sensors.
- 2 LLM planner agents.

### What it proves

- **True heterogeneity:** no common SDK, only Vertex.
- **Capability-based task allocation** via the stigmergic market.
- **Graceful handoff** when one vendor's fleet is paused (firmware update).

### Why it's a backup

Great for the industrial / commercial narrative, weaker on visual drama than the rescue scenario. We keep it in reserve for extended demo time or specific judge interest.

---

## Scenario 3 — "Agent Economy Micro-Test" (extensibility proof)

**The pitch:** AETHER's stigmergic market primitive extends directly to Track 3 ("Agent Economy"). We run a mini-demo of 10 LLM agents (tactical planners) bidding on plan-generation tasks via the same pheromone market used by the drones.

### Composition

- 10 LLM agents (small local models, e.g. Llama 3 8B or Phi-3).
- Tasks: "plan a search pattern for grid Xij", "propose formation for hazard Y".

### What it proves

- The AETHER substrate is **domain-neutral** — the same code that coordinates physical drones coordinates pure-digital agents.
- Pheromone decay works as a natural bid-aging mechanism.
- Adversarial Guard extends to detecting hallucinating or jailbroken LLM agents (their strands disagree with ground-truth observations).

### Why it's a "proof" scenario

Short, narrated. Demonstrates that AETHER is not a drone framework — it is a coordination substrate. Strategic: opens the door to Track 3 cross-applicability in judges' minds.

---

## Setup notes

- All scenarios run in simulation on a single workstation (target: 16-core Mac or Linux box).
- Drone sim: lightweight 3D physics (no Webots dependency — we don't want the xops install burden).
- AMR sim: 2D grid physics, sufficient for task-allocation demonstration.
- IoT sensors: simple periodic readings with configurable noise.
- LLM agents: local 8B-class model via llama.cpp / Ollama for reproducibility.
- Dashboard: WebGL viewer (any browser), receives mesh state as a gossip subscriber.

## What we will NOT demo

- Real hardware. Track 1 does not require it; attempting it burns hackathon hours for marginal narrative gain.
- A pre-recorded video. The chaos must be live-triggerable by judges — that is the whole point.
- Cloud fallbacks. The moment we show a cloud backup path, the integration story collapses.
