import pytest

from services.gateway.clients import GatewayClientError
from services.gateway.service import GatewayService


class FakeNameServiceClient:
    def __init__(self, members: list[dict]) -> None:
        self.members = members

    def list_members(self) -> dict:
        return {"members": self.members}


class FakeReplicaClient:
    def __init__(
        self,
        read_responses: list[dict] | None = None,
        fail_write: bool = False,
        fail_fault: bool = False,
    ) -> None:
        self.read_responses = read_responses or []
        self.fail_write = fail_write
        self.fail_fault = fail_fault
        self.read_urls: list[str] = []
        self.write_urls: list[str] = []
        self.fault_urls: list[str] = []

    def read_cache(self, replica_url: str, payload: dict) -> dict:
        self.read_urls.append(replica_url)
        if not self.read_responses:
            raise GatewayClientError("read failed")
        response = self.read_responses.pop(0)
        if response.get("raise"):
            raise GatewayClientError("read failed")
        return response

    def write_cache(self, replica_url: str, payload: dict) -> dict:
        self.write_urls.append(replica_url)
        if self.fail_write:
            raise GatewayClientError("write failed")
        return {
            "service": "replica",
            "action": "cache.write",
            "status": "placeholder",
            "detail": "stored",
            "stored": True,
            "replica_id": "replica-a",
            "model_id": payload["model_id"],
            "lamport_ts": None,
        }

    def arm_fault(self, replica_url: str, payload: dict) -> dict:
        self.fault_urls.append(replica_url)
        if self.fail_fault:
            raise GatewayClientError("fault failed")
        return {
            "service": "replica",
            "action": "admin.faults",
            "status": "placeholder",
            "detail": "fault armed",
            "accepted": True,
            "target_replica_id": None,
            "active_fault": payload,
        }


class FakeInferenceClient:
    def __init__(self) -> None:
        self.called = False

    def infer(self, payload: dict) -> dict:
        self.called = True
        return {
            "service": "inference-adapter",
            "action": "infer",
            "status": "placeholder",
            "detail": "generated",
            "response_text": "generated answer",
            "model_id": payload["model_id"],
            "provider": "placeholder",
        }


def test_query_cache_returns_replica_hit() -> None:
    replica_client = FakeReplicaClient(
        read_responses=[
            {
                "hit": True,
                "response_text": "cached answer",
                "replica_id": "replica-a",
                "model_id": "demo",
                "score": 0.93,
            }
        ]
    )
    service = GatewayService(
        name_service_client=FakeNameServiceClient([_member("replica-a", 8201)]),
        replica_client=replica_client,
        inference_client=FakeInferenceClient(),
    )

    response = service.query_cache(_query_payload())

    assert response["hit"] is True
    assert response["response_text"] == "cached answer"
    assert response["selected_replica_id"] == "replica-a"
    assert response["score"] == 0.93
    assert response["cache_status"] == "hit"
    assert replica_client.read_urls == ["http://replica-a:8201"]


