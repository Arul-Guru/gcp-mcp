"""Cloud Logging entries and sinks."""

from __future__ import annotations

from typing import Any, Literal

from ..client import FlociError, client

READ_ONLY = {"readOnlyHint": True}

Severity = Literal[
    "DEFAULT",
    "DEBUG",
    "INFO",
    "NOTICE",
    "WARNING",
    "ERROR",
    "CRITICAL",
    "ALERT",
    "EMERGENCY",
]


def register(mcp: Any) -> None:
    @mcp.tool(
        name="logging_write",
        description=(
            "Write a log entry. Give either text or a json_payload dict. "
            "The log_name is a short id such as 'my-app'."
        ),
    )
    async def logging_write(
        log_name: str,
        text: str | None = None,
        json_payload: dict[str, Any] | None = None,
        severity: Severity = "INFO",
        labels: dict[str, str] | None = None,
        resource_type: str = "global",
    ) -> Any:
        if text is None and json_payload is None:
            raise FlociError("Give either text or json_payload.")

        entry: dict[str, Any] = {"severity": severity}
        if json_payload is not None:
            entry["jsonPayload"] = json_payload
        else:
            entry["textPayload"] = text
        if labels:
            entry["labels"] = labels

        full_name = (
            log_name
            if log_name.startswith("projects/")
            else f"projects/{client.project}/logs/{log_name}"
        )

        await client.post(
            "/v2/entries:write",
            json={
                "logName": full_name,
                "resource": {"type": resource_type},
                "entries": [entry],
            },
        )
        return {"written": full_name, "severity": severity}

    @mcp.tool(
        name="logging_list",
        description=(
            "Read log entries, newest first. The filter uses Cloud Logging "
            'syntax, for example \'logName="projects/floci-local/logs/my-app"\' '
            'or \'severity>=ERROR\'.'
        ),
        annotations=READ_ONLY,
    )
    async def logging_list(
        filter: str | None = None,
        limit: int = 20,
        order_by: str = "timestamp desc",
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "resourceNames": [f"projects/{client.project}"],
            "pageSize": limit,
            "orderBy": order_by,
        }
        if filter:
            body["filter"] = filter

        result = await client.post("/v2/entries:list", json=body)
        entries = result.get("entries", []) if isinstance(result, dict) else []
        return {"count": len(entries), "entries": entries}

    @mcp.tool(
        name="logging_list_sinks",
        description="List log export sinks configured in the project.",
        annotations=READ_ONLY,
    )
    async def logging_list_sinks() -> Any:
        return await client.get(f"/v2/projects/{client.project}/sinks")
