import threading
import time

from fastapi.testclient import TestClient

from services.replica.cache_service import CacheService
from services.replica.clients import NameServiceClientError, ReplicaPeerClientError
from services.replica.embedding import DeterministicTestEmbedder
from services.replica.main import create_app as create_replica_app
from services.replica.manager import ReplicaManager
from services.replica.vector_store import VectorStoreAdapter
from shared.config import ReplicaSettings
from tests.replica_fakes import FakeQdrantClient


class RecordingNameServiceClient:
    def __init__(
        self,
        *,
        fail_heartbeat: bool = False,
        fail_register_count: int = 0,
        heartbeat_member_override: dict | None = None,
    ) -> None:
        self.fail_heartbeat = fail_heartbeat
        self.fail_register_count = fail_register_count
        self.heartbeat_member_override = heartbeat_member_override
        self.register_calls: list[dict] = []
        self.heartbeat_calls: list[dict] = []
        self.closed = False

    async def register(self, payload: dict) -> dict:
        self.register_calls.append(payload)
        if self.fail_register_count > 0:
            self.fail_register_count -= 1
            raise NameServiceClientError("register unavailable")
        return {"registered": True, "member": payload}

    async def heartbeat(self, payload: dict) -> dict:
        self.heartbeat_calls.append(payload)
        if self.fail_heartbeat:
            raise NameServiceClientError("heartbeat unavailable")
        member = self.heartbeat_member_override or payload
        return {"accepted": True, "member": member}

    async def close(self) -> None:
        self.closed = True


class RecordingWarmupEmbedder(DeterministicTestEmbedder):
    def __init__(self, dimensions: int = 384) -> None:
        super().__init__(dimensions=dimensions)
        self.calls: list[str] = []

    def embed(self, text: str) -> list[float]:
        self.calls.append(text)
        return super().embed(text)


class DirectReplicaPeerClient:
    def __init__(self, network: dict[str, ReplicaManager]) -> None:
        self.network = network

    def request_token(self, replica_url: str, payload: dict) -> dict:
        return self._target(replica_url).request_internal_token(payload)

    def transfer_token(self, replica_url: str, payload: dict) -> dict:
        return self._target(replica_url).receive_internal_token(payload)

    def mark_write_started(self, replica_url: str, payload: dict) -> dict:
        return self._target(replica_url).mark_internal_write_started(payload)

    def replicate_write(self, replica_url: str, payload: dict) -> dict:
        return self._target(replica_url).apply_replicated_write(payload)

    def mark_write_finished(self, replica_url: str, payload: dict) -> dict:
        return self._target(replica_url).mark_internal_write_finished(payload)

    def _target(self, replica_url: str) -> ReplicaManager:
        manager = self.network.get(replica_url)
        if manager is None:
            raise ReplicaPeerClientError(f"No replica is registered for {replica_url}")
        return manager


class FailingReplicationPeerClient(DirectReplicaPeerClient):
    def __init__(self, network: dict[str, ReplicaManager], failing_replica_url: str) -> None:
        super().__init__(network)
        self.failing_replica_url = failing_replica_url

    def replicate_write(self, replica_url: str, payload: dict) -> dict:
        if replica_url == self.failing_replica_url:
            raise ReplicaPeerClientError(f"replication failed for {replica_url}")
        return super().replicate_write(replica_url, payload)


class TimeoutAfterRemoteWriteStartedPeerClient(DirectReplicaPeerClient):
    def __init__(self, network: dict[str, ReplicaManager], failing_replica_url: str) -> None:
        super().__init__(network)
        self.failing_replica_url = failing_replica_url
        self._raised = False

    def mark_write_started(self, replica_url: str, payload: dict) -> dict:
        response = super().mark_write_started(replica_url, payload)
        if replica_url == self.failing_replica_url and not self._raised:
            self._raised = True
            raise ReplicaPeerClientError(f"timed out after starting remote write on {replica_url}")
        return response


