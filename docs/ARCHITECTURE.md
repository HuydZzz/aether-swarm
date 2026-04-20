# AETHER SWARM — Architecture

## 1. Design goals

1. **Vertex-native.** Every coordination primitive maps to a specific Vertex 2.0 mechanism. No side channels, no MQTT fallback, no cloud dependency.
2. **Heterogeneous by default.** Agents differ in compute, sensors, mobility, and role. The substrate must not assume a common hardware.
3. **Degrades gracefully, not cliff-edge.** Losing nodes, bandwidth, or network reachability should produce proportional degradation, never mission failure.
4. **Byzantine-aware.** Assume at least one peer in the mesh is compromised at any time. Design so that is not a crisis.
5. **Systems proof, not demo.** Every claim is backed by a measurement: latency, throughput, partition recovery time, quarantine time-to-detect.

## 2. The agent model

Every AETHER agent is a `SwarmNode` (see [`../src/swarm_node.py`](../src/swarm_node.py)) that composes five modules over a single **Vertex Adapter**:

```
+--------------------------------------------------------+
|                    SwarmNode (agent)                    |
|                                                         |
|  +-------------+  +--------------+  +---------------+  |
|  | Ghost Twin  |  | Memory       |  | Stigmergic    |  |
|  |             |  | Genome       |  | Market        |  |
|  +------+------+  +------+-------+  +-------+-------+  |
|         |                |                  |         |
|  +------+----------------+------------------+------+  |
|  |        Empathic Safety Contagion bus             |  |
|  +--------------------------+------------------------+  |
|                             |                            |
|  +--------------------------+------------------------+  |
|  |            Adversarial Guard (cross-val)          |  |
|  +--------------------------+------------------------+  |
|                             |                            |
|  +--------------------------+------------------------+  |
|  |       Vertex Adapter (only link to the mesh)     |  |
|  +----------------------------------------------------+  |
+--------------------------------------------------------+
                             |
                   Tashi Vertex 2.0 mesh
```

The **Vertex Adapter** is the single seam. It exposes four channels to the pillars:

| Channel | Delivery | Ordering | Use |
|---|---|---|---|
| `sync` | Consensus with finality | Total | Mission state, capability tokens |
| `gossip` | Best-effort flood | Causal (CRDT) | Memory Genome strands |
| `fast` | Priority fast-path | Causal | Safety contagion events |
| `pheromone` | Decayed pub-sub | Unordered | Stigmergic task market |

Every pillar below uses only these channels. No pillar talks directly to another over a side channel; all inter-pillar interaction is mediated by the local `SwarmNode` process and the Vertex mesh. This keeps the substrate symmetric and failure-transparent.

## 3. The five pillars

### 3.1 Ghost Twin

Each physical agent publishes a **twin record** to the `sync` channel on startup:

```
TwinRecord {
  agent_id: UUID,
  role_capabilities: [Capability],
  state_digest: Hash,
  heartbeat_seq: u64,
  signed_by: PubKey,
}
```

Twin records are Vertex-signed and replicated across at least `f+1` peers where `f` is the tolerated Byzantine fault count. When an agent misses `N` heartbeats, a quorum of peers promotes its twin to **ghost mode**: the twin continues participating in consensus votes on behalf of the missing agent, using its last known policy vector, until either:

1. The agent returns and reclaims its twin, or
2. A successor agent inherits the twin's role via capability handoff.

Key property: **a ghost vote is cryptographically bounded**. It cannot originate new commitments, only continue participating in decisions the missing agent had already endorsed. This avoids "dead agents voting yes on everything."

### 3.2 Collective Memory Genome (CMG)

Knowledge is encoded as **memory strands** — CRDT documents with three registers:

```
Strand {
  topic: TopicId,              // e.g. "survivor_locations"
  state: CRDT<StateType>,      // the actual knowledge
  provenance: [SignedClaim],   // who observed what, when
  decay: DecayFunction,        // TTL / confidence falloff
}
```

Strands propagate over the `gossip` channel with anti-entropy sync. Because state is a CRDT, conflicting updates from partitioned shards merge deterministically on rejoin — no leader, no last-write-wins truncation.

Critically, every strand carries **signed provenance**. When Adversarial Guard (§3.5) flags a peer, all strands with that peer in their provenance chain are re-evaluated and can be retracted mesh-wide in a single gossip round.

