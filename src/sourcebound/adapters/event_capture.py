from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import uuid
from typing import Any, Mapping

from sourcebound.errors import ConfigurationError

MAX_RESPONSE_BYTES = 4_096


def deliver_event(
    *,
    endpoint: str,
    token_env: str,
    envelope: Mapping[str, Any],
) -> None:
    token = os.environ.get(token_env)
    if not token:
        raise ConfigurationError(
            f"connected feedback token environment variable is unset: {token_env}"
        )
    wire_payload = json.dumps(
        {
            "api_key": token,
            "event": "sourcebound_feedback",
            "distinct_id": envelope["installation_id"],
            "uuid": str(uuid.UUID(hex=envelope["event_id"][:32])),
            "properties": {
                **envelope,
                "$process_person_profile": False,
            },
            "timestamp": envelope["occurred_at"],
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    request = urllib.request.Request(
        endpoint,
        data=wire_payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            response.read(MAX_RESPONSE_BYTES)
            if not 200 <= response.status < 300:
                raise ConfigurationError(
                    f"connected feedback sink returned HTTP {response.status}"
                )
    except (OSError, urllib.error.URLError) as exc:
        raise ConfigurationError("connected feedback delivery failed") from exc
