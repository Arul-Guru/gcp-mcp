# Ticket booking → Pub/Sub → Cloud Run → TVMaze

A booking service publishes a ticket-booking event; a Cloud Run subscriber
receives it, looks the booked show up on the public
[TVMaze](https://www.tvmaze.com/api) API, and emits the enriched event.

```
publish_booking.py ──► topic ticket-bookings ──┬─► sub ticket-bookings-run-push ──► Cloud Run (push)
                                               └─► sub ticket-bookings-worker   ──► run_local.py (pull)
```

## What the emulator does and does not do

floci serves the Cloud Run **admin** API and routes the service URL, but it
never starts a container. `GET /healthz` on the service URL returns
**503 `Cloud Run service has no ready runtime`**, so the push subscription
delivers into nothing — the emulator drops the delivery rather than retaining a
backlog. The deployed service object, its revision, URL and traffic split are
all real; only the runtime is absent.

`run_local.py` exists for that reason. It pulls from the second subscription and
calls the same `handler.enrich` the container runs, so the enrichment path is
genuinely exercised end to end against the live TVMaze API. Point the push
subscription at a real Cloud Run deployment and `app.py` serves the same result
with no code change.

## Files

| File | Role |
|---|---|
| `handler.py` | Envelope decoding + TVMaze lookup. Shared by both paths. |
| `app.py` | FastAPI push endpoint — the Cloud Run entry point. |
| `publish_booking.py` | Publishes sample (or supplied) booking events. |
| `run_local.py` | Pull worker running the container's logic locally. |
| `Dockerfile` | Image for a real Cloud Run deploy. |

## Run it

```bash
PY=../../mcp-server/.venv/Scripts/python.exe
$PY publish_booking.py                   # three samples
$PY publish_booking.py '{"booking_id":"BK-2","customer":"x@e.com","show_title":"Severance","seats":["D1"]}'
$PY run_local.py                         # pull, enrich, ack
```

## Event shape

```json
{
  "booking_id": "BK-10001",
  "customer": "ada@example.com",
  "show_title": "Breaking Bad",
  "seats": ["A1", "A2"],
  "channel": "web",
  "booked_at": "2026-11-05T10:00:00Z"
}
```

Published with attributes `eventType=ticket.booked`, `source=booking-service`.
The subscriber adds a `show` object: TVMaze id, name, genres, status, premiered
and ended dates, average runtime, rating, network and a tag-stripped summary.
An unmatched title yields `"show_found": false` rather than an error.

## Ack policy

- **2xx** — enriched, acked.
- **400** — unparseable envelope or a booking with no `show_title`. Acked
  deliberately: redelivering an event that can never parse would loop forever.
- **500** — TVMaze unreachable or erroring. Nacked, so Pub/Sub retries.

## Deploying for real

```bash
docker build -t gcr.io/PROJECT/ticket-booking-subscriber .
docker push  gcr.io/PROJECT/ticket-booking-subscriber
gcloud run deploy ticket-booking-subscriber \
  --image gcr.io/PROJECT/ticket-booking-subscriber --region us-central1
```

Then point the push subscription's endpoint at the deployed URL. On real GCP,
add an OIDC token to the push config and grant the push service account
`roles/run.invoker`; the emulator enforces no auth.
