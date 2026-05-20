from fastapi import APIRouter, Depends, Request

from shared.models import (
    HealthResponse,
    HeartbeatRequest,
    HeartbeatResponse,
    MembersResponse,
    RegisterNodeRequest,
    RegisterNodeResponse,
)
from services.name_service.registry import MembershipRegistry


router = APIRouter()
registry = MembershipRegistry()


def _get_registry(request: Request) -> MembershipRegistry:
    """Retrieve the per-app registry from app.state (set by create_app)."""
    return getattr(request.app.state, "registry", registry)


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(service="name-service", status="ok", detail="Name service is running.")


@router.post("/register", response_model=RegisterNodeResponse)
def register(
    request: RegisterNodeRequest,
    registry: MembershipRegistry = Depends(_get_registry),
) -> dict:
    return registry.register(request.model_dump())


@router.post("/heartbeat", response_model=HeartbeatResponse)
def heartbeat(
    request: HeartbeatRequest,
    registry: MembershipRegistry = Depends(_get_registry),
) -> dict:
    return registry.heartbeat(request.model_dump())


@router.get("/members", response_model=MembersResponse)
def members(registry: MembershipRegistry = Depends(_get_registry)) -> dict:
    return registry.list_members()


@router.get("/healthy-members", response_model=MembersResponse)
def healthy_members(registry: MembershipRegistry = Depends(_get_registry)) -> dict:
    """Return only replicas currently in the healthy state.

    Callers (e.g. the gateway) can use this to route traffic without
    needing to understand the internal heartbeat algorithm.
    """
    return registry.list_members(healthy_only=True)
