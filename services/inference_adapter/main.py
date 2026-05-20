from contextlib import asynccontextmanager

from fastapi import FastAPI

from services.inference_adapter.config import get_settings
from services.inference_adapter.routes import router
from services.inference_adapter.service import InferenceService
from shared.cors import enable_demo_cors
from shared.logging import configure_logging


def create_app(inference_service: InferenceService | None = None) -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    service = inference_service or InferenceService(settings=settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.inference_service = service
        service.start()
        try:
            yield
        finally:
            service.stop()

    app = FastAPI(
        title=f"{settings.project_name} Inference Adapter",
        version="0.1.0",
        summary="CacheMesh inference adapter scaffold",
        lifespan=lifespan,
    )
    enable_demo_cors(app)
    app.include_router(router)
    return app


app = create_app()

