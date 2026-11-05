# floci-gcp MCP server

An MCP server that gives Claude Code direct control of the local
[floci-gcp](https://floci.io/floci-gcp/getting-started/quick-start/) emulator
running in this repository. 62 tools across Pub/Sub, Cloud Storage, BigQuery,
Cloud Run, Secret Manager, IAM, Compute Engine, Cloud Scheduler and Cloud
Logging, plus a generic REST tool for everything else.

Nothing here touches real Google Cloud. There are no credentials, and all state
lives in `../data`.

## Why REST and not gcloud

Every tool speaks REST to the emulator directly. The `gcloud` CLI cannot reach
several of the emulated services at all — it requests Cloud Run's Knative v1
surface while floci implements v2 only, `bq` fails on the discovery document,
and Cloud Tasks and Cloud Functions are unimplemented. The REST surface is both
broader and more predictable. See `../labs/README.md` for the full survey.

## Setup

```bash
cd mcp-server
uv venv --python 3.11
uv pip install "mcp>=2.0,<3" "httpx>=0.27"
```

The emulator must be running:

```bash
cd ..
docker compose up -d
```

## Register with Claude Code

The repository root already contains a project-scoped `.mcp.json`, so starting
Claude Code from the repository root picks the server up automatically. Approve
it when prompted, then check it with `/mcp`.

If you move the repository, update the absolute paths in `.mcp.json`.

To register it globally instead:

```bash
claude mcp add floci-gcp \
  --env PYTHONPATH=/absolute/path/to/FlociGCP/mcp-server \
  -- /absolute/path/to/FlociGCP/mcp-server/.venv/Scripts/python.exe -m floci_mcp
```

## Configuration

All optional; the defaults match this repository's `docker-compose.yml`.

| Variable | Default | Purpose |
|---|---|---|
| `FLOCI_GCP_ENDPOINT` | `http://localhost:4588` | Emulator base URL |
| `FLOCI_GCP_PROJECT` | `floci-local` | Project id used in resource paths |
| `FLOCI_GCP_REGION` | `us-central1` | Default region for regional tools |
| `FLOCI_GCP_ZONE` | `us-central1-a` | Default zone for Compute tools |
| `FLOCI_GCP_TIMEOUT` | `60` | Per-request timeout, seconds |
| `FLOCI_GCP_ALLOW_DESTRUCTIVE` | `1` | Set to `0` to refuse every write and delete |

Setting `FLOCI_GCP_ALLOW_DESTRUCTIVE=0` makes the server read-only: creates,
updates and deletes are refused with an explanatory message, and `floci_request`
allows only `GET`.

## Tools

| Group | Tools |
|---|---|
| Core | `floci_health`, `floci_list_projects`, `floci_request` |
| Pub/Sub | `pubsub_list_topics`, `pubsub_create_topic`, `pubsub_delete_topic`, `pubsub_publish`, `pubsub_list_subscriptions`, `pubsub_create_subscription`, `pubsub_delete_subscription`, `pubsub_pull` |
| Storage | `storage_list_buckets`, `storage_create_bucket`, `storage_delete_bucket`, `storage_list_objects`, `storage_read_object`, `storage_write_object`, `storage_delete_object` |
| BigQuery | `bq_list_datasets`, `bq_create_dataset`, `bq_delete_dataset`, `bq_list_tables`, `bq_get_table`, `bq_create_table`, `bq_delete_table`, `bq_insert_rows`, `bq_query` |
| Cloud Run | `run_list_services`, `run_get_service`, `run_deploy_service`, `run_delete_service`, `run_list_jobs`, `run_create_job`, `run_execute_job`, `run_delete_job` |
| Secret Manager | `secrets_list`, `secrets_create`, `secrets_list_versions`, `secrets_add_version`, `secrets_access`, `secrets_delete` |
| IAM | `iam_list_service_accounts`, `iam_create_service_account`, `iam_delete_service_account`, `iam_get_policy`, `iam_add_binding`, `iam_remove_binding` |
| Compute | `compute_list_instances`, `compute_list_networks`, `compute_create_network`, `compute_create_subnet`, `compute_create_disk`, `compute_list_disks`, `compute_create_instance`, `compute_instance_action` |
| Scheduler | `scheduler_list_jobs`, `scheduler_create_job`, `scheduler_run_job`, `scheduler_delete_job` |
| Logging | `logging_write`, `logging_list`, `logging_list_sinks` |

Base64 encoding, `gs://` prefixes, nested object keys, and BigQuery's
`{"f":[{"v":...}]}` row format are all handled for you: Pub/Sub messages and
secrets go in and come out as plain text, and query results arrive as plain
dicts.

### The escape hatch

`floci_request` sends an arbitrary REST call for any API without a typed tool —
KMS, GKE, Cloud SQL, Managed Kafka, Cloud Functions, Eventarc, Monitoring,
Datastore, Firestore. The literal strings `{project}` and `{region}` in a path
are substituted for you:

```
floci_request(path="/v1/projects/{project}/locations/{region}/keyRings")
floci_request(path="/sql/v1beta4/projects/{project}/instances")
```

## Example prompts

- "Check the floci emulator is healthy."
- "Create a topic `orders`, a subscription on it, publish three test orders and
  pull them back."
- "Make a BigQuery dataset `analytics` with an `events` table, load ten sample
  rows, then show me the daily counts."
- "Deploy nginx:alpine to Cloud Run as `web` and tell me its URL."
- "Store a database password in Secret Manager and grant `app-sa` access to it."

## Emulator behaviour the tools work around

These are emulator limits, not bugs in the server:

- **Cloud Run** is v2-only, and create/delete return long-running operations.
  A deleted service can still appear in a listing for a few seconds.
  `run_deploy_service` reads the service back so you get its URL, and a service
  whose image never starts is still created but reports a failed
  `terminalCondition`.
- **Compute Engine** has no public image catalog, so an instance needs an
  existing disk as its boot disk — create one with `compute_create_disk`. The
  emulator also rejects an instance with no subnetwork, so
  `compute_create_instance` resolves one from the network automatically and
  tells you to create a subnet if none exists.
- **Only six machine types** are stocked: `c3-standard-4`, `e2-standard-2`,
  `g2-standard-4`, `g2-standard-8`, `n2-standard-4`, `n2-standard-8`. There is
  no `e2-micro`.
- **Secret Manager** returns no CRC32C checksum, so some clients report a
  spurious data-integrity warning. The stored value is correct.
- **`pubsub topics list-subscriptions`** is not served, so
  `pubsub_list_subscriptions` filters by topic client-side.
- **The IAM predefined-role catalog** is not served. Bindings work; listing all
  available roles does not.
- **Cloud Tasks** is not implemented at any API version.

Failed calls reach Claude as a `ToolError` carrying the HTTP status and the
response body, which is usually enough to diagnose the problem without opening
the emulator logs.

## Tests

Both need the emulator running. They create resources prefixed `mcpsmoke` and
delete them on the way out.

```bash
.venv/Scripts/python.exe tests/smoke_test.py   # 56 checks across every service
.venv/Scripts/python.exe tests/stdio_test.py   # MCP handshake over a subprocess
```

`smoke_test.py` calls tools through `call_tool`, so the registered schemas are
exercised as Claude Code would. `stdio_test.py` launches the server as a real
subprocess and speaks the protocol over stdio.

## Adding a service

1. Write `floci_mcp/services/<name>.py` with a `register(mcp)` function that
   declares tools via `@mcp.tool(...)`.
2. Add the module to the imports and to `MODULES` in
   `floci_mcp/services/__init__.py`.
3. Raise `FlociError` for anything the caller should see — the MCP SDK only
   forwards a `ToolError`'s message, and withholds the text of any other
   exception as a server crash.
4. Add coverage to `tests/smoke_test.py`.

## Layout

```
mcp-server/
  floci_mcp/
    __main__.py          entry point (stdio transport)
    server.py            builds the server, registers modules, holds instructions
    client.py            async REST client, FlociError, shared encode helpers
    config.py            environment-driven settings
    services/            one module per service, each exposing register(mcp)
  tests/
    smoke_test.py        end-to-end CRUD against a live emulator
    stdio_test.py        protocol handshake over a subprocess
```
