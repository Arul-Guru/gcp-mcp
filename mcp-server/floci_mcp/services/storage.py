"""Cloud Storage buckets and objects."""

from __future__ import annotations

import base64
from typing import Any

from ..client import client, path_segment

READ_ONLY = {"readOnlyHint": True}
DESTRUCTIVE = {"destructiveHint": True}


def _strip_scheme(name: str) -> str:
    """Accept 'gs://bucket' or 'bucket'."""
    return name[5:].split("/", 1)[0] if name.startswith("gs://") else name


def register(mcp: Any) -> None:
    @mcp.tool(
        name="storage_list_buckets",
        description="List Cloud Storage buckets in the project.",
        annotations=READ_ONLY,
    )
    async def storage_list_buckets() -> Any:
        return await client.get("/storage/v1/b", params={"project": client.project})

    @mcp.tool(
        name="storage_create_bucket",
        description="Create a Cloud Storage bucket. `bucket` may be 'name' or 'gs://name'.",
        annotations={"idempotentHint": True},
    )
    async def storage_create_bucket(
        bucket: str,
        location: str = "US",
        storage_class: str = "STANDARD",
    ) -> Any:
        return await client.post(
            "/storage/v1/b",
            params={"project": client.project},
            json={
                "name": _strip_scheme(bucket),
                "location": location,
                "storageClass": storage_class,
            },
        )

    @mcp.tool(
        name="storage_delete_bucket",
        description=(
            "Delete a bucket. Destructive. The API refuses a non-empty bucket; "
            "pass `force` to delete every object in it first."
        ),
        annotations=DESTRUCTIVE,
    )
    async def storage_delete_bucket(bucket: str, force: bool = False) -> Any:
        name = _strip_scheme(bucket)
        client.guard_destructive(f"delete bucket {name}")
        removed = 0
        if force:
            listing = await client.get(f"/storage/v1/b/{path_segment(name)}/o")
            for obj in (listing or {}).get("items", []):
                await client.delete(
                    f"/storage/v1/b/{path_segment(name)}/o/{path_segment(obj['name'])}"
                )
                removed += 1
        await client.delete(f"/storage/v1/b/{path_segment(name)}")
        return {"deleted": name, "objects_removed": removed}

    @mcp.tool(
        name="storage_list_objects",
        description="List objects in a bucket, optionally filtered by key `prefix`.",
        annotations=READ_ONLY,
    )
    async def storage_list_objects(
        bucket: str,
        prefix: str | None = None,
        max_results: int = 100,
    ) -> Any:
        return await client.get(
            f"/storage/v1/b/{path_segment(_strip_scheme(bucket))}/o",
            params={"prefix": prefix, "maxResults": max_results},
        )

    @mcp.tool(
        name="storage_read_object",
        description=(
            "Download an object and return its contents. UTF-8 text is returned "
            "as text; binary data is returned base64-encoded with "
            "`encoding: base64`."
        ),
        annotations=READ_ONLY,
    )
    async def storage_read_object(bucket: str, object_name: str) -> dict[str, Any]:
        raw = await client.get(
            f"/storage/v1/b/{path_segment(_strip_scheme(bucket))}"
            f"/o/{path_segment(object_name)}",
            params={"alt": "media"},
            raw=True,
        )
        try:
            return {
                "bucket": _strip_scheme(bucket),
                "object": object_name,
                "size_bytes": len(raw),
                "encoding": "utf-8",
                "content": raw.decode("utf-8"),
            }
        except UnicodeDecodeError:
            return {
                "bucket": _strip_scheme(bucket),
                "object": object_name,
                "size_bytes": len(raw),
                "encoding": "base64",
                "content": base64.b64encode(raw).decode("ascii"),
            }

    @mcp.tool(
        name="storage_write_object",
        description=(
            "Upload an object from `content`. Set `content_is_base64` to upload "
            "binary data. Overwrites an existing object at the same key."
        ),
    )
    async def storage_write_object(
        bucket: str,
        object_name: str,
        content: str,
        content_type: str = "text/plain",
        content_is_base64: bool = False,
    ) -> Any:
        payload = (
            base64.b64decode(content) if content_is_base64 else content.encode("utf-8")
        )
        return await client.post(
            f"/upload/storage/v1/b/{path_segment(_strip_scheme(bucket))}/o",
            params={"uploadType": "media", "name": object_name},
            content=payload,
            headers={"Content-Type": content_type},
        )

    @mcp.tool(
        name="storage_delete_object",
        description="Delete a single object from a bucket. Destructive.",
        annotations=DESTRUCTIVE,
    )
    async def storage_delete_object(bucket: str, object_name: str) -> Any:
        name = _strip_scheme(bucket)
        client.guard_destructive(f"delete gs://{name}/{object_name}")
        await client.delete(
            f"/storage/v1/b/{path_segment(name)}/o/{path_segment(object_name)}"
        )
        return {"deleted": f"gs://{name}/{object_name}"}
