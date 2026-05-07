from fastapi import APIRouter

from shared.models import CacheReadRequest, CacheWriteRequest, FaultInjectionRequest, HealthResponse, ReplayRequest, SnapshotRequest
from services.replica.cache_service import CacheService
from services.replica.fault_service import ReplicaFaultService
from services.replica.sync_service import SyncService
from services.replica.vector_store import VectorStoreAdapter


router = APIRouter()
cache_service = CacheService()
sync_service = SyncService()
fault_service = ReplicaFaultService()
vector_store = VectorStoreAdapter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(service="replica", status="ok", detail="Replica placeholder is running.")


@router.post("/cache/read")
def read_cache(request: CacheReadRequest) -> dict:
    return cache_service.read(request.model_dump())


@router.post("/cache/write")
def write_cache(request: CacheWriteRequest) -> dict:
    return cache_service.write(request.model_dump())


@router.post("/sync/snapshot")
def sync_snapshot(request: SnapshotRequest) -> dict:
    return sync_service.snapshot(request.model_dump())


@router.post("/sync/replay")
def sync_replay(request: ReplayRequest) -> dict:
    return sync_service.replay(request.model_dump())


@router.post("/admin/faults")
def admin_faults(request: FaultInjectionRequest) -> dict:
    return fault_service.arm_fault(request.model_dump())


@router.get("/vector-store")
def describe_vector_store() -> dict:
    return vector_store.describe()

