"""Publish sample ticket-booking events to the `ticket-bookings` topic."""

from __future__ import annotations

import base64
import json
import os
import sys

import httpx

ENDPOINT = os.environ.get("FLOCI_GCP_ENDPOINT", "http://localhost:4588")
PROJECT = os.environ.get("FLOCI_GCP_PROJECT", "floci-local")
TOPIC = os.environ.get("TOPIC", "ticket-bookings")

SAMPLES = [
    {
        "booking_id": "BK-10001",
        "customer": "ada@example.com",
        "show_title": "Breaking Bad",
        "seats": ["A1", "A2"],
        "channel": "web",
        "booked_at": "2026-11-05T10:00:00Z",
    },
    {
        "booking_id": "BK-10002",
        "customer": "linus@example.com",
        "show_title": "Stranger Things",
        "seats": ["C7"],
        "channel": "mobile",
        "booked_at": "2026-11-05T10:04:00Z",
    },
    {
        "booking_id": "BK-10003",
        "customer": "grace@example.com",
        "show_title": "The Mandalorian",
        "seats": ["B3", "B4", "B5"],
        "channel": "kiosk",
        "booked_at": "2026-11-05T10:09:00Z",
    },
]


def main() -> int:
    bookings = SAMPLES
    if len(sys.argv) > 1:  # a JSON file or a literal JSON object/array
        arg = sys.argv[1]
        text = open(arg, encoding="utf-8").read() if os.path.exists(arg) else arg
        loaded = json.loads(text)
        bookings = loaded if isinstance(loaded, list) else [loaded]

    messages = [
        {
            "data": base64.b64encode(
                json.dumps(b, separators=(",", ":")).encode()
            ).decode(),
            "attributes": {"eventType": "ticket.booked", "source": "booking-service"},
        }
        for b in bookings
    ]

    url = f"{ENDPOINT}/v1/projects/{PROJECT}/topics/{TOPIC}:publish"
    response = httpx.post(url, json={"messages": messages}, timeout=30)
    response.raise_for_status()
    ids = response.json().get("messageIds", [])
    for booking, message_id in zip(bookings, ids):
        title = booking.get("show_title", "(no show_title)")
        booking_id = booking.get("booking_id", "(no booking_id)")
        print(f"{booking_id}  {title:<20} -> {message_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
