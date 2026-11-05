"""Entry point: run the floci-gcp MCP server over stdio."""

from __future__ import annotations

import sys

from .server import build_server


def main() -> None:
    # MCP speaks JSON-RPC over stdout, so anything we want to say goes to
    # stderr or it corrupts the protocol stream.
    print("floci-gcp MCP server starting on stdio", file=sys.stderr)
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()
