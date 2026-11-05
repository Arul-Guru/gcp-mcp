"""MCP server definition: builds the server and registers every tool module."""

from __future__ import annotations

import logging

from mcp.server.mcpserver import MCPServer

from . import __version__
from .config import SETTINGS
from .services import MODULES

INSTRUCTIONS = f"""\
These tools drive a local floci-gcp emulator at {SETTINGS.endpoint}, a
stand-in for Google Cloud Platform. Project: {SETTINGS.project}. Default
region {SETTINGS.region}, default zone {SETTINGS.zone}.

This is disposable local state, not real cloud infrastructure, so creating and
deleting resources is cheap and safe. Nothing here touches a real GCP project
and no credentials are involved.

Start with floci_health if anything behaves unexpectedly: it reports whether
the emulator is up and which services answer.

Known emulator limits worth remembering:
  - Cloud Run works over the v2 admin API only. These tools use it; the
    `gcloud run` CLI cannot talk to the emulator at all.
  - A deployed Cloud Run service may report a failed terminalCondition if its
    image never becomes ready; the service object is still created.
  - Compute Engine has no public image catalog and no default VPC. Create a
    disk with compute_create_disk and attach it as the boot disk, and create a
    network and subnet before launching an instance.
  - Only six machine types exist; there is no e2-micro.
  - Secret Manager returns no CRC32C checksum, so some clients report a
    spurious data-integrity warning. The stored value is correct.
  - Cloud Tasks is not implemented at any API version.
  - For any service without a typed tool here (KMS, GKE, Cloud SQL, Managed
    Kafka, Cloud Functions, Eventarc, Monitoring, Firestore, Datastore), use
    floci_request to call its REST surface directly.
"""


def build_server() -> MCPServer:
    # httpx logs every request at INFO, which floods the host's MCP log with a
    # line per emulator call. Warnings and errors still come through.
    logging.getLogger("httpx").setLevel(logging.WARNING)

    mcp = MCPServer(
        name="floci-gcp",
        title="floci-gcp local emulator",
        version=__version__,
        instructions=INSTRUCTIONS,
    )
    for module in MODULES:
        module.register(mcp)
    return mcp
