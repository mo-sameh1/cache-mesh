from fastapi import APIRouter

from shared.models import CacheQueryRequest, CacheWriteRequest, FaultInjectionRequest, HealthResponse
from services.gateway.service import GatewayService


router = APIRouter()
service = GatewayService()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(service="gateway", status="ok", detail="Gateway placeholder is running.")


@router.post("/cache/query")
def query_cache(request: CacheQueryRequest) -> dict:
    return service.query_cache(request.model_dump())


@router.post("/cache/write")
def write_cache(request: CacheWriteRequest) -> dict:
    return service.write_cache(request.model_dump())


@router.post("/admin/faults/{replica_id}")
def arm_fault(replica_id: str, request: FaultInjectionRequest) -> dict:
    return service.arm_fault(replica_id, request.model_dump())
