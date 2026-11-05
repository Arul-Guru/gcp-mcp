# floci-gcp local setup

Local GCP emulator (floci-gcp 0.12.0) on `http://localhost:4588`, project `floci-local`.

## Start / stop

```powershell
docker compose up -d      # start
docker compose ps         # status (should read "healthy")
docker compose logs -f    # follow logs
docker compose down       # stop
```

State persists in `./data` (`FLOCI_GCP_STORAGE_MODE: hybrid`). Delete that
directory to reset the emulator to empty.

## Drive it from Claude Code

[`mcp-server/`](mcp-server/README.md) is an MCP server that gives Claude Code
62 tools for this emulator (Pub/Sub, Storage, BigQuery, Cloud Run, Secret
Manager, IAM, Compute, Scheduler, Logging, plus a generic REST tool). The
project-scoped `.mcp.json` registers it, so starting Claude Code from this
directory picks it up — approve it when prompted and check with `/mcp`.

It talks REST directly, so it reaches the services `gcloud` cannot (see the
gaps table in [labs/README.md](labs/README.md)).

## Point your shell at the emulator

Per-shell, so your real gcloud config and credentials stay untouched:

```powershell
. .\floci-env.ps1     # PowerShell
```
```bash
source ./floci-env.sh  # bash / git-bash
```

This sets the `*_EMULATOR_HOST` vars the google-cloud-* client libraries read,
plus the `CLOUDSDK_*` endpoint overrides the gcloud CLI needs (gcloud ignores
the `*_EMULATOR_HOST` vars).

## Smoke test

```powershell
gcloud pubsub topics create my-topic
gcloud pubsub subscriptions create my-sub --topic=my-topic
gcloud pubsub topics publish my-topic --message="hello"
gcloud pubsub subscriptions pull my-sub --auto-ack

gcloud storage buckets create gs://my-bucket
gcloud storage ls gs://my-bucket
```

## In application code

Point clients at `localhost:4588`, project `floci-local`, no credentials.
The client libraries do this automatically once `floci-env` is sourced.

Docs: https://floci.io/floci-gcp/getting-started/quick-start/
