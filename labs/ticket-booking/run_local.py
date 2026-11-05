"""Run the Cloud Run subscriber's logic locally against the floci emulator.

The emulator serves a Cloud Run URL but never starts a container, so the push
subscription has nothing behind it. This worker pulls from
`ticket-bookings-worker` and feeds each message through the exact same
`handler.enrich` the container would run, which is as close to the deployed
behaviour as the emulator allows.

    python run_local.py [--max-messages N]
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import httpx

from handler import BadEvent, enrich

ENDPOINT = os.environ.get("FLOCI_GCP_ENDPOINT", "http://localhost:4588")
PROJECT = os.environ.get("FLOCI_GCP_PROJECT", "floci-local")
SUBSCRIPTION = os.environ.get("SUBSCRIPTION", "ticket-bookings-worker")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-messages", type=int, default=10)
    args = parser.parse_args()

    base = f"{ENDPOINT}/v1/projects/{PROJECT}/subscriptions/{SUBSCRIPTION}"
    with httpx.Client(timeout=30) as client:
        pulled = client.post(
            f"{base}:pull",
            json={"maxMessages": args.max_messages, "returnImmediately": True},
        )
        pulled.raise_for_status()
        received = pulled.json().get("receivedMessages") or []

        if not received:
            print("no messages on", SUBSCRIPTION)
            return 0

        ack_ids, processed = [], 0
        for item in received:
            # Reassemble the push envelope shape so both paths share a decoder.
            from handler import decode_envelope

            try:
                booking = decode_envelope({"message": item["message"]})
                result = enrich(booking)
            except BadEvent as exc:
                print(f"  dropped malformed message: {exc}", file=sys.stderr)
                ack_ids.append(item["ackId"])  # unparseable: ack, never retry
                continue
            except Exception as exc:  # noqa: BLE001 - leave it for redelivery
                print(f"  retryable failure, not acking: {exc}", file=sys.stderr)
                continue

            print(json.dumps(result, indent=2))
            ack_ids.append(item["ackId"])
            processed += 1

        if ack_ids:
            client.post(f"{base}:acknowledge", json={"ackIds": ack_ids}).raise_for_status()

    print(f"\nprocessed {processed} of {len(received)} message(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
