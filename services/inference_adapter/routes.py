from fastapi import APIRouter

from shared.models import HealthResponse, InferRequest
from services.inference_adapter.client import InferenceStubClient


router = APIRouter()
client = InferenceStubClient()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(service="inference-adapter", status="ok", detail="Inference adapter placeholder is running.")


@router.post("/infer")
def infer(request: InferRequest) -> dict:
    return client.infer(request.model_dump())

