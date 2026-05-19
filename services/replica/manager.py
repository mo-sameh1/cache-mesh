import asyncio
import contextlib
import logging

from services.replica.cache_service import CacheService
from services.replica.clients import NameServiceClient, NameServiceClientError
from services.replica.config import get_settings
from services.replica.fault_service import ReplicaFaultService
from services.replica.sync_service import SyncService
from services.replica.vector_store import VectorStoreAdapter
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
    ) -> None:
        self.settings = settings or get_settings()
        self.cache_service = cache_service or CacheService(settings=self.settings)
        self.name_service_client = name_service_client or NameServiceClient(
            self.settings.name_service_url,
            self.settings.request_timeout_sec,
        )
        self.vector_store = vector_store or VectorStoreAdapter(settings=self.settings)
        self.fault_service = fault_service or ReplicaFaultService(FaultController())
        self.sync_service = sync_service or SyncService()
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
        return self.cache_service.read(payload)

    def write_cache(self, payload: dict) -> dict:
        return self.cache_service.write(payload)

    def snapshot(self, payload: dict) -> dict:
        return self.sync_service.snapshot(payload)

    def replay(self, payload: dict) -> dict:
        return self.sync_service.replay(payload)

    def arm_fault(self, payload: dict) -> dict:
        return self.fault_service.arm_fault(payload)

    def describe_vector_store(self) -> dict:
        return self.vector_store.describe()

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
