"""Protocol test: launch the server as a subprocess and speak MCP over stdio.

This is the path Claude Code uses, so it verifies the real handshake rather
than calling the tool functions in-process:

    .venv/Scripts/python.exe tests/stdio_test.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]


async def main() -> int:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "floci_mcp"],
        cwd=str(ROOT),
        env=None,
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print(f"server      : {init.server_info.name} v{init.server_info.version}")
            print(f"instructions: {len(init.instructions or '')} chars")

            tools = (await session.list_tools()).tools
            print(f"tools       : {len(tools)}")

            # Exercise a read, a write/read round-trip, and an error, over the wire.
            health = await session.call_tool("floci_health", {})
            payload = json.loads(health.content[0].text)
            print(f"health      : reachable={payload['emulator_reachable']}")
            ok = [k for k, v in payload["services"].items() if v == "ok"]
            print(f"             {len(ok)}/{len(payload['services'])} services ok")

            topic = "stdio-protocol-check"
            await session.call_tool("pubsub_create_topic", {"topic": topic})
            listed = json.loads(
                (await session.call_tool("pubsub_list_topics", {})).content[0].text
            )
            names = [t["name"].split("/")[-1] for t in listed.get("topics", [])]
            created = topic in names
            print(f"write path  : topic created over stdio = {created}")

            err = await session.call_tool(
                "bq_query", {"sql": "SELECT * FROM nonexistent_dataset.nope"}
            )
            detail = err.content[0].text if err.content else ""
            print(f"error path  : is_error={err.is_error}")
            print(f"             message reaches client = {'404' in detail or 'not' in detail.lower()}")

            await session.call_tool("pubsub_delete_topic", {"topic": topic})
            print("cleanup     : topic deleted")

            failures = []
            if not payload["emulator_reachable"]:
                failures.append("emulator unreachable")
            if len(tools) < 50:
                failures.append(f"only {len(tools)} tools registered")
            if not created:
                failures.append("topic was not created over stdio")
            if not err.is_error:
                failures.append("a failing query did not report is_error")

            print()
            if failures:
                for f in failures:
                    print(f"FAIL: {f}")
                return 1
            print("stdio protocol check passed")
            return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
