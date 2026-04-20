"""
Chaos trigger — judge-facing CLI to break the swarm live.

Run during the demo to publish chaos commands on aether/chaos:
    python -m demo.chaos kill drone-01
    python -m demo.chaos revive drone-01
    python -m demo.chaos fault iot-01 power_loss
    python -m demo.chaos resume iot-01
    python -m demo.chaos byzantine-on amr-02
    python -m demo.chaos byzantine-off amr-02

The triggers are themselves Vertex messages, so the same Vertex integration
that runs the swarm runs the chaos — no side channel.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

# Make project root importable when run as `python -m demo.chaos ...` or directly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.vertex_adapter import VertexAdapter, TOPIC_CHAOS  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description="Chaos trigger for AETHER demo")
    sub = p.add_subparsers(dest="cmd", required=True)
    for cmd in ["kill", "revive", "byzantine-on", "byzantine-off"]:
        sp = sub.add_parser(cmd)
        sp.add_argument("target")
    sp = sub.add_parser("fault")
    sp.add_argument("target")
    sp.add_argument("cause", nargs="?", default="manual_fault")
    sp = sub.add_parser("resume")
    sp.add_argument("target")
    args = p.parse_args()

    if not os.getenv("VERTEX_USER"):
        print("ERROR: VERTEX_USER env var is required.", file=sys.stderr)
        sys.exit(2)

    adapter = VertexAdapter(node_id="chaos-trigger")
    adapter.start()

    kind_map = {
        "kill": "KILL",
        "revive": "REVIVE",
        "fault": "FAULT",
        "resume": "RESUME",
        "byzantine-on": "BYZANTINE_ON",
        "byzantine-off": "BYZANTINE_OFF",
    }
    payload = {"kind": kind_map[args.cmd], "target": args.target}
    if args.cmd == "fault":
        payload["cause"] = args.cause

    # Publish via the chaos channel (raw publish, since adapter doesn't have a typed method)
    adapter._client.publish(TOPIC_CHAOS,
                            __import__("json").dumps({
                                "channel": TOPIC_CHAOS,
                                "sender_id": "chaos-trigger",
                                "seq": 1,
                                "sent_at": time.time(),
                                "payload": payload,
                            }), qos=1)
    time.sleep(0.5)
    adapter.stop()
    print(f"chaos: sent {payload}")


if __name__ == "__main__":
    main()
