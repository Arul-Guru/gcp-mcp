# gcloud practice labs (floci-gcp)

Activate the environment once per shell, then run any lab:

```powershell
. .\floci-env.ps1
.\labs\01-storage.ps1
```

| Lab | Covers | Status |
|---|---|---|
| [01-storage.ps1](01-storage.ps1) | buckets, cp/mv, ls variants, cat, object metadata, rm | all 9 steps pass |
| [02-pubsub.ps1](02-pubsub.ps1) | topics, subs, attributes, fan-out, ack deadline, dead-letter | 9/10 (`list-subscriptions` 404s) |
| [03-security.ps1](03-security.ps1) | service accounts, IAM bindings, secrets + versions, KMS encrypt/decrypt | all pass except `iam roles list` |
| [04-compute-scheduler-logging.ps1](04-compute-scheduler-logging.ps1) | projects, scheduler cron, logging write/read | scheduler + logging pass |
| [05-compute.ps1](05-compute.ps1) | VPC, subnets, firewall, VM lifecycle, disks, labels | all pass |

## Emulator gaps found by probing

| Command | Result | Workaround |
|---|---|---|
| `gcloud run ...` | Two separate problems, see note below | Use REST or a client library, not gcloud |
| `bq ls` | 500 on the discovery doc | BigQuery **REST works**: `curl http://localhost:4588/bigquery/v2/projects/floci-local/datasets` |
| `gcloud tasks ...` | 404 on every API version | Not implemented; no workaround |
| `gcloud functions list` | 404 | Not implemented |
| `gcloud sql instances list` | UNAUTHENTICATED | Rejects the dummy token |
| `gcloud pubsub topics list-subscriptions` | 404 | Use `gcloud pubsub subscriptions list` and filter on `topic` |
| `gcloud iam roles list` | 404 | Predefined-role catalog not served; bindings themselves work |
| `gcloud compute machine-types list` (no `--zones`) | gcloud crash (`AttributeError`) | Always pass `--zones=<zone>` |

## Behaviour differences to expect

- **Compute image catalog is empty**, so gcloud's default boot image
  (`debian-cloud/debian-12`) 404s. Create a disk and pass
  `--disk="name=<disk>,boot=yes"` instead of `--image-family`.
- **No default VPC.** Create the network and subnet before any instance or
  firewall rule.
- **Only 6 machine types** are stocked: `c3-standard-4`, `e2-standard-2`,
  `g2-standard-4`, `g2-standard-8`, `n2-standard-4`, `n2-standard-8`.
  There is no `e2-micro`.
- `gcloud storage objects describe` returns only `name` and `size` — no
  `contentType`, `md5Hash` or `storageClass`. Custom metadata reads back `null`.
- `gcloud secrets versions add` prints a **data-integrity error** because the
  emulator returns no CRC32C checksum. The data is stored correctly; verify with
  `gcloud secrets versions access`.

## PowerShell gotcha (not an emulator issue)

An unquoted comma is PowerShell's array operator, so `--labels=env=lab,owner=me`
reaches gcloud mangled. Always quote: `--labels="env=lab,owner=me"`. Same for
`--attribute=`, `--source-ranges=` and any other comma-separated flag value.


## Why `gcloud run` cannot work against floci-gcp

Worth understanding, because it looks like two bugs but is really one:

1. **Connectivity.** gcloud builds a *regional* hostname by prefixing the region
   onto the override host, so `http://localhost:4588/` becomes
   `us-central1-localhost` — which does not resolve.
   This part is fixable: floci publishes a wildcard `*.localhost.floci.io` that
   resolves to loopback, and Docker maps `[::]:4588`, so
   `CLOUDSDK_API_ENDPOINT_OVERRIDES_RUN="http://run.localhost.floci.io:4588/"`
   makes gcloud build `us-central1-run.localhost.floci.io`, which connects.

2. **API surface mismatch — the real blocker.** Once connected, `gcloud run`
   requests the *Knative v1* admin surface
   (`/apis/serving.knative.dev/v1/namespaces/<project>/services`).
   floci implements **Cloud Run v2 only**, so that path is unhandled and falls
   through to the GCS handler, which replies with a misleading
   `NoSuchBucket` / "Namespaces instance not found". No endpoint override can
   bridge this; gcloud has no flag to force the v2 surface.

So drive Cloud Run through v2 REST or a client library. This works today:

```bash
curl -X POST "http://localhost:4588/v2/projects/floci-local/locations/us-central1/services?serviceId=lab-svc"   -H "Content-Type: application/json"   -d '{"template":{"containers":[{"image":"nginx:alpine"}]}}'
```

The emulator assigns each service a real reachable URL, e.g.
`http://lab-svc-<hash>.us-central1.run.localhost.floci.io:4588`.
See [06-rest.sh](06-rest.sh), which also covers BigQuery (datasets and tables
both work over REST).
