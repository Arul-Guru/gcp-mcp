"""Pub/Sub topics, subscriptions, publish and pull."""

from __future__ import annotations

from typing import Any

from ..client import b64_decode_text, b64_encode, client

READ_ONLY = {"readOnlyHint": True}
DESTRUCTIVE = {"destructiveHint": True}


def _topic_path(topic: str) -> str:
    """Accept either a bare id or a full projects/.../topics/... name."""
    if topic.startswith("projects/"):
        return topic
    return f"projects/{client.project}/topics/{topic}"


def _sub_path(subscription: str) -> str:
    if subscription.startswith("projects/"):
        return subscription
    return f"projects/{client.project}/subscriptions/{subscription}"


def register(mcp: Any) -> None:
    @mcp.tool(
        name="pubsub_list_topics",
        description="List all Pub/Sub topics in the project.",
        annotations=READ_ONLY,
    )
    async def pubsub_list_topics() -> Any:
        return await client.get(f"/v1/projects/{client.project}/topics")

    @mcp.tool(
        name="pubsub_create_topic",
        description="Create a Pub/Sub topic. `topic` is a short id, e.g. 'orders'.",
        annotations={"idempotentHint": True},
    )
    async def pubsub_create_topic(topic: str, labels: dict[str, str] | None = None) -> Any:
        body: dict[str, Any] = {}
        if labels:
            body["labels"] = labels
        return await client.put(f"/v1/{_topic_path(topic)}", json=body)

    @mcp.tool(
        name="pubsub_delete_topic",
        description="Delete a Pub/Sub topic. Destructive: its messages are discarded.",
        annotations=DESTRUCTIVE,
    )
    async def pubsub_delete_topic(topic: str) -> Any:
        client.guard_destructive(f"delete topic {topic}")
        await client.delete(f"/v1/{_topic_path(topic)}")
        return {"deleted": _topic_path(topic)}

    @mcp.tool(
        name="pubsub_publish",
        description=(
            "Publish one or more messages to a topic. Pass plain text in "
            "`messages`; base64 encoding is handled for you. `attributes` are "
            "applied to every message in the call."
        ),
    )
    async def pubsub_publish(
        topic: str,
        messages: list[str],
        attributes: dict[str, str] | None = None,
    ) -> Any:
        payload = {
            "messages": [
                {
                    "data": b64_encode(text),
                    **({"attributes": attributes} if attributes else {}),
                }
                for text in messages
            ]
        }
        return await client.post(f"/v1/{_topic_path(topic)}:publish", json=payload)

    @mcp.tool(
        name="pubsub_list_subscriptions",
        description=(
            "List subscriptions in the project, optionally only those attached "
            "to `topic`. (The emulator does not serve the "
            "topics.list-subscriptions endpoint, so this filters client-side.)"
        ),
        annotations=READ_ONLY,
    )
    async def pubsub_list_subscriptions(topic: str | None = None) -> Any:
        result = await client.get(f"/v1/projects/{client.project}/subscriptions")
        subs = result.get("subscriptions", []) if isinstance(result, dict) else []
        if topic:
            wanted = _topic_path(topic)
            subs = [s for s in subs if s.get("topic") == wanted]
        return {"subscriptions": subs}

    @mcp.tool(
        name="pubsub_create_subscription",
        description=(
            "Create a subscription on a topic. Omit `push_endpoint` for a pull "
            "subscription. Set `dead_letter_topic` plus `max_delivery_attempts` "
            "to attach a dead-letter policy."
        ),
        annotations={"idempotentHint": True},
    )
    async def pubsub_create_subscription(
        subscription: str,
        topic: str,
        ack_deadline_seconds: int = 10,
        push_endpoint: str | None = None,
        dead_letter_topic: str | None = None,
        max_delivery_attempts: int = 5,
    ) -> Any:
        body: dict[str, Any] = {
            "topic": _topic_path(topic),
            "ackDeadlineSeconds": ack_deadline_seconds,
        }
        if push_endpoint:
            body["pushConfig"] = {"pushEndpoint": push_endpoint}
        if dead_letter_topic:
            body["deadLetterPolicy"] = {
                "deadLetterTopic": _topic_path(dead_letter_topic),
                "maxDeliveryAttempts": max_delivery_attempts,
            }
        return await client.put(f"/v1/{_sub_path(subscription)}", json=body)

    @mcp.tool(
        name="pubsub_delete_subscription",
        description="Delete a subscription. Destructive: undelivered messages are lost.",
        annotations=DESTRUCTIVE,
    )
    async def pubsub_delete_subscription(subscription: str) -> Any:
        client.guard_destructive(f"delete subscription {subscription}")
        await client.delete(f"/v1/{_sub_path(subscription)}")
        return {"deleted": _sub_path(subscription)}

    @mcp.tool(
        name="pubsub_pull",
        description=(
            "Pull messages from a pull subscription and return their decoded "
            "text. With `auto_ack` (the default) the messages are acknowledged, "
            "so they will not be redelivered; set it false to peek at them."
        ),
    )
    async def pubsub_pull(
        subscription: str,
        max_messages: int = 10,
        auto_ack: bool = True,
    ) -> dict[str, Any]:
        sub = _sub_path(subscription)
        result = await client.post(
            f"/v1/{sub}:pull",
            json={"maxMessages": max_messages, "returnImmediately": True},
        )
        received = result.get("receivedMessages", []) if isinstance(result, dict) else []

        messages = []
        ack_ids = []
        for item in received:
            msg = item.get("message", {})
            if item.get("ackId"):
                ack_ids.append(item["ackId"])
            messages.append(
                {
                    "messageId": msg.get("messageId"),
                    "data": b64_decode_text(msg.get("data")),
                    "attributes": msg.get("attributes", {}),
                    "publishTime": msg.get("publishTime"),
                }
            )

        acked = False
        if auto_ack and ack_ids:
            await client.post(f"/v1/{sub}:acknowledge", json={"ackIds": ack_ids})
            acked = True

        return {
            "subscription": sub,
            "count": len(messages),
            "acknowledged": acked,
            "messages": messages,
        }
