from fastapi import APIRouter

from shared.models import (
    CacheReadRequest,
    CacheReadResponse,
    CacheWriteRequest,
    CacheWriteResponse,
    FaultInjectionRequest,
    FaultInjectionResponse,
    HealthResponse,
    ReplayRequest,
    ReplayResponse,
    SnapshotRequest,
    SnapshotResponse,
    VectorStoreDescriptionResponse,
)
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


@router.post("/cache/read", response_model=CacheReadResponse)
def read_cache(request: CacheReadRequest) -> dict:
    return cache_service.read(request.model_dump())


@router.post("/cache/write", response_model=CacheWriteResponse)
def write_cache(request: CacheWriteRequest) -> dict:
    return cache_service.write(request.model_dump())


@router.post("/sync/snapshot", response_model=SnapshotResponse)
def sync_snapshot(request: SnapshotRequest) -> dict:
    return sync_service.snapshot(request.model_dump())


@router.post("/sync/replay", response_model=ReplayResponse)
def sync_replay(request: ReplayRequest) -> dict:
    return sync_service.replay(request.model_dump())


@router.post("/admin/faults", response_model=FaultInjectionResponse)
def admin_faults(request: FaultInjectionRequest) -> dict:
    return fault_service.arm_fault(request.model_dump())


@router.get("/vector-store", response_model=VectorStoreDescriptionResponse)
def describe_vector_store() -> dict:
    return vector_store.describe()

