from fastapi import FastAPI

from services.replica.config import get_settings
from services.replica.routes import router
from shared.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=f"{settings.project_name} Replica {settings.replica_id}",
        version="0.1.0",
        summary="CacheMesh replica scaffold",
    )
    app.include_router(router)
    return app


app = create_app()

