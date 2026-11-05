"""Thin async REST client for the floci-gcp emulator.

Everything goes over plain REST rather than the gcloud CLI. The repository's
labs/README.md documents several services where gcloud cannot reach the
emulator at all (Cloud Run's Knative surface, Cloud Tasks, Cloud Functions,
`bq ls`) while REST works fine, so REST is both the broader and the more
predictable surface.

No credentials are involved: the emulator accepts any caller.
"""

from __future__ import annotations

import base64
import json as jsonlib
from typing import Any, Mapping, Sequence
from urllib.parse import quote

import httpx
from mcp.server.mcpserver.exceptions import ToolError

from .config import SETTINGS


class FlociError(ToolError):
    """An emulator call failed, or the emulator is unreachable.

    Deriving from ToolError matters: the MCP SDK forwards a ToolError's message
    to the caller, while any other exception is treated as a server crash and
    its text is withheld. The HTTP status and response body are the whole
    diagnostic value here, so they have to reach the model.
    """


_MAX_ERROR_BODY = 1200


def _describe_failure(response: httpx.Response) -> str:
    body = response.text or "<empty body>"
    if len(body) > _MAX_ERROR_BODY:
        body = body[:_MAX_ERROR_BODY] + " ...[truncated]"
    return (
        f"{response.request.method} {response.request.url} "
        f"-> HTTP {response.status_code}\n{body}"
    )


class FlociClient:
    """Issues requests against the emulator and normalises the responses."""

    def __init__(self) -> None:
        self._settings = SETTINGS
        self._client: httpx.AsyncClient | None = None

    # -- lifecycle ---------------------------------------------------------
    async def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._settings.endpoint,
                timeout=self._settings.timeout,
                follow_redirects=True,
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # -- settings passthrough ---------------------------------------------
    @property
    def project(self) -> str:
        return self._settings.project

    @property
    def region(self) -> str:
        return self._settings.region

    @property
    def zone(self) -> str:
        return self._settings.zone

    @property
    def endpoint(self) -> str:
        return self._settings.endpoint

    def guard_destructive(self, what: str) -> None:
        """Raise unless destructive calls are enabled."""
        if not self._settings.allow_destructive:
            raise FlociError(
                f"Refusing to {what}: this server is running read-only "
                "(FLOCI_GCP_ALLOW_DESTRUCTIVE is disabled)."
            )

    # -- core request ------------------------------------------------------
    async def request(
        self,
        method: str,
        path: str,
        *,
        json: Any | None = None,
        params: Mapping[str, Any] | None = None,
        content: bytes | str | None = None,
        headers: Mapping[str, str] | None = None,
        raw: bool = False,
    ) -> Any:
        """Call the emulator and return parsed JSON (or text/bytes when raw).

        Raises FlociError on a non-2xx response or a transport failure.
        """
        http = await self._http()
        clean_params = (
            {k: v for k, v in params.items() if v is not None} if params else None
        )
        try:
            response = await http.request(
                method.upper(),
                path if path.startswith("/") else f"/{path}",
                json=json,
                params=clean_params,
                content=content,
                headers=dict(headers or {}),
            )
        except httpx.RequestError as exc:
            raise FlociError(
                f"Cannot reach the floci-gcp emulator at {self._settings.endpoint} "
                f"({exc.__class__.__name__}: {exc}).\n"
                "Start it with: docker compose up -d"
            ) from exc

        if response.status_code >= 400:
            raise FlociError(_describe_failure(response))

        if raw:
            return response.content

        if not response.content:
            return {}

        try:
            return response.json()
        except (ValueError, jsonlib.JSONDecodeError):
            return {"_raw": response.text}

    # -- convenience wrappers ---------------------------------------------
    async def get(self, path: str, **kw: Any) -> Any:
        return await self.request("GET", path, **kw)

    async def post(self, path: str, **kw: Any) -> Any:
        return await self.request("POST", path, **kw)

    async def put(self, path: str, **kw: Any) -> Any:
        return await self.request("PUT", path, **kw)

    async def patch(self, path: str, **kw: Any) -> Any:
        return await self.request("PATCH", path, **kw)

    async def delete(self, path: str, **kw: Any) -> Any:
        return await self.request("DELETE", path, **kw)


# Single shared client for the server process.
client = FlociClient()


# -- small shared helpers -------------------------------------------------
def b64_encode(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def b64_decode_text(payload: str | None) -> str | None:
    """Decode a base64 payload to text, falling back to a marker for binary."""
    if payload is None:
        return None
    try:
        return base64.b64decode(payload).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return "<binary data; not valid UTF-8>"


def path_segment(value: str) -> str:
    """URL-encode a single path segment, escaping '/' as %2F.

    GCS object names routinely contain slashes and must arrive as one segment.
    """
    return quote(value, safe="")


def flatten_bq_rows(
    schema: Mapping[str, Any] | None, rows: Sequence[Mapping[str, Any]] | None
) -> list[dict[str, Any]]:
    """Turn BigQuery's {"f":[{"v":...}]} rows into plain dicts."""
    if not rows:
        return []
    fields = [f.get("name", f"f{i}") for i, f in enumerate((schema or {}).get("fields", []))]
    out: list[dict[str, Any]] = []
    for row in rows:
        values = [cell.get("v") for cell in row.get("f", [])]
        if fields:
            out.append(dict(zip(fields, values)))
        else:
            out.append({f"f{i}": v for i, v in enumerate(values)})
    return out
