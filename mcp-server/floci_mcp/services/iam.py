"""IAM service accounts and project-level policy bindings.

The emulator does not serve the predefined-role catalog (roles.list returns
404), but service accounts and policy bindings both work.
"""

from __future__ import annotations

from typing import Any

from ..client import client

READ_ONLY = {"readOnlyHint": True}
DESTRUCTIVE = {"destructiveHint": True}


def _base() -> str:
    return f"/v1/projects/{client.project}"


def _sa_email(account: str) -> str:
    """Accept a short account id or a full service-account email."""
    if "@" in account:
        return account
    return f"{account}@{client.project}.iam.gserviceaccount.com"


def _qualify(member: str) -> str:
    """Turn a bare account id into a fully qualified IAM member."""
    if ":" in member:
        return member
    return f"serviceAccount:{_sa_email(member)}"


def register(mcp: Any) -> None:
    @mcp.tool(
        name="iam_list_service_accounts",
        description="List service accounts in the project.",
        annotations=READ_ONLY,
    )
    async def iam_list_service_accounts() -> Any:
        return await client.get(f"{_base()}/serviceAccounts")

    @mcp.tool(
        name="iam_create_service_account",
        description=(
            "Create a service account. The account_id is the short name "
            "before the @, for example 'data-loader'."
        ),
        annotations={"idempotentHint": True},
    )
    async def iam_create_service_account(
        account_id: str,
        display_name: str | None = None,
        description: str | None = None,
    ) -> Any:
        sa: dict[str, Any] = {}
        if display_name:
            sa["displayName"] = display_name
        if description:
            sa["description"] = description
        return await client.post(
            f"{_base()}/serviceAccounts",
            json={"accountId": account_id, "serviceAccount": sa},
        )

    @mcp.tool(
        name="iam_delete_service_account",
        description=(
            "Delete a service account, given a short id or full email. "
            "Destructive."
        ),
        annotations=DESTRUCTIVE,
    )
    async def iam_delete_service_account(account: str) -> Any:
        email = _sa_email(account)
        client.guard_destructive(f"delete service account {email}")
        await client.delete(f"{_base()}/serviceAccounts/{email}")
        return {"deleted": email}

    @mcp.tool(
        name="iam_get_policy",
        description="Get the project's IAM policy: its role bindings and etag.",
        annotations=READ_ONLY,
    )
    async def iam_get_policy() -> Any:
        return await client.post(f"{_base()}:getIamPolicy", json={})

    @mcp.tool(
        name="iam_add_binding",
        description=(
            "Grant a role to a member on the project, preserving existing "
            "bindings (read-modify-write). A role looks like "
            "'roles/pubsub.subscriber'. A member may be a bare service-account "
            "id, or fully qualified such as "
            "'serviceAccount:x@p.iam.gserviceaccount.com' or 'user:a@b.c'."
        ),
    )
    async def iam_add_binding(role: str, member: str) -> Any:
        qualified = _qualify(member)
        policy = await client.post(f"{_base()}:getIamPolicy", json={})
        bindings = policy.get("bindings") or []

        for binding in bindings:
            if binding.get("role") == role:
                members = binding.setdefault("members", [])
                if qualified in members:
                    return {
                        "unchanged": True,
                        "role": role,
                        "member": qualified,
                    }
                members.append(qualified)
                break
        else:
            bindings.append({"role": role, "members": [qualified]})

        policy["bindings"] = bindings
        updated = await client.post(
            f"{_base()}:setIamPolicy", json={"policy": policy}
        )
        return {
            "added": {"role": role, "member": qualified},
            "policy": updated,
        }

    @mcp.tool(
        name="iam_remove_binding",
        description="Revoke a role from a member on the project. Destructive.",
        annotations=DESTRUCTIVE,
    )
    async def iam_remove_binding(role: str, member: str) -> Any:
        qualified = _qualify(member)
        client.guard_destructive(f"revoke {role} from {qualified}")

        policy = await client.post(f"{_base()}:getIamPolicy", json={})
        bindings = policy.get("bindings") or []

        changed = False
        for binding in list(bindings):
            if binding.get("role") == role and qualified in binding.get(
                "members", []
            ):
                binding["members"].remove(qualified)
                changed = True
                if not binding["members"]:
                    bindings.remove(binding)

        if not changed:
            return {"unchanged": True, "role": role, "member": qualified}

        policy["bindings"] = bindings
        updated = await client.post(
            f"{_base()}:setIamPolicy", json={"policy": policy}
        )
        return {
            "removed": {"role": role, "member": qualified},
            "policy": updated,
        }
