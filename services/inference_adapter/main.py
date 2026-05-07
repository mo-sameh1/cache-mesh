from fastapi import FastAPI

from services.inference_adapter.config import get_settings
from services.inference_adapter.routes import router
from shared.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=f"{settings.project_name} Inference Adapter",
        version="0.1.0",
        summary="CacheMesh inference adapter scaffold",
    )
    app.include_router(router)
    return app


app = create_app()

