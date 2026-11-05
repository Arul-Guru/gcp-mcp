"""Health, project inspection, and the generic REST escape hatch."""

from __future__ import annotations

from typing import Any, Literal

from ..client import FlociError, client

READ_ONLY = {"readOnlyHint": True}


def register(mcp: Any) -> None:
    @mcp.tool(
        name="floci_health",
        description=(
            "Check that the floci-gcp emulator is reachable and report the "
            "endpoint, project, and a per-service availability summary. Run "
            "this first when anything behaves unexpectedly."
        ),
        annotations=READ_ONLY,
    )
    async def floci_health() -> dict[str, Any]:
        probes: dict[str, str] = {}
        checks = {
            "pubsub": f"/v1/projects/{client.project}/topics",
            "storage": "/storage/v1/b",
            "bigquery": f"/bigquery/v2/projects/{client.project}/datasets",
            "cloudrun": f"/v2/projects/{client.project}/locations/{client.region}/services",
            "secretmanager": f"/v1/projects/{client.project}/secrets",
            "iam": f"/v1/projects/{client.project}/serviceAccounts",
            "compute": f"/compute/v1/projects/{client.project}/global/networks",
            "scheduler": f"/v1/projects/{client.project}/locations/{client.region}/jobs",
            "logging": f"/v2/projects/{client.project}/sinks",
        }
        reachable = True
        for name, path in checks.items():
            params = {"project": client.project} if name == "storage" else None
            try:
                await client.get(path, params=params)
                probes[name] = "ok"
            except FlociError as exc:
                probes[name] = f"error: {str(exc).splitlines()[0]}"
                if "Cannot reach" in str(exc):
                    reachable = False

        return {
            "endpoint": client.endpoint,
            "project": client.project,
            "default_region": client.region,
            "default_zone": client.zone,
            "emulator_reachable": reachable,
            "services": probes,
        }

    @mcp.tool(
        name="floci_list_projects",
        description="List projects known to the emulator's Resource Manager.",
        annotations=READ_ONLY,
    )
    async def floci_list_projects() -> Any:
        return await client.get("/v1/projects")

    @mcp.tool(
        name="floci_request",
        description=(
            "Escape hatch: send an arbitrary REST request to the emulator for "
            "any API the typed tools do not cover (KMS, GKE, Cloud SQL, "
            "Managed Kafka, Cloud Functions, Eventarc, Monitoring, Datastore, "
            "Firestore, or newer surfaces).\n\n"
            "`path` is relative to the emulator root and may include a query "
            "string. Useful path prefixes: '/v1/projects/{p}/...' (Pub/Sub, "
            "Secret Manager, IAM, Scheduler, KMS, GKE), "
            "'/v2/projects/{p}/locations/{region}/...' (Cloud Run, Functions), "
            "'/storage/v1/...', '/bigquery/v2/...', '/compute/v1/...', "
            "'/sql/v1beta4/...', '/v3/projects/{p}/...' (Monitoring). "
            "Use the literal string '{project}' and it is substituted for you."
        ),
        annotations={"destructiveHint": True},
    )
    async def floci_request(
        path: str,
        method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = "GET",
        body: dict[str, Any] | None = None,
    ) -> Any:
        if method != "GET":
            client.guard_destructive(f"send a {method} request")
        resolved = path.replace("{project}", client.project).replace(
            "{region}", client.region
        )
        return await client.request(method, resolved, json=body)
