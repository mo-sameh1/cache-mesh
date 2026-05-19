from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from shared.models import HealthResponse, InferRequest, InferResponse
from services.inference_adapter.runtime import InferenceRuntimeError


router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    return HealthResponse(**request.app.state.inference_service.health())


@router.post("/infer", response_model=InferResponse)
def infer(request: Request, payload: InferRequest) -> dict:
    try:
        return request.app.state.inference_service.infer(payload.model_dump())
    except InferenceRuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/infer/stream")
def infer_stream(request: Request, payload: InferRequest) -> StreamingResponse:
    return StreamingResponse(
        request.app.state.inference_service.stream_sse(payload.model_dump()),
        media_type="text/event-stream",
    )

