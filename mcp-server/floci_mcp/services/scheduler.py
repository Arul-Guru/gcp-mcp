"""Cloud Scheduler cron jobs."""

from __future__ import annotations

from typing import Any

from ..client import FlociError, b64_encode, client

READ_ONLY = {"readOnlyHint": True}
DESTRUCTIVE = {"destructiveHint": True}


def _parent(region: str | None) -> str:
    return f"/v1/projects/{client.project}/locations/{region or client.region}"


def register(mcp: Any) -> None:
    @mcp.tool(
        name="scheduler_list_jobs",
        description="List Cloud Scheduler jobs in a region.",
        annotations=READ_ONLY,
    )
    async def scheduler_list_jobs(region: str | None = None) -> Any:
        return await client.get(f"{_parent(region)}/jobs")

    @mcp.tool(
        name="scheduler_create_job",
        description=(
            "Create a cron job with a unix-cron schedule such as '0 2 * * *'. "
            "Give either pubsub_topic (publishing message_body) or http_url "
            "for an HTTP target."
        ),
    )
    async def scheduler_create_job(
        name: str,
        schedule: str,
        pubsub_topic: str | None = None,
        http_url: str | None = None,
        message_body: str = "",
        http_method: str = "POST",
        time_zone: str = "Etc/UTC",
        description: str | None = None,
        region: str | None = None,
    ) -> Any:
        if not pubsub_topic and not http_url:
            raise FlociError("Give either pubsub_topic or http_url.")
        if pubsub_topic and http_url:
            raise FlociError("Give only one of pubsub_topic or http_url.")

        target = region or client.region
        body: dict[str, Any] = {
            "name": f"projects/{client.project}/locations/{target}/jobs/{name}",
            "schedule": schedule,
            "timeZone": time_zone,
        }
        if description:
            body["description"] = description

        if pubsub_topic:
            topic = (
                pubsub_topic
                if pubsub_topic.startswith("projects/")
                else f"projects/{client.project}/topics/{pubsub_topic}"
            )
            pubsub: dict[str, Any] = {"topicName": topic}
            if message_body:
                pubsub["data"] = b64_encode(message_body)
            body["pubsubTarget"] = pubsub
        else:
            http: dict[str, Any] = {"uri": http_url, "httpMethod": http_method}
            if message_body:
                http["body"] = b64_encode(message_body)
            body["httpTarget"] = http

        return await client.post(f"{_parent(region)}/jobs", json=body)

    @mcp.tool(
        name="scheduler_run_job",
        description="Trigger a scheduler job immediately, ignoring its schedule.",
    )
    async def scheduler_run_job(name: str, region: str | None = None) -> Any:
        return await client.post(f"{_parent(region)}/jobs/{name}:run", json={})

    @mcp.tool(
        name="scheduler_delete_job",
        description="Delete a scheduler job. Destructive.",
        annotations=DESTRUCTIVE,
    )
    async def scheduler_delete_job(name: str, region: str | None = None) -> Any:
        client.guard_destructive(f"delete scheduler job {name}")
        await client.delete(f"{_parent(region)}/jobs/{name}")
        return {"deleted": name}
