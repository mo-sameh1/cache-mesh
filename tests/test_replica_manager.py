import time

from fastapi.testclient import TestClient

from services.replica.clients import NameServiceClientError
from services.replica.manager import ReplicaManager
from services.replica.main import create_app as create_replica_app
from services.replica.vector_store import VectorStoreAdapter
from shared.config import ReplicaSettings


class RecordingNameServiceClient:
    def __init__(self, *, fail_heartbeat: bool = False) -> None:
        self.fail_heartbeat = fail_heartbeat
        self.register_calls: list[dict] = []
        self.heartbeat_calls: list[dict] = []
        self.closed = False

    async def register(self, payload: dict) -> dict:
        self.register_calls.append(payload)
        return {"registered": True, "member": payload}

    async def heartbeat(self, payload: dict) -> dict:
        self.heartbeat_calls.append(payload)
        if self.fail_heartbeat:
            raise NameServiceClientError("heartbeat unavailable")
        return {"accepted": True, "member": payload}

    async def close(self) -> None:
        self.closed = True


class NoOpVectorClient:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs

    def get_collections(self) -> dict:
        return {"collections": []}

    def close(self) -> None:
        return None


def test_replica_registers_on_startup() -> None:
    name_service = RecordingNameServiceClient()
    manager = _build_manager(name_service_client=name_service)

    with TestClient(create_replica_app(replica_manager=manager)):
        pass

    assert name_service.register_calls == [
        {"replica_id": "replica-a", "host": "replica-a", "port": 8201}
    ]
    assert name_service.closed is True


def test_replica_heartbeat_failures_are_tolerated() -> None:
    name_service = RecordingNameServiceClient(fail_heartbeat=True)
    manager = _build_manager(
        name_service_client=name_service,
        settings=ReplicaSettings(
            replica_id="replica-a",
            replica_advertised_host="replica-a",
            replica_advertised_port=8201,
            heartbeat_interval_sec=0.01,
        ),
    )

    with TestClient(create_replica_app(replica_manager=manager)) as client:
        time.sleep(0.05)
        response = client.get("/health")

    assert response.status_code == 200
    assert len(name_service.heartbeat_calls) >= 1


def test_replica_overwrite_and_model_id_isolation() -> None:
    manager = _build_manager()

    first_write = manager.write_cache({"prompt": "hello", "response_text": "world", "model_id": "demo"})
    second_write = manager.write_cache({"prompt": "hello", "response_text": "again", "model_id": "demo"})
    other_model_write = manager.write_cache({"prompt": "hello", "response_text": "other", "model_id": "alt"})

    first_hit = manager.read_cache({"prompt": "hello", "model_id": "demo", "semantic_enabled": True})
    other_hit = manager.read_cache({"prompt": "hello", "model_id": "alt", "semantic_enabled": True})
    miss = manager.read_cache({"prompt": "hello", "model_id": "missing", "semantic_enabled": True})

    assert first_write["lamport_ts"] == 1
    assert second_write["lamport_ts"] == 2
    assert other_model_write["lamport_ts"] == 3
    assert first_hit["response_text"] == "again"
    assert other_hit["response_text"] == "other"
    assert miss["hit"] is False


def _build_manager(
    *,
    settings: ReplicaSettings | None = None,
    name_service_client: RecordingNameServiceClient | None = None,
) -> ReplicaManager:
    resolved_settings = settings or ReplicaSettings(
        replica_id="replica-a",
        replica_advertised_host="replica-a",
        replica_advertised_port=8201,
        qdrant_url="http://qdrant-a:6333",
    )
    return ReplicaManager(
        settings=resolved_settings,
        name_service_client=name_service_client or RecordingNameServiceClient(),
        vector_store=VectorStoreAdapter(settings=resolved_settings, client_factory=NoOpVectorClient),
    )
