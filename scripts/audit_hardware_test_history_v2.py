"""Offline audit for an exported /hardware_test/history JSON snapshot.

Usage: python3 -m scripts.audit_hardware_test_history_v2
       --history-json path.json --session-id FIELD_SESSION_NAME
No Firebase initialization, writes or model inference.
"""
import argparse
import json
from pathlib import Path

from ai.hardware_test_history_v2 import prepare_backlog


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history-json", type=Path, required=True,
                        help="JSON file containing exactly the /hardware_test/history subtree")
    parser.add_argument("--session-id", required=True,
                        help="Explicit observation session identifier; not guessed")
    args = parser.parse_args(argv)
    history = json.loads(args.history_json.read_text(encoding="utf-8"))
    plan = prepare_backlog(history, session_id=args.session_id)
    print("=== TASNIM /hardware_test/history V2 OFFLINE AUDIT ===")
    print("Valid slots:", len(plan["rows"]))
    print("Pending AI candidates:", len(plan["pending_timestamps"]))
    print("Warmup slots:", len(plan["warmup_slots"]))
    print("Skipped slots:", len(plan["skipped"]))
    for slot, reasons in sorted(plan["skipped"].items()):
        print("[SKIP]", slot, "|", "; ".join(reasons))
    print("[SAFE] No Firebase access; no model inference; no writes")


if __name__ == "__main__":
    main()
