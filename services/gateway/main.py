from fastapi import FastAPI

from services.gateway.config import get_settings
from services.gateway.routes import router
from shared.cors import enable_demo_cors
from shared.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=f"{settings.project_name} Gateway",
        version="0.1.0",
        summary="CacheMesh gateway scaffold",
    )
    enable_demo_cors(app)
    app.include_router(router)
    return app


app = create_app()

