from typing import Any

import httpx

from shared.http_client import request_json


class NameServiceClientError(Exception):
    """Raised when the replica cannot complete a membership call."""


class ReplicaPeerClientError(Exception):
    """Raised when a replica cannot coordinate with a peer."""


class NameServiceClient:
    def __init__(
        self,
        base_url: str,
        timeout_sec: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=timeout_sec, transport=transport)

    async def register(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request_json("POST", f"{self.base_url}/register", payload=payload)

    async def heartbeat(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request_json("POST", f"{self.base_url}/heartbeat", payload=payload)

    async def close(self) -> None:
        await self._client.aclose()

    async def _request_json(
        self,
        method: str,
        url: str,
        *,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            response = await self._client.request(method, url, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise NameServiceClientError(f"Remote call failed: {method} {url}") from exc


class ReplicaPeerClient:
    def __init__(
        self,
        timeout_sec: float,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.timeout_sec = timeout_sec
        self.transport = transport

    def request_token(self, replica_url: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", f"{replica_url.rstrip('/')}/internal/mutex/request-token", payload)

    def transfer_token(self, replica_url: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", f"{replica_url.rstrip('/')}/internal/mutex/transfer-token", payload)

    def mark_write_started(self, replica_url: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", f"{replica_url.rstrip('/')}/internal/locks/write-started", payload)

    def replicate_write(self, replica_url: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", f"{replica_url.rstrip('/')}/internal/cache/replicate", payload)

    def mark_write_finished(self, replica_url: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", f"{replica_url.rstrip('/')}/internal/locks/write-finished", payload)

    def _request(self, method: str, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return request_json(
                method,
                url,
                timeout_sec=self.timeout_sec,
                transport=self.transport,
                payload=payload,
            )
        except Exception as exc:
            raise ReplicaPeerClientError(f"Remote replica call failed: {method} {url}") from exc
