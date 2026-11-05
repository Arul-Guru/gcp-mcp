"""Secret Manager secrets and versions."""

from __future__ import annotations

from typing import Any

from ..client import b64_decode_text, b64_encode, client

READ_ONLY = {"readOnlyHint": True}
DESTRUCTIVE = {"destructiveHint": True}


def _base() -> str:
    return f"/v1/projects/{client.project}"


def register(mcp: Any) -> None:
    @mcp.tool(
        name="secrets_list",
        description="List Secret Manager secrets in the project.",
        annotations=READ_ONLY,
    )
    async def secrets_list() -> Any:
        return await client.get(f"{_base()}/secrets")

    @mcp.tool(
        name="secrets_create",
        description=(
            "Create a secret container with automatic replication. This holds "
            "no data; add a value with secrets_add_version."
        ),
        annotations={"idempotentHint": True},
    )
    async def secrets_create(
        secret_id: str, labels: dict[str, str] | None = None
    ) -> Any:
        body: dict[str, Any] = {"replication": {"automatic": {}}}
        if labels:
            body["labels"] = labels
        return await client.post(
            f"{_base()}/secrets", params={"secretId": secret_id}, json=body
        )

    @mcp.tool(
        name="secrets_list_versions",
        description="List the versions of a secret.",
        annotations=READ_ONLY,
    )
    async def secrets_list_versions(secret_id: str) -> Any:
        return await client.get(f"{_base()}/secrets/{secret_id}/versions")

    @mcp.tool(
        name="secrets_add_version",
        description=(
            "Add a new version holding the given plain-text payload; encoding "
            "is handled for you. Each call creates a new version and 'latest' "
            "moves to it."
        ),
    )
    async def secrets_add_version(secret_id: str, payload: str) -> Any:
        return await client.post(
            f"{_base()}/secrets/{secret_id}:addVersion",
            json={"payload": {"data": b64_encode(payload)}},
        )

    @mcp.tool(
        name="secrets_access",
        description=(
            "Read a secret's value, decoded to text. The version accepts "
            "'latest' or a version number."
        ),
        annotations=READ_ONLY,
    )
    async def secrets_access(
        secret_id: str, version: str = "latest"
    ) -> dict[str, Any]:
        result = await client.get(
            f"{_base()}/secrets/{secret_id}/versions/{version}:access"
        )
        return {
            "secret": secret_id,
            "version": result.get("name", version),
            "value": b64_decode_text((result.get("payload") or {}).get("data")),
        }

    @mcp.tool(
        name="secrets_delete",
        description="Delete a secret and every version it holds. Destructive.",
        annotations=DESTRUCTIVE,
    )
    async def secrets_delete(secret_id: str) -> Any:
        client.guard_destructive(f"delete secret {secret_id}")
        await client.delete(f"{_base()}/secrets/{secret_id}")
        return {"deleted": secret_id}
