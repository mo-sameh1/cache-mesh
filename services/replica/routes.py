from fastapi import APIRouter, Request

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
router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    return HealthResponse(**request.app.state.replica_manager.health())


@router.post("/cache/read", response_model=CacheReadResponse)
def read_cache(request: Request, payload: CacheReadRequest) -> dict:
    return request.app.state.replica_manager.read_cache(payload.model_dump())


@router.post("/cache/write", response_model=CacheWriteResponse)
def write_cache(request: Request, payload: CacheWriteRequest) -> dict:
    return request.app.state.replica_manager.write_cache(payload.model_dump())


@router.post("/sync/snapshot", response_model=SnapshotResponse)
def sync_snapshot(request: Request, payload: SnapshotRequest) -> dict:
    return request.app.state.replica_manager.snapshot(payload.model_dump())


@router.post("/sync/replay", response_model=ReplayResponse)
def sync_replay(request: Request, payload: ReplayRequest) -> dict:
    return request.app.state.replica_manager.replay(payload.model_dump())


@router.post("/admin/faults", response_model=FaultInjectionResponse)
def admin_faults(request: Request, payload: FaultInjectionRequest) -> dict:
    return request.app.state.replica_manager.arm_fault(payload.model_dump())


@router.get("/vector-store", response_model=VectorStoreDescriptionResponse)
def describe_vector_store(request: Request) -> dict:
    return request.app.state.replica_manager.describe_vector_store()

