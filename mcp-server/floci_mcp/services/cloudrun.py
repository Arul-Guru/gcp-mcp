"""Cloud Run services and jobs (admin API v2).

`gcloud run` cannot drive the emulator: it requests the Knative v1 surface
while floci implements v2 only, and its regional hostname rewriting does not
resolve against localhost. These tools therefore speak v2 REST directly.

Container workloads need the Docker socket mount from docker-compose.yml. A
service can be created successfully and still report a failed
terminalCondition if its image never becomes ready.
"""

from __future__ import annotations

from typing import Any

from ..client import FlociError, client

READ_ONLY = {"readOnlyHint": True}
DESTRUCTIVE = {"destructiveHint": True}


def _parent(region: str | None) -> str:
    return f"/v2/projects/{client.project}/locations/{region or client.region}"


def register(mcp: Any) -> None:
    @mcp.tool(
        name="run_list_services",
        description="List Cloud Run services in a region, including their URLs.",
        annotations=READ_ONLY,
    )
    async def run_list_services(region: str | None = None) -> Any:
        return await client.get(f"{_parent(region)}/services")

    @mcp.tool(
        name="run_get_service",
        description=(
            "Get one Cloud Run service: its reachable `uri`, the ready "
            "revision, and `terminalCondition` (check this if the service is "
            "not responding)."
        ),
        annotations=READ_ONLY,
    )
    async def run_get_service(service: str, region: str | None = None) -> Any:
        return await client.get(f"{_parent(region)}/services/{service}")

    @mcp.tool(
        name="run_deploy_service",
        description=(
            "Deploy a Cloud Run service from a container image, creating it or "
            "updating it in place if it already exists. `env` is a plain "
            "name->value mapping. Returns the service URL once assigned; the "
            "emulator serves it on a *.run.localhost.floci.io host that "
            "resolves to loopback."
        ),
    )
    async def run_deploy_service(
        service: str,
        image: str,
        env: dict[str, str] | None = None,
        port: int | None = None,
        cpu: str | None = None,
        memory: str | None = None,
        args: list[str] | None = None,
        region: str | None = None,
    ) -> dict[str, Any]:
        container: dict[str, Any] = {"image": image}
        if env:
            container["env"] = [{"name": k, "value": v} for k, v in env.items()]
        if port:
            container["ports"] = [{"containerPort": port}]
        if args:
            container["args"] = args
        limits = {}
        if cpu:
            limits["cpu"] = cpu
        if memory:
            limits["memory"] = memory
        if limits:
            container["resources"] = {"limits": limits}

        body = {"template": {"containers": [container]}}
        parent = _parent(region)

        existing = True
        try:
            await client.get(f"{parent}/services/{service}")
        except FlociError:
            existing = False

        if existing:
            action = "updated"
            result = await client.patch(f"{parent}/services/{service}", json=body)
        else:
            action = "created"
            result = await client.post(
                f"{parent}/services", params={"serviceId": service}, json=body
            )

        # The create/patch response may be a long-running operation, so read
        # the service back for the assigned URL.
        uri = None
        condition = None
        try:
            svc = await client.get(f"{parent}/services/{service}")
            uri = svc.get("uri")
            condition = svc.get("terminalCondition")
        except FlociError:
            pass

        return {
            "service": service,
            "action": action,
            "image": image,
            "uri": uri,
            "terminal_condition": condition,
            "response": result,
        }

    @mcp.tool(
        name="run_delete_service",
        description=(
            "Delete a Cloud Run service. Destructive. This returns a "
            "long-running operation and the service is torn down "
            "asynchronously, so it may still appear in run_list_services for a "
            "few seconds afterwards."
        ),
        annotations=DESTRUCTIVE,
    )
    async def run_delete_service(service: str, region: str | None = None) -> Any:
        client.guard_destructive(f"delete Cloud Run service {service}")
        result = await client.delete(f"{_parent(region)}/services/{service}")
        return {"deleted": service, "response": result}

    @mcp.tool(
        name="run_list_jobs",
        description="List Cloud Run jobs in a region.",
        annotations=READ_ONLY,
    )
    async def run_list_jobs(region: str | None = None) -> Any:
        return await client.get(f"{_parent(region)}/jobs")

    @mcp.tool(
        name="run_create_job",
        description=(
            "Create a Cloud Run job from a container image. Use `run_execute_job` "
            "to run it. `task_count` sets how many tasks each execution runs."
        ),
    )
    async def run_create_job(
        job: str,
        image: str,
        env: dict[str, str] | None = None,
        args: list[str] | None = None,
        task_count: int = 1,
        max_retries: int = 3,
        region: str | None = None,
    ) -> Any:
        container: dict[str, Any] = {"image": image}
        if env:
            container["env"] = [{"name": k, "value": v} for k, v in env.items()]
        if args:
            container["args"] = args
        body = {
            "template": {
                "taskCount": task_count,
                "template": {"containers": [container], "maxRetries": max_retries},
            }
        }
        return await client.post(
            f"{_parent(region)}/jobs", params={"jobId": job}, json=body
        )

    @mcp.tool(
        name="run_execute_job",
        description="Trigger an execution of an existing Cloud Run job.",
    )
    async def run_execute_job(job: str, region: str | None = None) -> Any:
        return await client.post(f"{_parent(region)}/jobs/{job}:run", json={})

    @mcp.tool(
        name="run_delete_job",
        description="Delete a Cloud Run job. Destructive.",
        annotations=DESTRUCTIVE,
    )
    async def run_delete_job(job: str, region: str | None = None) -> Any:
        client.guard_destructive(f"delete Cloud Run job {job}")
        result = await client.delete(f"{_parent(region)}/jobs/{job}")
        return {"deleted": job, "response": result}