class DelayedRemoteWriteStartTimeoutPeerClient(DirectReplicaPeerClient):
    def __init__(self, network: dict[str, ReplicaManager], failing_replica_url: str) -> None:
        super().__init__(network)
        self.failing_replica_url = failing_replica_url
        self._raised = False
        self.delayed_start_completed = threading.Event()

    def mark_write_started(self, replica_url: str, payload: dict) -> dict:
        if replica_url == self.failing_replica_url and not self._raised:
            self._raised = True

            def run_delayed_start() -> None:
                time.sleep(0.2)
                self._target(replica_url).mark_internal_write_started(payload)
                self.delayed_start_completed.set()

            threading.Thread(target=run_delayed_start, daemon=True).start()
            raise ReplicaPeerClientError(f"timed out before remote write start completed on {replica_url}")
        return super().mark_write_started(replica_url, payload)


class LostTokenTransferResponsePeerClient(DirectReplicaPeerClient):
    def __init__(self, network: dict[str, ReplicaManager], failing_replica_url: str) -> None:
        super().__init__(network)
        self.failing_replica_url = failing_replica_url
        self._raised = False

    def transfer_token(self, replica_url: str, payload: dict) -> dict:
        response = super().transfer_token(replica_url, payload)
        if replica_url == self.failing_replica_url and not self._raised:
            self._raised = True
            raise ReplicaPeerClientError(f"lost token transfer response for {replica_url}")
        return response


def test_replica_registers_on_startup() -> None:
    name_service = RecordingNameServiceClient()
    manager = _build_manager(name_service_client=name_service)

    with TestClient(create_replica_app(replica_manager=manager)):
        pass

    assert name_service.register_calls == [
        {"replica_id": "replica-a", "host": "replica-a", "port": 8201}
    ]
    assert name_service.closed is True


def test_replica_prewarms_semantic_runtime_on_startup() -> None:
    settings = _settings(
        "replica-a",
        8201,
        peer_targets="replica-a=http://replica-a:8201",
    )
    embedder = RecordingWarmupEmbedder(dimensions=settings.semantic_vector_size)
    vector_store = VectorStoreAdapter(
        settings=settings,
        client_factory=FakeQdrantClient,
        vector_size=embedder.vector_size,
    )
    cache_service = CacheService(
        settings=settings,
        vector_store=vector_store,
        embedder=embedder,
    )
    manager = ReplicaManager(
        settings=settings,
        cache_service=cache_service,
        name_service_client=RecordingNameServiceClient(),
        vector_store=vector_store,
        peer_client=DirectReplicaPeerClient({}),
    )

    with TestClient(create_replica_app(replica_manager=manager)):
        pass

    assert embedder.calls == ["CacheMesh startup semantic warmup."]


def test_replica_heartbeat_failures_are_tolerated() -> None:
    name_service = RecordingNameServiceClient(fail_heartbeat=True)
    manager = _build_manager(
        name_service_client=name_service,
        settings=ReplicaSettings(
            replica_id="replica-a",
            replica_advertised_host="replica-a",
            replica_advertised_port=8201,
            heartbeat_interval_sec=0.01,
            replica_peer_targets="replica-a=http://replica-a:8201",
            qdrant_url="http://qdrant-a:6333",
        ),
    )

    with TestClient(create_replica_app(replica_manager=manager)) as client:
        time.sleep(0.05)
        response = client.get("/health")

    assert response.status_code == 200
    assert len(name_service.heartbeat_calls) >= 1


def test_replica_retries_registration_until_name_service_is_reachable() -> None:
    name_service = RecordingNameServiceClient(fail_register_count=1)
    manager = _build_manager(
        name_service_client=name_service,
        settings=ReplicaSettings(
            replica_id="replica-a",
            replica_advertised_host="replica-a",
            replica_advertised_port=8201,
            heartbeat_interval_sec=0.01,
            replica_peer_targets="replica-a=http://replica-a:8201",
            qdrant_url="http://qdrant-a:6333",
        ),
    )

    with TestClient(create_replica_app(replica_manager=manager)) as client:
        time.sleep(0.05)
        response = client.get("/health")

    assert response.status_code == 200
    assert len(name_service.register_calls) >= 2
    assert manager._registered_with_name_service is True


