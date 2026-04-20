# Build Roadmap — 7 days to submission

A realistic, aggressive plan from blueprint to submittable demo. Assumes one dedicated builder + optional collaborator help.

---

## Day 0 — Setup (half day)

- [ ] Clone Vertex hackathon guide: <https://github.com/tashigit/vertex-hackathon-guide>
- [ ] Get a 2-node Vertex mesh running locally (this is the Warm Up "Stateful Handshake" task — do it first; a valid Warm Up is a safety net for submission validity).
- [ ] Pick language: **Python** for pillars + LLM agents, **Rust** only if Vertex SDK requires it. (Competitors over-engineered with polyglot stacks; we will not.)
- [ ] Set up a monorepo, CI with pytest, pre-commit hooks.

**Gate:** two Python processes talking through Vertex end-to-end. Commit.

---

## Day 1 — Vertex Adapter + minimal SwarmNode

- [ ] Implement `vertex_adapter.py` with the four channels (`sync`, `gossip`, `fast`, `pheromone`). Stub any channel Vertex doesn't expose natively as a layered pattern over the closest primitive.
- [ ] Implement `swarm_node.py`: registration, heartbeat, graceful shutdown.
- [ ] Unit tests: spawn 5 nodes, verify they all see each other.
- [ ] Decision log commit: document which Vertex primitives back which channels.

**Gate:** 5 `SwarmNode` processes auto-discover each other via Vertex. Commit.

---

## Day 2 — Ghost Twin + Memory Genome

- [ ] `ghost_twin.py`: TwinRecord, heartbeat tracking, quorum-based ghost promotion, capability handoff.
- [ ] `memory_genome.py`: CRDT strands (use a library, e.g. `pycrdt` or `Automerge` via WASM binding; do not roll your own CRDT).
- [ ] Kill -9 one of five nodes during a test run. Confirm twin stays in consensus; strands remain intact.

**Gate:** 5-node test where one node dies, twin persists for `T` seconds, strands are recoverable from any surviving node. Commit.

---

## Day 3 — Stigmergic Market + Empathic Safety

- [ ] `stigmergic_market.py`: pheromone deposit / decay / affinity calculation / commitment transactions.
- [ ] `empathic_safety.py`: fast-path safety signal + mesh-wide freeze + ack collection.
- [ ] Measure: end-to-end freeze latency across 10 nodes. Target sub-100 ms p99 at this scale.

**Gate:** 10-node mesh, a fake "fault" at node 0 freezes all 10 within 100 ms p99. Commit.

---

## Day 4 — Adversarial Guard + scale-up

- [ ] `adversarial_guard.py`: per-peer trust score, quarantine ballot, capability revocation path.
- [ ] Write a Byzantine agent harness: a `SwarmNode` variant that broadcasts fabricated observations.
- [ ] Inject it into a 20-node mesh; verify quarantine within 5 s.
- [ ] Scale test: push to 50 nodes. Measure consensus latency, gossip throughput, freeze latency at scale. Tune.

**Gate:** 50-node mesh holds. Byzantine is quarantined. Metrics captured. Commit.

---

## Day 5 — Blackout Rescue scenario

- [ ] `scenario_rescue.py`: spawn 20 drone sims + 15 AMR sims + 10 IoT sensors + 5 LLM agents.
- [ ] Implement survivor simulation + mission success criteria.
- [ ] Wire the chaos script: cloud drop, partition, mass kill, Byzantine injection, each triggerable by a judge.
- [ ] Dashboard (gossip subscriber) showing topology, pheromone heatmap, trust scores, metrics.

**Gate:** end-to-end run of Blackout Rescue, all chaos actions triggerable, swarm recovers in every case. Commit.

---

## Day 6 — Polish, record, write

- [ ] Polish dashboard visuals. Make partition and quarantine events visible and beautiful.
- [ ] Record a 3-minute narrated demo video (backup for the live demo).
- [ ] Finalise `PITCH.md` with measured metrics from the 50-node run replacing any placeholders.
- [ ] Screenshot the competitor comparison table with real numbers in our column.

**Gate:** submission-ready artifacts. Commit + tag `v0.1-submission`.

---

## Day 7 — Submit + buffer

- [ ] Re-run the full demo on a clean machine to verify reproducibility.
- [ ] Submit with `PITCH.md`, repo link, demo video, measured metrics document.
- [ ] Post in the Tashi Discord hackathon channel.

---

## What to cut if behind schedule

Priority order for de-scoping (cut from bottom):

1. LLM tactical agents in the demo → replace with scripted "tactical" planners. The mesh proof doesn't need LLMs; they're narrative colour.
2. IoT sensors → fold into drone observations. Reduces heterogeneity claim from 4 classes to 3; acceptable.
3. Scenario 2 / 3 → these are backups anyway.
4. Dashboard polish → judges care about the mesh, not the CSS. A rough viewer with correct data beats a pretty viewer with faked data.

**Do not cut, ever:**

- Vertex integration depth (Vertex Adapter covering all four channels).
- 50-node scale proof.
- Live Byzantine injection + quarantine.
- Measured latency numbers.

Those four are what win Track 1.

---

## Pre-submission checklist

- [ ] Every pillar has a passing test.
- [ ] `grep -R "import.*vertex"` returns **only** `vertex_adapter.py`.
- [ ] Disconnecting the adapter halts the swarm (verified).
- [ ] Demo video under 3 minutes.
- [ ] Pitch readable by a non-robotics judge.
- [ ] Competitor-comparison table has measured numbers, not promises.
- [ ] Warm-up "Stateful Handshake" is also submitted (zero-cost fallback for submission validity).
