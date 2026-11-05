"""Cloud Run push subscriber for the `ticket-bookings` topic."""

from __future__ import annotations

import json
import logging
import os

from fastapi import FastAPI, Request, Response

from handler import BadEvent, enrich

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("ticket-booking")

app = FastAPI(title="ticket-booking-subscriber")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/")
async def receive(request: Request) -> Response:
    """Handle one Pub/Sub push delivery.

    A 2xx acks the message. A 400 on a malformed payload acks it too, on
    purpose: redelivering an unparseable event would loop forever. Anything
    that might succeed on a retry (a TVMaze outage) returns 500 and is nacked.
    """
    try:
        envelope = await request.json()
    except Exception:  # noqa: BLE001
        return Response(content="body is not JSON", status_code=400)

    try:
        booking = _decode(envelope)
        result = enrich(booking)
    except BadEvent as exc:
        log.warning("dropping malformed event: %s", exc)
        return Response(content=str(exc), status_code=400)
    except Exception as exc:  # noqa: BLE001 - retryable, so nack it
        log.exception("enrichment failed")
        return Response(content=str(exc), status_code=500)

    log.info("enriched booking: %s", json.dumps(result))
    return Response(
        content=json.dumps(result), media_type="application/json", status_code=200
    )


def _decode(envelope: dict) -> dict:
    from handler import decode_envelope

    return decode_envelope(envelope)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