def test_replica_overwrite_model_isolation_and_semantic_hits() -> None:
    manager = _build_manager(
        settings=ReplicaSettings(
            replica_id="replica-a",
            replica_advertised_host="replica-a",
            replica_advertised_port=8201,
            qdrant_url="http://qdrant-a:6333",
            replica_peer_targets="replica-a=http://replica-a:8201",
            semantic_score_threshold=0.18,
        )
    )

    first_write = manager.write_cache(
        {"prompt": "hello distributed systems", "response_text": "world", "model_id": "demo"}
    )
    second_write = manager.write_cache(
        {"prompt": "hello distributed systems", "response_text": "again", "model_id": "demo"}
    )
    other_model_write = manager.write_cache(
        {"prompt": "hello distributed systems", "response_text": "other", "model_id": "alt"}
    )
    semantic_write = manager.write_cache(
        {
            "prompt": "how can i bake bread at home",
            "response_text": "Use flour, water, yeast, and patience.",
            "model_id": "demo",
        }
    )

    first_hit = manager.read_cache({"prompt": "hello distributed systems", "model_id": "demo", "semantic_enabled": True})
    other_hit = manager.read_cache({"prompt": "hello distributed systems", "model_id": "alt", "semantic_enabled": True})
    semantic_hit = manager.read_cache(
        {"prompt": "bread baking instructions for beginners", "model_id": "demo", "semantic_enabled": True}
    )
    miss = manager.read_cache({"prompt": "hello distributed systems", "model_id": "missing", "semantic_enabled": True})

    assert first_write["lamport_ts"] == 1
    assert second_write["lamport_ts"] == 2
    assert other_model_write["lamport_ts"] == 3
    assert semantic_write["lamport_ts"] == 4
    assert first_hit["response_text"] == "again"
    assert other_hit["response_text"] == "other"
    assert semantic_hit["hit"] is True
    assert semantic_hit["response_text"] == "Use flour, water, yeast, and patience."
    assert semantic_hit["score"] is not None
    assert miss["hit"] is False


def test_coordination_status_reports_token_holder_state() -> None:
    network: dict[str, ReplicaManager] = {}
    manager_a = _build_manager(
        settings=_settings(
            "replica-a",
            8201,
            peer_targets="replica-a=http://replica-a:8201,replica-b=http://replica-b:8202",
        ),
        peer_client=DirectReplicaPeerClient(network),
    )
    manager_b = _build_manager(
        settings=_settings(
            "replica-b",
            8202,
            peer_targets="replica-a=http://replica-a:8201,replica-b=http://replica-b:8202",
        ),
        peer_client=DirectReplicaPeerClient(network),
    )
    network.update(
        {
            "http://replica-a:8201": manager_a,
            "http://replica-b:8202": manager_b,
        }
    )

    status_a_before = manager_a.coordination_status()
    status_b_before = manager_b.coordination_status()

    manager_b.write_cache(
        {"prompt": "handoff check", "response_text": "token moved", "model_id": "demo"}
    )

    status_a_after = manager_a.coordination_status()
    status_b_after = manager_b.coordination_status()

    assert status_a_before["has_token"] is True
    assert status_b_before["has_token"] is False
    assert status_a_after["has_token"] is False
    assert status_b_after["has_token"] is True
    assert status_b_after["local_write_active"] is False


