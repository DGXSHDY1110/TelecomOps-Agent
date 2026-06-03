"""FastAPI application factory — creates and configures the FastAPI app."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.telecomops_agent.api.routes import router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="TelecomOps-Agent API",
        description="LangGraph + GraphRAG telecom operation diagnosis agent",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)

    return app


app = create_app()
