"""Enrich a ticket-booking event with show details from the TVMaze API.

Shared by the Cloud Run push endpoint (app.py) and the local pull worker
(run_local.py), so both paths run byte-for-byte the same logic.
"""

from __future__ import annotations

import base64
import json
import os
from typing import Any

import httpx

TVMAZE_BASE = os.environ.get("TVMAZE_BASE", "https://api.tvmaze.com")
HTTP_TIMEOUT = float(os.environ.get("TVMAZE_TIMEOUT", "15"))


class BadEvent(ValueError):
    """The push envelope or the booking payload was not usable."""


def decode_envelope(envelope: dict[str, Any]) -> dict[str, Any]:
    """Pull the booking dict out of a Pub/Sub push envelope."""
    message = envelope.get("message")
    if not isinstance(message, dict):
        raise BadEvent("envelope has no 'message' object")

    data = message.get("data")
    if not data:
        raise BadEvent("message has no 'data' field")

    try:
        raw = base64.b64decode(data)
    except Exception as exc:  # noqa: BLE001 - surfaced to the caller as 400
        raise BadEvent(f"message data is not valid base64: {exc}") from exc

    try:
        booking = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BadEvent(f"message data is not valid JSON: {exc}") from exc

    if not isinstance(booking, dict):
        raise BadEvent("booking payload must be a JSON object")
    return booking


def lookup_show(title: str) -> dict[str, Any] | None:
    """Single-search TVMaze for `title`. Returns None when nothing matches."""
    with httpx.Client(timeout=HTTP_TIMEOUT) as client:
        response = client.get(
            f"{TVMAZE_BASE}/singlesearch/shows", params={"q": title}
        )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


def _plain(html: str | None) -> str | None:
    """TVMaze summaries arrive as HTML; strip the handful of tags it uses."""
    if not html:
        return None
    import re

    return re.sub(r"<[^>]+>", "", html).strip()


def enrich(booking: dict[str, Any]) -> dict[str, Any]:
    """Look the booked show up on TVMaze and fold the details into the event."""
    title = booking.get("show_title")
    if not title:
        raise BadEvent("booking is missing 'show_title'")

    show = lookup_show(title)
    if show is None:
        return {
            "booking_id": booking.get("booking_id"),
            "customer": booking.get("customer"),
            "show_title": title,
            "show_found": False,
            "show": None,
        }

    network = show.get("network") or show.get("webChannel") or {}
    return {
        "booking_id": booking.get("booking_id"),
        "customer": booking.get("customer"),
        "seats": booking.get("seats"),
        "show_title": title,
        "show_found": True,
        "show": {
            "id": show.get("id"),
            "name": show.get("name"),
            "type": show.get("type"),
            "language": show.get("language"),
            "genres": show.get("genres"),
            "status": show.get("status"),
            "premiered": show.get("premiered"),
            "ended": show.get("ended"),
            "average_runtime": show.get("averageRuntime"),
            "rating": (show.get("rating") or {}).get("average"),
            "network": network.get("name"),
            "url": show.get("url"),
            "summary": _plain(show.get("summary")),
        },
    }
