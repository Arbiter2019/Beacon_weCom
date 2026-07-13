from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from wecom_app.api import attachments, callbacks, conversations, health, observable


def create_app() -> FastAPI:
    app = FastAPI(title="WeCom Archive Service", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(observable.router)
    app.include_router(conversations.router)
    app.include_router(attachments.router)
    app.include_router(callbacks.router)
    return app


app = create_app()
