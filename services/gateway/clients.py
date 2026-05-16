from typing import Any

import httpx

from shared.http_client import request_json


class NameServiceClient:
    def __init__(self, base_url: str, timeout_sec: float, transport: httpx.BaseTransport | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_sec = timeout_sec
        self.transport = transport

    def list_members(self) -> dict[str, Any]:
        return request_json(
            "GET",
            f"{self.base_url}/members",
            timeout_sec=self.timeout_sec,
            transport=self.transport,
        )


class ReplicaClient:
    def __init__(self, timeout_sec: float, transport: httpx.BaseTransport | None = None) -> None:
        self.timeout_sec = timeout_sec
        self.transport = transport

    def read_cache(self, replica_url: str, payload: dict[str, Any]) -> dict[str, Any]:
        return request_json(
            "POST",
            f"{replica_url.rstrip('/')}/cache/read",
            payload=payload,
            timeout_sec=self.timeout_sec,
            transport=self.transport,
        )

    def write_cache(self, replica_url: str, payload: dict[str, Any]) -> dict[str, Any]:
        return request_json(
            "POST",
            f"{replica_url.rstrip('/')}/cache/write",
            payload=payload,
            timeout_sec=self.timeout_sec,
            transport=self.transport,
        )

    def arm_fault(self, replica_url: str, payload: dict[str, Any]) -> dict[str, Any]:
        return request_json(
            "POST",
            f"{replica_url.rstrip('/')}/admin/faults",
            payload=payload,
            timeout_sec=self.timeout_sec,
            transport=self.transport,
        )


class InferenceClient:
    def __init__(self, base_url: str, timeout_sec: float, transport: httpx.BaseTransport | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_sec = timeout_sec
        self.transport = transport

    def infer(self, payload: dict[str, Any]) -> dict[str, Any]:
        return request_json(
            "POST",
            f"{self.base_url}/infer",
            payload=payload,
            timeout_sec=self.timeout_sec,
            transport=self.transport,
        )