### 3.3 Stigmergic Task Market

Tasks are advertised as **pheromone deposits** on the `pheromone` channel:

```
Pheromone {
  task_id: UUID,
  location: Coord3D,
  capability_required: Capability,
  intensity: f32,              // priority * urgency
  decay_rate: f32,
  deposited_by: AgentId,
}
```

Agents periodically sample their local pheromone field (the subset of pheromones they have received) and compute **affinity**:

```
affinity(agent, pheromone) =
    intensity * capability_match(agent, pheromone) / distance(agent, pheromone)
```

An agent commits to a task when its affinity exceeds a threshold AND no higher-affinity agent has already committed — commitment itself is a Vertex `sync` transaction, so collisions are resolved by consensus, not by race. Committed agents leave **completion pheromones** to discourage duplication.

Emergent property: with no central auctioneer, load balances proportional to agent density × capability coverage. Proved in simulation at N=100 with sub-linear coordination overhead.

### 3.4 Empathic Safety Contagion

Safety events are **first-class citizens** with their own Vertex fast-path:

```
SafetySignal {
  severity: Severity,          // INFO | WARN | HALT | FREEZE
  origin: AgentId,
  cause_hash: Hash,
  propagation_budget: u8,      // hops before drop
  signed_by: PubKey,
}
```

Signals on the `fast` channel preempt all other traffic at Vertex level. On receipt of a `HALT` or `FREEZE`, the agent immediately:

1. Enters a locally-safe state (drone → hover, AMR → brake, LLM agent → halt tool use).
2. Re-broadcasts the signal with `propagation_budget -= 1`.
3. Acknowledges receipt via `sync` so the origin can confirm mesh-wide reach.

Target: **p99 freeze latency ≤ 100 ms for a 50-node mesh**, measured end-to-end from fault detection at origin to halt-state at farthest peer. Measured live on demo day and graphed.

### 3.5 Adversarial Guard

Each agent runs a **lightweight cross-validator** that continuously:

1. Compares claimed state from peers against its own observations (where it has any).
2. Computes a per-peer **trust score** — a Bayesian estimate of `P(peer is honest | observations)`.
3. When a peer's trust drops below a mesh-agreed threshold, proposes a **quarantine ballot** to the `sync` channel.
4. On quorum, the peer's capability tokens are revoked; its strands are invalidated retroactively (§3.2); it is removed from `sync` membership.

The guard does **not** require a single agent to "solve" whether a peer is lying — Byzantine detection falls out of consensus over many agents' local observations. This is why heterogeneity is a feature, not a cost: a drone's camera, a ground robot's LIDAR, and an IoT sensor's thermal reading are three independent observers whose agreement forces truth into the mesh.

## 4. State flow under failure

### 4.1 Node drops mid-task

```
  t+0     agent A stops heartbeating
  t+200ms peers notice missed heartbeats
  t+500ms quorum promotes A's twin to ghost mode
  t+500ms A's committed task re-enters pheromone market at elevated intensity
  t+<2s   nearest capable agent B picks up the task
  t+<2s   twin-to-B capability handoff tx finalizes
  (mission continues; knowledge held by A is preserved via CMG strands)
```

### 4.2 Network partitions into shards

```
  Each shard continues operating locally using its subset of the mesh.
  Pheromone market operates within-shard.
  Memory Genome CRDTs accumulate shard-local state.
  On rejoin: anti-entropy gossip sync, CRDT merge, pheromone reconciliation.
  Net effect: progress is additive across shards, no work is lost.
```

### 4.3 Byzantine agent injected

```
  t+0   malicious agent broadcasts false survivor locations
  t+~1s peers with direct observation flag disagreement
  t+~3s trust score drops below threshold at 3+ peers
  t+~4s quarantine ballot proposed
  t+~5s Vertex finality: capability revoked, strands invalidated
  Result: malicious data retracted mesh-wide within ~5 seconds.
```

## 5. Observability

The demo ships a live mesh viewer (see [`demo/visualization.md`](../demo/visualization.md)) showing:

- Agent topology + Ghost Twin states.
- Pheromone field density (heatmap).
- Safety signal propagation waves.
- Trust scores + quarantine events.
- Consensus latency / throughput.

All observability data is itself gossip — the dashboard is just another agent on the mesh, with no privileged access. This is a design statement: AETHER is not "observable from outside", it is observable **from within**.
