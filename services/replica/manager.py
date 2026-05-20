import asyncio
import contextlib
import logging
from collections.abc import Callable
from uuid import uuid4

from services.replica.cache_service import CacheService
from services.replica.clients import (
    NameServiceClient,
    NameServiceClientError,
    ReplicaPeerClient,
    ReplicaPeerClientError,
)
from services.replica.coordination import RicartAgrawalaTokenCoordinator
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
        coordinator: RicartAgrawalaTokenCoordinator | None = None,
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
        self.coordinator = coordinator or RicartAgrawalaTokenCoordinator(
            self.settings.replica_id,
            self.clock,
            replica_ids=[target["replica_id"] for target in self.settings.peer_targets],
            initial_token_holder=self.settings.initial_token_replica_id,
        )
        self.write_delay_hook = write_delay_hook
        self._pending_token_transfer: tuple[str, dict[str, object]] | None = None
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
        self.fault_service.check_and_apply()
        with self.coordinator.read_guard():
            return self.cache_service.read(payload)

    def write_cache(self, payload: dict) -> dict:
        self.fault_service.check_and_apply()
        request_seq = self.coordinator.open_local_write_request()
        peers = self._peer_targets()
        started_peers: list[dict[str, str]] = []
        write_started = False
        local_write_applied = False
        lamport_ts: int | None = None
        write_id = str(uuid4())
        try:
            if self.coordinator.should_broadcast_request():
                for peer in peers:
                    self.peer_client.request_token(
                        peer["url"],
                        {"replica_id": self.settings.replica_id, "request_seq": request_seq},
                    )

            self.coordinator.begin_local_write(request_seq)
            lamport_ts = self.clock.tick()
            write_started = True
            for peer in peers:
                started_peers.append(peer)
                self.peer_client.mark_write_started(
                    peer["url"],
                    {
                        "replica_id": self.settings.replica_id,
                        "lamport_ts": lamport_ts,
                        "write_id": write_id,
                    },
                )

            result = self.cache_service.apply_write(
                payload,
                lamport_ts=lamport_ts,
                replica_origin=self.settings.replica_id,
            )
            local_write_applied = True
            self.sync_service.record_write(
                payload=payload,
                lamport_ts=lamport_ts,
                vector=result.vector,
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
            for peer in peers:
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
            if local_write_applied:
                return self._write_response(
                    status="degraded",
                    detail=(
                        "Cache entry stored locally, but distributed replication did not "
                        f"complete successfully: {exc}"
                    ),
                    stored=True,
                    model_id=payload["model_id"],
                    lamport_ts=lamport_ts,
                )
            return self._write_response(
                status="unavailable",
                detail=f"Distributed cache write failed: {exc}",
                stored=False,
                model_id=payload["model_id"],
                lamport_ts=lamport_ts,
            )
        finally:
            self._release_remote_writers(started_peers, write_id)
            if write_started:
                self.coordinator.finish_local_write(request_seq)
            else:
                self.coordinator.abort_local_write(request_seq)
            self._pass_token_if_needed()

    def snapshot(self, payload: dict) -> dict:
        self.fault_service.check_and_apply()
        return self.sync_service.snapshot(payload)

    def replay(self, payload: dict) -> dict:
        self.fault_service.check_and_apply()
        result = self.sync_service.replay(payload)
        replay_entries = result.pop("_replay_entries", [])
        for entry in replay_entries:
            self.clock.update(entry["lamport_ts"])
            self.cache_service.apply_write(
                {
                    "prompt": entry["prompt"],
                    "response_text": entry["response_text"],
                    "model_id": entry["model_id"],
                },
                lamport_ts=entry["lamport_ts"],
                vector=entry["vector"],
                replica_origin=entry.get("replica_origin"),
            )
            self.sync_service.record_replay_entry(entry)
        return result

    def arm_fault(self, payload: dict) -> dict:
        return self.fault_service.arm_fault(payload)

    def describe_vector_store(self) -> dict:
        return self.vector_store.describe()

    def request_internal_token(self, payload: dict) -> dict:
        response = self.coordinator.note_remote_token_request(payload["replica_id"], payload["request_seq"])
        self._pass_token_if_needed()
        return response

    def receive_internal_token(self, payload: dict) -> dict:
        response = self.coordinator.receive_token(
            payload["from_replica_id"],
            last_granted=payload["last_granted"],
            queue=payload["queue"],
            version=payload["version"],
        )
        self._pass_token_if_needed()
        return response

    def mark_internal_write_started(self, payload: dict) -> dict:
        return self.coordinator.mark_remote_write_started(
            payload["replica_id"],
            payload["lamport_ts"],
            payload["write_id"],
        )

    def apply_replicated_write(self, payload: dict) -> dict:
        self.clock.update(payload["lamport_ts"])
        self.cache_service.apply_write(
            payload,
            lamport_ts=payload["lamport_ts"],
            vector=payload["vector"],
            replica_origin=payload["source_replica_id"],
        )
        self.sync_service.record_write(
            payload=payload,
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
        return self.coordinator.mark_remote_write_finished(payload["replica_id"], payload["write_id"])

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

    def _release_remote_writers(self, peers: list[dict[str, str]], write_id: str) -> None:
        for peer in reversed(peers):
            try:
                self.peer_client.mark_write_finished(
                    peer["url"],
                    {"replica_id": self.settings.replica_id, "write_id": write_id},
                )
            except ReplicaPeerClientError as exc:
                logger.warning("Could not release remote writer state on %s: %s", peer["replica_id"], exc)

    def _pass_token_if_needed(self) -> None:
        if self._pending_token_transfer is None:
            recipient_id = self.coordinator.next_token_recipient()
            if recipient_id is None:
                return
            target = self._peer_target_by_id(recipient_id)
            if target is None:
                logger.warning("Token recipient %s is not in the configured peer targets.", recipient_id)
                return
            payload = {
                "from_replica_id": self.settings.replica_id,
                **self.coordinator.export_token_for_transfer(recipient_id),
            }
            self.coordinator.mark_token_sent(recipient_id, int(payload["version"]))
            self._pending_token_transfer = (recipient_id, payload)

        recipient_id, payload = self._pending_token_transfer
        target = self._peer_target_by_id(recipient_id)
        if target is None:
            logger.warning("Pending token recipient %s is not in the configured peer targets.", recipient_id)
            return

        try:
            response = self.peer_client.transfer_token(target["url"], payload)
        except ReplicaPeerClientError as exc:
            logger.warning("Could not complete token transfer to %s: %s", recipient_id, exc)
            return

        if response.get("accepted") or response.get("stale"):
            self._pending_token_transfer = None

    def _peer_target_by_id(self, replica_id: str) -> dict[str, str] | None:
        for target in self.settings.peer_targets:
            if target["replica_id"] == replica_id:
                return target
        return None

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