def test_query_cache_uses_fallback_replica_on_empty_members(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GATEWAY_REPLICA_URLS", "http://replica-a:8201")
    replica_client = FakeReplicaClient(read_responses=[{"hit": False, "model_id": "demo"}])
    inference_client = FakeInferenceClient()
    service = GatewayService(
        name_service_client=FakeNameServiceClient([]),
        replica_client=replica_client,
        inference_client=inference_client,
    )

    response = service.query_cache(_query_payload())

    assert response["hit"] is False
    assert response["response_text"] == "generated answer"
    assert response["selected_replica_id"] == "replica-a"
    assert response["cache_status"] == "miss_generated"
    assert inference_client.called is True
    assert replica_client.write_urls == ["http://replica-a:8201"]


def test_query_cache_reports_write_failure_after_generation() -> None:
    service = GatewayService(
        name_service_client=FakeNameServiceClient([_member("replica-a", 8201)]),
        replica_client=FakeReplicaClient(read_responses=[{"hit": False, "model_id": "demo"}], fail_write=True),
        inference_client=FakeInferenceClient(),
    )

    response = service.query_cache(_query_payload())

    assert response["response_text"] == "generated answer"
    assert response["cache_status"] == "miss_generated_write_failed"


def test_query_cache_returns_unavailable_when_no_replica_can_be_read() -> None:
    service = GatewayService(
        name_service_client=FakeNameServiceClient([_member("replica-a", 8201)]),
        replica_client=FakeReplicaClient(read_responses=[{"raise": True}]),
        inference_client=FakeInferenceClient(),
    )

    response = service.query_cache(_query_payload())

    assert response["status"] == "unavailable"
    assert response["cache_status"] == "replicas_unavailable"
    assert response["selected_replica_id"] is None


def test_write_cache_uses_first_available_replica() -> None:
    service = GatewayService(
        name_service_client=FakeNameServiceClient([_member("replica-a", 8201)]),
        replica_client=FakeReplicaClient(),
        inference_client=FakeInferenceClient(),
    )

    response = service.write_cache({"prompt": "hello", "response_text": "world", "model_id": "demo"})

    assert response["stored"] is True
    assert response["replica_id"] == "replica-a"
    assert response["service"] == "gateway"
    assert response["action"] == "cache.write"


def test_arm_fault_forwards_to_fallback_replica(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GATEWAY_REPLICA_URLS", "http://replica-a:8201")
    replica_client = FakeReplicaClient()
    service = GatewayService(
        name_service_client=FakeNameServiceClient([]),
        replica_client=replica_client,
        inference_client=FakeInferenceClient(),
    )

    response = service.arm_fault("replica-a", _fault_payload())

    assert response["accepted"] is True
    assert response["target_replica_id"] == "replica-a"
    assert replica_client.fault_urls == ["http://replica-a:8201"]


def test_arm_fault_returns_unavailable_for_unknown_replica(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GATEWAY_REPLICA_URLS", "http://replica-a:8201")
    service = GatewayService(
        name_service_client=FakeNameServiceClient([]),
        replica_client=FakeReplicaClient(),
        inference_client=FakeInferenceClient(),
    )

    response = service.arm_fault("replica-z", _fault_payload())

    assert response["accepted"] is False
    assert response["status"] == "unavailable"
    assert response["target_replica_id"] == "replica-z"


def test_arm_fault_returns_unavailable_when_forwarding_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GATEWAY_REPLICA_URLS", "http://replica-a:8201")
    service = GatewayService(
        name_service_client=FakeNameServiceClient([]),
        replica_client=FakeReplicaClient(fail_fault=True),
        inference_client=FakeInferenceClient(),
    )

    response = service.arm_fault("replica-a", _fault_payload())

    assert response["accepted"] is False
    assert response["status"] == "unavailable"
    assert response["target_replica_id"] == "replica-a"


def test_arm_fault_uses_fallback_when_members_do_not_include_target(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GATEWAY_REPLICA_TARGETS", "replica-b=http://replica-b:8202")
    replica_client = FakeReplicaClient()
    service = GatewayService(
        name_service_client=FakeNameServiceClient([_member("replica-a", 8201)]),
        replica_client=replica_client,
        inference_client=FakeInferenceClient(),
    )

    response = service.arm_fault("replica-b", _fault_payload())

    assert response["accepted"] is True
    assert response["target_replica_id"] == "replica-b"
    assert replica_client.fault_urls == ["http://replica-b:8202"]


def test_arm_fault_supports_ip_based_fallback_targets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GATEWAY_REPLICA_TARGETS", "replica-a=http://192.168.1.10:8201")
    replica_client = FakeReplicaClient()
    service = GatewayService(
        name_service_client=FakeNameServiceClient([]),
        replica_client=replica_client,
        inference_client=FakeInferenceClient(),
    )

    response = service.arm_fault("replica-a", _fault_payload())

    assert response["accepted"] is True
    assert response["target_replica_id"] == "replica-a"
    assert replica_client.fault_urls == ["http://192.168.1.10:8201"]


def _member(replica_id: str, port: int) -> dict:
    return {"replica_id": replica_id, "host": replica_id, "port": port, "status": "healthy"}


def _query_payload() -> dict:
    return {"prompt": "hello", "model_id": "demo", "semantic_enabled": True}


def _fault_payload() -> dict:
    return {"mode": "pause_node", "duration_sec": 10, "once": True}
