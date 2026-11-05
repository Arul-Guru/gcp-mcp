"""Runtime configuration, read from the environment.

Defaults match the docker-compose setup in the repository root, so the server
works with no configuration at all.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_ENDPOINT = "http://localhost:4588"
DEFAULT_PROJECT = "floci-local"
DEFAULT_REGION = "us-central1"
DEFAULT_ZONE = "us-central1-a"


@dataclass(frozen=True)
class Settings:
    endpoint: str
    project: str
    region: str
    zone: str
    timeout: float
    allow_destructive: bool

    @classmethod
    def from_env(cls) -> "Settings":
        endpoint = os.environ.get("FLOCI_GCP_ENDPOINT", DEFAULT_ENDPOINT).rstrip("/")
        return cls(
            endpoint=endpoint,
            project=os.environ.get("FLOCI_GCP_PROJECT", DEFAULT_PROJECT),
            region=os.environ.get("FLOCI_GCP_REGION", DEFAULT_REGION),
            zone=os.environ.get("FLOCI_GCP_ZONE", DEFAULT_ZONE),
            timeout=float(os.environ.get("FLOCI_GCP_TIMEOUT", "60")),
            # The emulator is disposable local state, so destructive calls are
            # allowed by default. Set to 0/false to run the server read-only.
            allow_destructive=os.environ.get(
                "FLOCI_GCP_ALLOW_DESTRUCTIVE", "1"
            ).strip().lower()
            not in {"0", "false", "no", "off"},
        )


SETTINGS = Settings.from_env()
