import asyncio
import contextlib
import logging
from collections.abc import Callable

from services.replica.cache_service import CacheService
from services.replica.clients import (
    NameServiceClient,
    NameServiceClientError,
    ReplicaPeerClient,
    ReplicaPeerClientError,
)
from services.replica.coordination import DistributedReadWriteCoordinator
from services.replica.config import get_settings
from services.replica.embedding import SentenceTransformerEmbedder
from services.replica.fault_service import ReplicaFaultService
from services.replica.sync_service import SyncService
from services.replica.vector_store import VectorStoreAdapter
from shared.clock import LamportClock
from shared.config import ReplicaSettings
from shared.faults import FaultController


logger = logging.getLogger(__name__)


class ReplicaManager:
    def __init__(
        self,
        settings: ReplicaSettings | None = None,
        cache_service: CacheService | None = None,
        name_service_client: NameServiceClient | None = None,
        vector_store: VectorStoreAdapter | None = None,
        fault_service: ReplicaFaultService | None = None,
        sync_service: SyncService | None = None,
        peer_client: ReplicaPeerClient | None = None,
        coordinator: DistributedReadWriteCoordinator | None = None,
        write_delay_hook: Callable[[dict], None] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.clock = LamportClock()
        self.embedder = SentenceTransformerEmbedder(settings=self.settings)
        self.vector_store = vector_store or VectorStoreAdapter(
            settings=self.settings,
            vector_size=self.embedder.vector_size,
        )
        self.cache_service = cache_service or CacheService(
            settings=self.settings,
            vector_store=self.vector_store,
            embedder=self.embedder,
        )
        self.name_service_client = name_service_client or NameServiceClient(
            self.settings.name_service_url,
            self.settings.request_timeout_sec,
        )
        self.fault_service = fault_service or ReplicaFaultService(FaultController())
        self.sync_service = sync_service or SyncService()
        self.peer_client = peer_client or ReplicaPeerClient(self.settings.request_timeout_sec)
        self.coordinator = coordinator or DistributedReadWriteCoordinator(self.settings.replica_id, self.clock)
        self.write_delay_hook = write_delay_hook
        self._heartbeat_task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        await self._register()
        if self._heartbeat_task is None:
            self._stop_event = asyncio.Event()
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def stop(self) -> None:
        self._stop_event.set()
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._heartbeat_task
            self._heartbeat_task = None
        await self.name_service_client.close()
        self.vector_store.close()

    def health(self) -> dict:
        return {
            "service": "replica",
            "status": "ok",
            "detail": "Replica manager is running.",
        }

    def read_cache(self, payload: dict) -> dict:
        with self.coordinator.read_guard():
            return self.cache_service.read(payload)

    def write_cache(self, payload: dict) -> dict:
        request = self.coordinator.open_local_write_request()
        peers = self._peer_targets()
        granted_peers: list[dict[str, str]] = []
        started_peers: list[dict[str, str]] = []
        write_started = False
        lamport_ts: int | None = None
        try:
            for peer in peers:
                self.peer_client.request_write_lock(
                    peer["url"],
                    {"replica_id": self.settings.replica_id, "lamport_ts": request.lamport_ts},
                )
                granted_peers.append(peer)

            lamport_ts = self.coordinator.begin_local_write(request)
            write_started = True
            for peer in granted_peers:
                self.peer_client.mark_write_started(
                    peer["url"],
                    {"replica_id": self.settings.replica_id, "lamport_ts": lamport_ts},
                )
                started_peers.append(peer)

            result = self.cache_service.apply_write(
                payload,
                lamport_ts=lamport_ts,
                replica_origin=self.settings.replica_id,
            )
            if self.write_delay_hook is not None:
                self.write_delay_hook(payload)

            replicate_payload = {
                **payload,
                "lamport_ts": lamport_ts,
                "vector": result.vector,
                "source_replica_id": self.settings.replica_id,
            }
            for peer in granted_peers:
                self.peer_client.replicate_write(peer["url"], replicate_payload)

            return self._write_response(
                status="ok",
                detail="Cache entry stored locally and replicated to healthy peers.",
                stored=True,
                model_id=payload["model_id"],
                lamport_ts=lamport_ts,
            )
        except (ReplicaPeerClientError, Exception) as exc:
            logger.exception("Distributed cache write failed: %s", exc)
            return self._write_response(
                status="unavailable",
                detail=f"Distributed cache write failed: {exc}",
                stored=False,
                model_id=payload["model_id"],
                lamport_ts=lamport_ts,
            )
        finally:
            self._release_remote_writers(started_peers)
            if write_started:
                self.coordinator.finish_local_write(request)
            else:
                self.coordinator.abort_local_write(request)

    def snapshot(self, payload: dict) -> dict:
        return self.sync_service.snapshot(payload)

    def replay(self, payload: dict) -> dict:
        return self.sync_service.replay(payload)

    def arm_fault(self, payload: dict) -> dict:
        return self.fault_service.arm_fault(payload)

    def describe_vector_store(self) -> dict:
        return self.vector_store.describe()

    def request_internal_write_lock(self, payload: dict) -> dict:
        return self.coordinator.grant_remote_write_request(payload["replica_id"], payload["lamport_ts"])

    def mark_internal_write_started(self, payload: dict) -> dict:
        return self.coordinator.mark_remote_write_started(payload["replica_id"], payload["lamport_ts"])

    def apply_replicated_write(self, payload: dict) -> dict:
        self.clock.update(payload["lamport_ts"])
        self.cache_service.apply_write(
            payload,
            lamport_ts=payload["lamport_ts"],
            vector=payload["vector"],
            replica_origin=payload["source_replica_id"],
        )
        return self._write_response(
            status="ok",
            detail="Replicated cache entry stored on this replica.",
            stored=True,
            model_id=payload["model_id"],
            lamport_ts=payload["lamport_ts"],
        )

    def mark_internal_write_finished(self, payload: dict) -> dict:
        return self.coordinator.mark_remote_write_finished(payload["replica_id"])

    async def _register(self) -> None:
        payload = {
            "replica_id": self.settings.replica_id,
            "host": self.settings.replica_advertised_host,
            "port": self.settings.advertised_port,
        }
        try:
            await self.name_service_client.register(payload)
        except NameServiceClientError as exc:
            logger.warning("Replica registration failed: %s", exc)

    async def _heartbeat_loop(self) -> None:
        interval = self.settings.heartbeat_interval_sec
        while not self._stop_event.is_set():
            try:
                await asyncio.sleep(interval)
                await self.name_service_client.heartbeat(
                    {
                        "replica_id": self.settings.replica_id,
                        "status": "healthy",
                    }
                )
            except asyncio.CancelledError:
                raise
            except NameServiceClientError as exc:
                logger.warning("Replica heartbeat failed: %s", exc)

    def _peer_targets(self) -> list[dict[str, str]]:
        return [
            target
            for target in self.settings.peer_targets
            if target["replica_id"] != self.settings.replica_id
        ]

    def _release_remote_writers(self, peers: list[dict[str, str]]) -> None:
        for peer in reversed(peers):
            try:
                self.peer_client.mark_write_finished(
                    peer["url"],
                    {"replica_id": self.settings.replica_id},
                )
            except ReplicaPeerClientError as exc:
                logger.warning("Could not release remote writer state on %s: %s", peer["replica_id"], exc)

    def _write_response(
        self,
        *,
        status: str,
        detail: str,
        stored: bool,
        model_id: str,
        lamport_ts: int | None,
    ) -> dict:
        return {
            "service": "replica",
            "action": "cache.write",
            "status": status,
            "detail": detail,
            "stored": stored,
            "replica_id": self.settings.replica_id,
            "model_id": model_id,
            "lamport_ts": lamport_ts,
        }
