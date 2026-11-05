"""Compute Engine networks, disks and instances.

Two emulator behaviours shape these tools:

* The public image catalog is empty, so the usual --image-family boot path
  fails. Create a disk first and attach it as the boot disk.
* There is no default VPC in a fresh emulator, and only six machine types are
  stocked: c3-standard-4, e2-standard-2, g2-standard-4, g2-standard-8,
  n2-standard-4, n2-standard-8. There is no e2-micro.
"""

from __future__ import annotations

from typing import Any, Literal

from ..client import FlociError, client

READ_ONLY = {"readOnlyHint": True}
DESTRUCTIVE = {"destructiveHint": True}

MACHINE_TYPES = (
    "c3-standard-4",
    "e2-standard-2",
    "g2-standard-4",
    "g2-standard-8",
    "n2-standard-4",
    "n2-standard-8",
)


def _base() -> str:
    return f"/compute/v1/projects/{client.project}"


def register(mcp: Any) -> None:
    @mcp.tool(
        name="compute_list_instances",
        description="List Compute Engine VM instances in a zone.",
        annotations=READ_ONLY,
    )
    async def compute_list_instances(zone: str | None = None) -> Any:
        return await client.get(f"{_base()}/zones/{zone or client.zone}/instances")

    @mcp.tool(
        name="compute_list_networks",
        description="List VPC networks in the project.",
        annotations=READ_ONLY,
    )
    async def compute_list_networks() -> Any:
        return await client.get(f"{_base()}/global/networks")

    @mcp.tool(
        name="compute_create_network",
        description=(
            "Create a VPC network. With auto_create_subnetworks false (the "
            "default) you must also create a subnet before launching an "
            "instance."
        ),
    )
    async def compute_create_network(
        name: str, auto_create_subnetworks: bool = False
    ) -> Any:
        return await client.post(
            f"{_base()}/global/networks",
            json={
                "name": name,
                "autoCreateSubnetworks": auto_create_subnetworks,
            },
        )

    @mcp.tool(
        name="compute_create_subnet",
        description=(
            "Create a subnet in a region, for example with ip_cidr_range "
            "'10.0.0.0/24'."
        ),
    )
    async def compute_create_subnet(
        name: str,
        network: str,
        ip_cidr_range: str = "10.0.0.0/24",
        region: str | None = None,
    ) -> Any:
        target = region or client.region
        return await client.post(
            f"{_base()}/regions/{target}/subnetworks",
            json={
                "name": name,
                "network": f"projects/{client.project}/global/networks/{network}",
                "ipCidrRange": ip_cidr_range,
            },
        )

    @mcp.tool(
        name="compute_create_disk",
        description=(
            "Create a persistent disk. Needed before creating an instance, "
            "because the emulator serves no public boot images."
        ),
    )
    async def compute_create_disk(
        name: str,
        size_gb: int = 10,
        disk_type: str = "pd-standard",
        zone: str | None = None,
    ) -> Any:
        target = zone or client.zone
        return await client.post(
            f"{_base()}/zones/{target}/disks",
            json={
                "name": name,
                "sizeGb": str(size_gb),
                "type": f"projects/{client.project}/zones/{target}/diskTypes/{disk_type}",
            },
        )

    @mcp.tool(
        name="compute_list_disks",
        description="List persistent disks in a zone.",
        annotations=READ_ONLY,
    )
    async def compute_list_disks(zone: str | None = None) -> Any:
        return await client.get(f"{_base()}/zones/{zone or client.zone}/disks")

    @mcp.tool(
        name="compute_create_instance",
        description=(
            "Create a VM instance attaching an existing disk as its boot disk "
            "(create one with compute_create_disk first). The emulator requires "
            "a subnetwork: if subnet is omitted, the first subnet on the given "
            "network in that region is used. Stocked machine types: "
            "c3-standard-4, e2-standard-2, g2-standard-4, g2-standard-8, "
            "n2-standard-4, n2-standard-8."
        ),
    )
    async def compute_create_instance(
        name: str,
        boot_disk: str,
        machine_type: str = "e2-standard-2",
        network: str = "default",
        subnet: str | None = None,
        labels: dict[str, str] | None = None,
        zone: str | None = None,
    ) -> Any:
        target = zone or client.zone
        region = target.rsplit("-", 1)[0]

        # The emulator rejects an instance with no subnetwork, so find one on
        # this network rather than failing with "Missing or invalid subnetwork".
        if not subnet:
            listing = await client.get(f"{_base()}/regions/{region}/subnetworks")
            for item in (listing or {}).get("items", []):
                # The network field comes back as a full googleapis URL.
                if (item.get("network") or "").rstrip("/").endswith(f"/{network}"):
                    subnet = item.get("name")
                    break
            if not subnet:
                raise FlociError(
                    f"No subnet exists on network '{network}' in {region}, and "
                    "the emulator requires one. Create it first with "
                    f"compute_create_subnet(name=..., network='{network}')."
                )

        interface: dict[str, Any] = {
            "network": f"projects/{client.project}/global/networks/{network}",
            "subnetwork": (
                f"projects/{client.project}/regions/{region}/subnetworks/{subnet}"
            ),
        }

        body: dict[str, Any] = {
            "name": name,
            "machineType": (
                f"projects/{client.project}/zones/{target}/machineTypes/{machine_type}"
            ),
            "disks": [
                {
                    "boot": True,
                    "autoDelete": False,
                    "source": (
                        f"projects/{client.project}/zones/{target}/disks/{boot_disk}"
                    ),
                }
            ],
            "networkInterfaces": [interface],
        }
        if labels:
            body["labels"] = labels

        return await client.post(f"{_base()}/zones/{target}/instances", json=body)

    @mcp.tool(
        name="compute_instance_action",
        description=(
            "Start, stop, reset or delete a VM instance. Deleting is "
            "destructive."
        ),
        annotations=DESTRUCTIVE,
    )
    async def compute_instance_action(
        name: str,
        action: Literal["start", "stop", "reset", "delete"],
        zone: str | None = None,
    ) -> Any:
        target = zone or client.zone
        path = f"{_base()}/zones/{target}/instances/{name}"

        if action == "delete":
            client.guard_destructive(f"delete instance {name}")
            result = await client.delete(path)
        else:
            client.guard_destructive(f"{action} instance {name}")
            result = await client.post(f"{path}/{action}", json={})

        return {"instance": name, "zone": target, "action": action, "response": result}
