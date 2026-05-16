from typing import Any

import httpx


class NameServiceClientError(Exception):
    """Raised when the replica cannot complete a membership call."""


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
