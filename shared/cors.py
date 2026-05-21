from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def enable_demo_cors(app: FastAPI) -> None:
    """Allow the static demo console to call service APIs across local ports."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
