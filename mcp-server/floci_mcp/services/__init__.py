"""Tool modules, one per emulated GCP service."""

from . import (
    bigquery,
    cloudrun,
    compute,
    core,
    iam,
    logs,
    pubsub,
    scheduler,
    secrets,
    storage,
)

#: Registered in this order; determines the order tools are listed.
MODULES = [
    core,
    pubsub,
    storage,
    bigquery,
    cloudrun,
    secrets,
    iam,
    compute,
    scheduler,
    logs,
]

__all__ = ["MODULES"]