def test_replica_write_replicates_to_all_peers() -> None:
    network: dict[str, ReplicaManager] = {}
    managers = [
        _build_manager(
            settings=_settings(
                "replica-a",
                8201,
                peer_targets="replica-a=http://replica-a:8201,replica-b=http://replica-b:8202,replica-c=http://replica-c:8203",
            ),
            peer_client=DirectReplicaPeerClient(network),
        ),
        _build_manager(
            settings=_settings(
                "replica-b",
                8202,
                peer_targets="replica-a=http://replica-a:8201,replica-b=http://replica-b:8202,replica-c=http://replica-c:8203",
            ),
            peer_client=DirectReplicaPeerClient(network),
        ),
        _build_manager(
            settings=_settings(
                "replica-c",
                8203,
                peer_targets="replica-a=http://replica-a:8201,replica-b=http://replica-b:8202,replica-c=http://replica-c:8203",
            ),
            peer_client=DirectReplicaPeerClient(network),
        ),
    ]
    network.update(
        {
            "http://replica-a:8201": managers[0],
            "http://replica-b:8202": managers[1],
            "http://replica-c:8203": managers[2],
        }
    )

    response = managers[1].write_cache({"prompt": "cache me", "response_text": "yes", "model_id": "demo"})

    assert response["stored"] is True
    assert response["replica_id"] == "replica-b"
    for manager in managers:
        hit = manager.read_cache({"prompt": "cache me", "model_id": "demo", "semantic_enabled": True})
        assert hit["hit"] is True
        assert hit["response_text"] == "yes"


def test_read_waits_for_remote_write_and_returns_hit_after_replication() -> None:
    network: dict[str, ReplicaManager] = {}
    delay_started = threading.Event()
    release_write = threading.Event()
    writer_result: dict = {}
    reader_result: dict = {}

    def delay_hook(_: dict) -> None:
        delay_started.set()
        assert release_write.wait(timeout=15)

    manager_a = _build_manager(
        settings=_settings(
            "replica-a",
            8201,
            peer_targets="replica-a=http://replica-a:8201,replica-b=http://replica-b:8202",
        ),
        peer_client=DirectReplicaPeerClient(network),
    )
    manager_b = _build_manager(
        settings=_settings(
            "replica-b",
            8202,
            peer_targets="replica-a=http://replica-a:8201,replica-b=http://replica-b:8202",
        ),
        peer_client=DirectReplicaPeerClient(network),
        write_delay_hook=delay_hook,
    )
    network.update(
        {
            "http://replica-a:8201": manager_a,
            "http://replica-b:8202": manager_b,
        }
    )

    def run_write() -> None:
        writer_result["response"] = manager_b.write_cache(
            {
                "prompt": "long write prompt",
                "response_text": "written before read returns",
                "model_id": "demo",
            }
        )

    def run_read() -> None:
        reader_result["response"] = manager_a.read_cache(
            {
                "prompt": "long write prompt",
                "model_id": "demo",
                "semantic_enabled": True,
            }
        )

    writer = threading.Thread(target=run_write)
    writer.start()
    assert delay_started.wait(timeout=5)

    read_started = time.monotonic()
    reader = threading.Thread(target=run_read)
    reader.start()
    time.sleep(0.2)
    assert reader.is_alive() is True

    release_write.set()
    writer.join(timeout=15)
    reader.join(timeout=15)
    elapsed = time.monotonic() - read_started

    assert writer_result["response"]["stored"] is True
    assert reader_result["response"]["hit"] is True
    assert reader_result["response"]["response_text"] == "written before read returns"
    assert elapsed >= 0.15


def test_replication_failure_after_local_write_reports_degraded_but_origin_keeps_value() -> None:
    network: dict[str, ReplicaManager] = {}
    peer_client = FailingReplicationPeerClient(network, "http://replica-b:8202")
    manager_a = _build_manager(
        settings=_settings(
            "replica-a",
            8201,
            peer_targets="replica-a=http://replica-a:8201,replica-b=http://replica-b:8202",
        ),
        peer_client=peer_client,
    )
    manager_b = _build_manager(
        settings=_settings(
            "replica-b",
            8202,
            peer_targets="replica-a=http://replica-a:8201,replica-b=http://replica-b:8202",
        ),
        peer_client=DirectReplicaPeerClient(network),
    )
    network.update(
        {
            "http://replica-a:8201": manager_a,
            "http://replica-b:8202": manager_b,
        }
    )

    response = manager_a.write_cache(
        {"prompt": "partial replication", "response_text": "origin keeps value", "model_id": "demo"}
    )
    origin_hit = manager_a.read_cache(
        {"prompt": "partial replication", "model_id": "demo", "semantic_enabled": True}
    )
    peer_hit = manager_b.read_cache(
        {"prompt": "partial replication", "model_id": "demo", "semantic_enabled": True}
    )

    assert response["status"] == "degraded"
    assert response["stored"] is True
    assert origin_hit["hit"] is True
    assert origin_hit["response_text"] == "origin keeps value"
    assert peer_hit["hit"] is False


