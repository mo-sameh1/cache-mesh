from typing import Any

import httpx


class ServiceClientError(Exception):
    """Raised when a service-to-service HTTP call cannot be completed."""


def request_json(
    method: str,
    url: str,
    *,
    timeout_sec: float,
    transport: httpx.BaseTransport | None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        with httpx.Client(timeout=timeout_sec, transport=transport) as client:
            response = client.request(method, url, json=payload)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as exc:
        raise ServiceClientError(f"Remote call failed: {method} {url}") from exc
