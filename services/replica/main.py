from contextlib import asynccontextmanager

from fastapi import FastAPI

from services.replica.config import get_settings
from services.replica.manager import ReplicaManager
from services.replica.routes import router
from shared.logging import configure_logging


def create_app(replica_manager: ReplicaManager | None = None) -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    manager = replica_manager or ReplicaManager(settings=settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.replica_manager = manager
        await manager.start()
        try:
            yield
        finally:
            await manager.stop()

    app = FastAPI(
        title=f"{settings.project_name} Replica {settings.replica_id}",
        version="0.1.0",
        summary="CacheMesh replica scaffold",
        lifespan=lifespan,
    )
    app.include_router(router)
    return app


app = create_app()

