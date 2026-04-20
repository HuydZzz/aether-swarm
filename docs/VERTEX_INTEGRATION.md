# Vertex 2.0 Integration — the non-negotiable layer

The engineering team at Tashi flagged that submissions missing Vertex integration are invalid. This document maps every AETHER feature to a specific Vertex 2.0 primitive, so the integration is auditable end-to-end.

Reference: <https://github.com/tashigit/vertex-hackathon-guide>

---

## 1. Integration seam

All Vertex interaction is routed through a single module: [`../src/vertex_adapter.py`](../src/vertex_adapter.py). No other file in the codebase imports Vertex directly. This is deliberate:

- A reviewer can verify Vertex integration by reading one file.
- Upstream Vertex API changes touch one file.
- Pillar modules stay protocol-agnostic and unit-testable.

The adapter exposes four logical channels backed by Vertex primitives:

| AETHER channel | Vertex 2.0 primitive | Why |
|---|---|---|
| `sync` | Consensus-finalized transactions | Ghost Twin records, capability tokens, quarantine ballots — all require Byzantine agreement. |
| `gossip` | Best-effort broadcast with signed envelopes | CRDT memory strands — need causal delivery, not total order. |
| `fast` | Priority fast-path channel | Safety contagion — must preempt other traffic. |
| `pheromone` | Topic pub-sub with TTL | Stigmergic task market — ephemeral, decayed, high-volume. |

## 2. Mapping per pillar

### Ghost Twin ↔ Vertex `sync`

- **Twin registration** is a Vertex transaction signed by the agent's private key.
- **Heartbeat** is a lightweight signed message on `sync`; missed heartbeats are observed by every peer.
- **Ghost promotion** is a quorum ballot on `sync` — `f+1` signatures required.
- **Capability handoff** from ghost to successor is a two-phase Vertex transaction: proposal, then finalization.

**Why Vertex:** ghost votes must be non-repudiable. A non-BFT channel would allow a single malicious peer to forge "ghost reassignments."

### Collective Memory Genome ↔ Vertex `gossip`

- Each **memory strand** update is a CRDT delta wrapped in a signed Vertex gossip envelope.
- **Provenance claims** inside strands are themselves Vertex-signed, creating a verifiable chain of custody for every fact the swarm knows.
- **Retroactive invalidation** after Adversarial Guard quarantine uses a Vertex `sync` transaction that lists strand hashes to retract; every peer processes retractions deterministically.

**Why Vertex:** gossip on its own has no trust model. Vertex-signed envelopes give us "who claimed this fact" without a PKI.

### Stigmergic Task Market ↔ Vertex pub-sub (`pheromone`)

- Pheromone deposits are topic-addressed messages (`task.<region>.<capability>`).
- **Decay** is handled by Vertex TTLs — the network, not the agent, forgets stale pheromones.
- **Task commitment** is a `sync` transaction — this is the only consensus-gated step in the market. Everything else is eventually-consistent.

**Why Vertex:** the market scales because only commitments (low-rate) hit consensus; advertisements (high-rate) do not. This is the same principle that makes TCP/IP work.

### Empathic Safety Contagion ↔ Vertex `fast`

- Safety signals bypass normal ordering — they ride a dedicated priority channel.
- **Propagation budget** is the Vertex hop counter.
- **End-to-end acknowledgement** uses `sync` so the origin can confirm the mesh has frozen; this is the measured metric.

**Why Vertex:** only a consensus substrate gives us verifiable mesh-wide reach ("the swarm has frozen") as a finalized event rather than a hopeful broadcast.

### Adversarial Guard ↔ Vertex signed history + `sync` ballots

- Trust scoring uses Vertex-signed history: each peer's claims are cryptographically attributable.
- **Quarantine ballots** are `sync` transactions. Quorum revokes the target's capability tokens.
- **Capability revocation** is a Vertex mechanism; once revoked, the peer's transactions are rejected by every honest node automatically.

**Why Vertex:** without Vertex finality, a Byzantine peer could race the quarantine and keep committing damage. With finality, revocation is atomic and mesh-wide.

## 3. What we are NOT doing

To be unambiguous about integration depth, here is what AETHER explicitly refuses to do:

- **No MQTT wrapper.** Vertex is not used as a drop-in broker. Competitors do this; it hides Vertex's actual value.
- **No centralized state server.** The mesh is authoritative. There is no database behind it.
- **No optional Vertex path.** Every pillar fails closed if the adapter is unavailable — we do not provide "degraded mode without Vertex."
- **No trust in a single observation.** All safety-critical decisions require consensus, even if that costs a few hundred ms.

## 4. Verification checklist for judges

A reviewer can confirm integration in four steps:

1. Open [`../src/vertex_adapter.py`](../src/vertex_adapter.py) — confirm the four channels are present and wired to Vertex primitives.
2. Grep for `import` / `from vertex` across the codebase — it must appear **only** in `vertex_adapter.py`.
3. Run the `scenario_rescue.py` demo with `--vertex-trace` — emits a log of every Vertex transaction, signed message, and consensus round.
4. Disconnect the Vertex adapter mid-run — mission must halt immediately (we do not fake it).

## 5. References

- Vertex Hackathon Guide: <https://github.com/tashigit/vertex-hackathon-guide>
- Tashi Network: <https://tashi.network/>
- Competitor integrations analysed: `drone-swarm` (real, shallow), `xops` (real, minimal), `vertex_swarn` (nominal, via MQTT wrapper).

AETHER is designed so that removing Vertex removes the swarm. That is the integration standard we intend to meet.
