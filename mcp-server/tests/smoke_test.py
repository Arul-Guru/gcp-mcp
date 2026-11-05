"""End-to-end smoke test: drives every tool group against a live emulator.

Run it the way Claude Code would use the server, through call_tool, so the
registered schemas are exercised too:

    .venv/Scripts/python.exe tests/smoke_test.py

It creates resources prefixed `mcpsmoke` and deletes them on the way out.
Exits non-zero if any step fails.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp.server.mcpserver.exceptions import ToolError  # noqa: E402

from floci_mcp.client import client  # noqa: E402
from floci_mcp.server import build_server  # noqa: E402

logging.getLogger("httpx").setLevel(logging.WARNING)

TAG = "mcpsmoke"
SUFFIX = str(int(time.time()))[-6:]

# Resource names live at module scope so teardown can run even if a check
# raises partway through.
TOPIC = f"{TAG}-topic-{SUFFIX}"
SUB = f"{TAG}-sub-{SUFFIX}"
BUCKET = f"{TAG}-bucket-{SUFFIX}"
DATASET = f"{TAG}_ds_{SUFFIX}"
TABLE = "events"
SECRET = f"{TAG}-secret-{SUFFIX}"
SA_ID = f"{TAG}-sa-{SUFFIX}"[:30]
CRON = f"{TAG}-cron-{SUFFIX}"
DISK = f"{TAG}-disk-{SUFFIX}"
VM = f"{TAG}-vm-{SUFFIX}"
NET = f"{TAG}-net-{SUFFIX}"
SUBNET = f"{TAG}-subnet-{SUFFIX}"
LOG_NAME = f"{TAG}-log"

passed: list[str] = []
failed: list[tuple[str, str]] = []


def _payload(result: Any) -> Any:
    if getattr(result, "structured_content", None) is not None:
        return result.structured_content
    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            try:
                return json.loads(text)
            except ValueError:
                return text
    return None


async def call(mcp: Any, label: str, tool: str, args: dict[str, Any] | None = None) -> Any:
    """Invoke a tool, record pass/fail, and return its payload."""
    try:
        result = await mcp.call_tool(tool, args or {})
    except Exception as exc:  # noqa: BLE001 - the test reports every failure
        failed.append((label, f"{exc.__class__.__name__}: {exc}"))
        print(f"  FAIL  {label}: {exc}")
        return None

    if getattr(result, "is_error", False):
        detail = str(_payload(result))[:300]
        failed.append((label, detail))
        print(f"  FAIL  {label}: {detail}")
        return None

    passed.append(label)
    print(f"  ok    {label}")
    return _payload(result)


async def run_checks(mcp: Any) -> None:
    topic, sub, bucket = TOPIC, SUB, BUCKET
    dataset, table = DATASET, TABLE
    secret, sa_id, cron = SECRET, SA_ID, CRON
    disk, vm, net, subnet = DISK, VM, NET, SUBNET
    log_name = LOG_NAME

    print("\n== pub/sub ==")
    await call(mcp, "create topic", "pubsub_create_topic", {"topic": topic})
    await call(
        mcp,
        "create subscription",
        "pubsub_create_subscription",
        {"subscription": sub, "topic": topic, "ack_deadline_seconds": 30},
    )
    await call(
        mcp,
        "publish",
        "pubsub_publish",
        {
            "topic": topic,
            "messages": ["first message", "second message"],
            "attributes": {"source": "smoke"},
        },
    )
    pulled = await call(
        mcp, "pull", "pubsub_pull", {"subscription": sub, "max_messages": 10}
    )
    if pulled is not None:
        got = [m["data"] for m in pulled.get("messages", [])]
        if "first message" in got and "second message" in got:
            passed.append("pull round-trip")
            print("  ok    pull round-trip (both messages decoded)")
        else:
            failed.append(("pull round-trip", f"got {got}"))
            print(f"  FAIL  pull round-trip: got {got}")
    await call(mcp, "list subscriptions by topic", "pubsub_list_subscriptions", {"topic": topic})

    print("\n== storage ==")
    await call(mcp, "create bucket", "storage_create_bucket", {"bucket": bucket})
    await call(
        mcp,
        "write object",
        "storage_write_object",
        {
            "bucket": bucket,
            "object_name": "nested/path/hello.txt",
            "content": "hello from the smoke test",
        },
    )
    read = await call(
        mcp,
        "read object",
        "storage_read_object",
        {"bucket": f"gs://{bucket}", "object_name": "nested/path/hello.txt"},
    )
    if read is not None:
        if read.get("content") == "hello from the smoke test":
            passed.append("object round-trip")
            print("  ok    object round-trip (nested key + gs:// form)")
        else:
            failed.append(("object round-trip", str(read)[:200]))
            print(f"  FAIL  object round-trip: {str(read)[:200]}")
    await call(mcp, "list objects", "storage_list_objects", {"bucket": bucket})

    print("\n== bigquery ==")
    await call(mcp, "create dataset", "bq_create_dataset", {"dataset_id": dataset})
    await call(
        mcp,
        "create table",
        "bq_create_table",
        {
            "dataset_id": dataset,
            "table_id": table,
            "schema": [
                {"name": "id", "type": "INTEGER"},
                {"name": "name", "type": "STRING"},
            ],
        },
    )
    await call(
        mcp,
        "insert rows",
        "bq_insert_rows",
        {
            "dataset_id": dataset,
            "table_id": table,
            "rows": [{"id": 1, "name": "alpha"}, {"id": 2, "name": "beta"}],
        },
    )
    q = await call(
        mcp,
        "query",
        "bq_query",
        {"sql": f"SELECT id, name FROM {dataset}.{table} ORDER BY id"},
    )
    if q is not None:
        names = [r.get("name") for r in q.get("rows", [])]
        if names == ["alpha", "beta"]:
            passed.append("sql round-trip")
            print("  ok    sql round-trip (rows flattened to dicts)")
        else:
            failed.append(("sql round-trip", f"got {names}"))
            print(f"  FAIL  sql round-trip: got {names}")
    await call(mcp, "get table", "bq_get_table", {"dataset_id": dataset, "table_id": table})

    print("\n== secret manager ==")
    await call(mcp, "create secret", "secrets_create", {"secret_id": secret})
    await call(
        mcp,
        "add version",
        "secrets_add_version",
        {"secret_id": secret, "payload": "s3cr3t-value"},
    )
    acc = await call(mcp, "access secret", "secrets_access", {"secret_id": secret})
    if acc is not None:
        if acc.get("value") == "s3cr3t-value":
            passed.append("secret round-trip")
            print("  ok    secret round-trip")
        else:
            failed.append(("secret round-trip", str(acc)[:200]))
            print(f"  FAIL  secret round-trip: {str(acc)[:200]}")

    print("\n== iam ==")
    await call(
        mcp,
        "create service account",
        "iam_create_service_account",
        {"account_id": sa_id, "display_name": "smoke test runner"},
    )
    await call(
        mcp,
        "add binding",
        "iam_add_binding",
        {"role": "roles/pubsub.subscriber", "member": sa_id},
    )
    pol = await call(mcp, "get policy", "iam_get_policy")
    if pol is not None:
        members = [m for b in pol.get("bindings", []) for m in b.get("members", [])]
        if any(sa_id in m for m in members):
            passed.append("binding visible in policy")
            print("  ok    binding visible in policy")
        else:
            failed.append(("binding visible in policy", "member not found"))
            print("  FAIL  binding visible in policy")
    await call(
        mcp,
        "remove binding",
        "iam_remove_binding",
        {"role": "roles/pubsub.subscriber", "member": sa_id},
    )

    print("\n== cloud run ==")
    await call(mcp, "list services", "run_list_services")
    await call(mcp, "list jobs", "run_list_jobs")

    print("\n== compute ==")
    await call(mcp, "list networks", "compute_list_networks")
    await call(mcp, "create network", "compute_create_network", {"name": net})
    await call(
        mcp,
        "create subnet",
        "compute_create_subnet",
        {"name": subnet, "network": net, "ip_cidr_range": "10.42.0.0/24"},
    )
    await call(mcp, "create disk", "compute_create_disk", {"name": disk, "size_gb": 10})
    # subnet is deliberately omitted: the tool should resolve it from the network.
    await call(
        mcp,
        "create instance (subnet auto-resolved)",
        "compute_create_instance",
        {"name": vm, "boot_disk": disk, "machine_type": "e2-standard-2", "network": net},
    )
    await call(mcp, "list instances", "compute_list_instances")

    print("\n== scheduler ==")
    await call(
        mcp,
        "create cron job",
        "scheduler_create_job",
        {
            "name": cron,
            "schedule": "0 2 * * *",
            "pubsub_topic": topic,
            "message_body": "nightly tick",
        },
    )
    await call(mcp, "run cron job", "scheduler_run_job", {"name": cron})
    await call(mcp, "list cron jobs", "scheduler_list_jobs")

    print("\n== logging ==")
    await call(
        mcp,
        "write log entry",
        "logging_write",
        {"log_name": log_name, "text": "smoke test entry", "severity": "WARNING"},
    )
    await call(mcp, "list log entries", "logging_list", {"limit": 5})
    await call(mcp, "list sinks", "logging_list_sinks")

    print("\n== escape hatch ==")
    await call(
        mcp,
        "floci_request (KMS key rings)",
        "floci_request",
        {"path": "/v1/projects/{project}/locations/{region}/keyRings"},
    )
    await call(
        mcp,
        "floci_request (Cloud SQL)",
        "floci_request",
        {"path": "/sql/v1beta4/projects/{project}/instances"},
    )

    print("\n== error handling ==")
    # A failing call must reach the model as a ToolError carrying the HTTP
    # status and body, not as an opaque crash.
    try:
        await mcp.call_tool(
            "storage_read_object", {"bucket": bucket, "object_name": "nope.txt"}
        )
        failed.append(("missing object reports an error", "call unexpectedly succeeded"))
        print("  FAIL  missing object did not report an error")
    except ToolError as exc:
        if "404" in str(exc) and "nope.txt" in str(exc):
            passed.append("error message reaches the caller")
            print("  ok    error message reaches the caller (404 + body preserved)")
        else:
            failed.append(("error message reaches the caller", str(exc)[:200]))
            print(f"  FAIL  error detail lost: {str(exc)[:200]}")
    except Exception as exc:  # noqa: BLE001
        failed.append(
            ("error message reaches the caller", f"wrong type {type(exc).__name__}: {exc}")
        )
        print(f"  FAIL  wrong exception type {type(exc).__name__}: {exc}")

async def teardown(mcp: Any) -> None:
    """Delete everything the checks created. Runs even if a check raised."""
    topic, sub, bucket = TOPIC, SUB, BUCKET
    dataset = DATASET
    secret, sa_id, cron = SECRET, SA_ID, CRON
    disk, vm, net, subnet = DISK, VM, NET, SUBNET

    print("\n== cleanup ==")
    await call(mcp, "delete cron job", "scheduler_delete_job", {"name": cron})
    await call(
        mcp,
        "delete instance",
        "compute_instance_action",
        {"name": vm, "action": "delete"},
    )
    await call(
        mcp,
        "delete disk",
        "floci_request",
        {
            "method": "DELETE",
            "path": f"/compute/v1/projects/{client.project}/zones/{client.zone}/disks/{disk}",
        },
    )
    await call(
        mcp,
        "delete subnet",
        "floci_request",
        {
            "method": "DELETE",
            "path": f"/compute/v1/projects/{client.project}/regions/{client.region}/subnetworks/{subnet}",
        },
    )
    await call(
        mcp,
        "delete network",
        "floci_request",
        {
            "method": "DELETE",
            "path": f"/compute/v1/projects/{client.project}/global/networks/{net}",
        },
    )
    await call(mcp, "delete secret", "secrets_delete", {"secret_id": secret})
    await call(
        mcp,
        "delete service account",
        "iam_delete_service_account",
        {"account": sa_id},
    )
    await call(
        mcp,
        "delete dataset",
        "bq_delete_dataset",
        {"dataset_id": dataset, "delete_contents": True},
    )
    await call(
        mcp, "delete bucket", "storage_delete_bucket", {"bucket": bucket, "force": True}
    )
    await call(
        mcp, "delete subscription", "pubsub_delete_subscription", {"subscription": sub}
    )
    await call(mcp, "delete topic", "pubsub_delete_topic", {"topic": topic})


async def main() -> int:
    mcp = build_server()

    print("\n== health ==")
    health = await call(mcp, "floci_health", "floci_health")
    if not health or not health.get("emulator_reachable"):
        print("\nEmulator unreachable. Start it with: docker compose up -d")
        await client.aclose()
        return 1
    await call(mcp, "floci_list_projects", "floci_list_projects")

    try:
        await run_checks(mcp)
    except Exception as exc:  # noqa: BLE001 - report, then always tear down
        failed.append(("unhandled exception mid-run", f"{type(exc).__name__}: {exc}"))
        print(f"\n!! aborted: {type(exc).__name__}: {exc}")
    finally:
        try:
            await teardown(mcp)
        except Exception as exc:  # noqa: BLE001
            failed.append(("teardown", f"{type(exc).__name__}: {exc}"))
            print(f"!! teardown failed: {exc}")
        await client.aclose()

    print("\n" + "=" * 60)
    print(f"passed: {len(passed)}    failed: {len(failed)}")
    if failed:
        print("\nfailures:")
        for label, detail in failed:
            print(f"  - {label}: {detail}")
    print("=" * 60)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
