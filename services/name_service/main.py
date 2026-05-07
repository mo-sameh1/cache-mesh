from fastapi import FastAPI

from services.name_service.config import get_settings
from services.name_service.routes import router
from shared.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=f"{settings.project_name} Name Service",
        version="0.1.0",
        summary="CacheMesh name service scaffold",
    )
    app.include_router(router)
    return app


app = create_app()