def test_failed_mark_write_started_still_releases_remote_writer_state() -> None:
    network: dict[str, ReplicaManager] = {}
    peer_client = TimeoutAfterRemoteWriteStartedPeerClient(network, "http://replica-b:8202")
    manager_a = _build_manager(
        settings=_settings(
            "replica-a",
            8201,
            peer_targets="replica-a=http://replica-a:8201,replica-b=http://replica-b:8202",
        ),
        peer_client=peer_client,
    )
    manager_b = _build_manager(
        settings=_settings(
            "replica-b",
            8202,
            peer_targets="replica-a=http://replica-a:8201,replica-b=http://replica-b:8202",
        ),
        peer_client=DirectReplicaPeerClient(network),
    )
    network.update(
        {
            "http://replica-a:8201": manager_a,
            "http://replica-b:8202": manager_b,
        }
    )

    response = manager_a.write_cache(
        {"prompt": "start timeout", "response_text": "should not persist", "model_id": "demo"}
    )
    start = time.monotonic()
    read_response = manager_b.read_cache(
        {"prompt": "start timeout", "model_id": "demo", "semantic_enabled": True}
    )
    elapsed = time.monotonic() - start

    assert response["status"] == "unavailable"
    assert response["stored"] is False
    assert read_response["hit"] is False
    assert elapsed < 1.0


def test_write_finish_arriving_before_remote_start_completes_does_not_block_future_reads() -> None:
    network: dict[str, ReplicaManager] = {}
    peer_client = DelayedRemoteWriteStartTimeoutPeerClient(network, "http://replica-b:8202")
    manager_a = _build_manager(
        settings=_settings(
            "replica-a",
            8201,
            peer_targets="replica-a=http://replica-a:8201,replica-b=http://replica-b:8202",
        ),
        peer_client=peer_client,
    )
    manager_b = _build_manager(
        settings=_settings(
            "replica-b",
            8202,
            peer_targets="replica-a=http://replica-a:8201,replica-b=http://replica-b:8202",
        ),
        peer_client=DirectReplicaPeerClient(network),
    )
    network.update(
        {
            "http://replica-a:8201": manager_a,
            "http://replica-b:8202": manager_b,
        }
    )

    response = manager_a.write_cache(
        {"prompt": "finish before start", "response_text": "should not stick", "model_id": "demo"}
    )
    assert peer_client.delayed_start_completed.wait(timeout=2)

    start = time.monotonic()
    read_response = manager_b.read_cache(
        {"prompt": "finish before start", "model_id": "demo", "semantic_enabled": True}
    )
    elapsed = time.monotonic() - start

    assert response["status"] == "unavailable"
    assert response["stored"] is False
    assert read_response["hit"] is False
    assert elapsed < 1.0


def test_lost_token_transfer_response_does_not_leave_both_replicas_holding_token() -> None:
    network: dict[str, ReplicaManager] = {}
    manager_a = _build_manager(
        settings=_settings(
            "replica-a",
            8201,
            peer_targets="replica-a=http://replica-a:8201,replica-b=http://replica-b:8202",
        ),
        peer_client=LostTokenTransferResponsePeerClient(network, "http://replica-b:8202"),
    )
    manager_b = _build_manager(
        settings=_settings(
            "replica-b",
            8202,
            peer_targets="replica-a=http://replica-a:8201,replica-b=http://replica-b:8202",
        ),
        peer_client=DirectReplicaPeerClient(network),
    )
    network.update(
        {
            "http://replica-a:8201": manager_a,
            "http://replica-b:8202": manager_b,
        }
    )

    response = manager_b.write_cache(
        {"prompt": "token handoff", "response_text": "may fail before write", "model_id": "demo"}
    )

    assert response["status"] == "ok"
    assert response["stored"] is True
    assert manager_a.coordinator.has_token is False
    assert manager_b.coordinator.has_token is True


def test_token_can_move_multiple_times_between_replicas() -> None:
    network: dict[str, ReplicaManager] = {}
    managers = {
        "replica-a": _build_manager(
            settings=_settings(
                "replica-a",
                8201,
                peer_targets="replica-a=http://replica-a:8201,replica-b=http://replica-b:8202,replica-c=http://replica-c:8203",
            ),
            peer_client=DirectReplicaPeerClient(network),
        ),
        "replica-b": _build_manager(
            settings=_settings(
                "replica-b",
                8202,
                peer_targets="replica-a=http://replica-a:8201,replica-b=http://replica-b:8202,replica-c=http://replica-c:8203",
            ),
            peer_client=DirectReplicaPeerClient(network),
        ),
        "replica-c": _build_manager(
            settings=_settings(
                "replica-c",
                8203,
                peer_targets="replica-a=http://replica-a:8201,replica-b=http://replica-b:8202,replica-c=http://replica-c:8203",
            ),
            peer_client=DirectReplicaPeerClient(network),
        ),
    }
    network.update(
        {
            "http://replica-a:8201": managers["replica-a"],
            "http://replica-b:8202": managers["replica-b"],
            "http://replica-c:8203": managers["replica-c"],
        }
    )

    first = managers["replica-b"].write_cache(
        {"prompt": "first distributed write", "response_text": "from b", "model_id": "demo"}
    )
    second = managers["replica-c"].write_cache(
        {"prompt": "second distributed write", "response_text": "from c", "model_id": "demo"}
    )

    assert first["stored"] is True
    assert second["stored"] is True
    for manager in managers.values():
        first_hit = manager.read_cache(
            {"prompt": "first distributed write", "model_id": "demo", "semantic_enabled": True}
        )
        second_hit = manager.read_cache(
            {"prompt": "second distributed write", "model_id": "demo", "semantic_enabled": True}
        )
        assert first_hit["hit"] is True
        assert second_hit["hit"] is True


def _settings(replica_id: str, port: int, *, peer_targets: str) -> ReplicaSettings:
    return ReplicaSettings(
        replica_id=replica_id,
        replica_advertised_host=replica_id,
        replica_advertised_port=port,
        qdrant_url=f"http://qdrant-{replica_id[-1]}:6333",
        replica_peer_targets=peer_targets,
        initial_token_replica_id="replica-a",
        semantic_score_threshold=0.18,
    )


def _build_manager(
    *,
    settings: ReplicaSettings | None = None,
    name_service_client: RecordingNameServiceClient | None = None,
    peer_client: DirectReplicaPeerClient | None = None,
    write_delay_hook=None,
) -> ReplicaManager:
    resolved_settings = settings or _settings(
        "replica-a",
        8201,
        peer_targets="replica-a=http://replica-a:8201",
    )
    embedder = DeterministicTestEmbedder(dimensions=resolved_settings.semantic_vector_size)
    vector_store = VectorStoreAdapter(
        settings=resolved_settings,
        client_factory=FakeQdrantClient,
        vector_size=embedder.vector_size,
    )
    cache_service = CacheService(
        settings=resolved_settings,
        vector_store=vector_store,
        embedder=embedder,
    )
    return ReplicaManager(
        settings=resolved_settings,
        cache_service=cache_service,
        name_service_client=name_service_client or RecordingNameServiceClient(),
        vector_store=vector_store,
        peer_client=peer_client or DirectReplicaPeerClient({}),
        write_delay_hook=write_delay_hook,
    )
