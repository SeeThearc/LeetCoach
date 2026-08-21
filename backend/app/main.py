"""FastAPI application entry point.

This is the top-level module that:
1. Creates the FastAPI application instance
2. Configures middleware (CORS, request ID)
3. Registers exception handlers
4. Includes API routers
5. Manages application lifecycle (startup/shutdown)

The lifespan context manager pattern (replacing @app.on_event)
is the modern way to handle startup/shutdown in FastAPI.
It ensures resources are properly initialized before serving
requests and cleaned up when the server stops.
"""

import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import v1_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager.

    This runs ONCE when the server starts and ONCE when it stops.
    Use it for expensive one-time setup (DB connections, ML models, etc.)

    Why lifespan instead of @app.on_event("startup")?
    - @app.on_event is deprecated in modern FastAPI
    - lifespan provides a clean context manager pattern
    - Resources created in startup are guaranteed to be cleaned up in shutdown
    - The 'yield' clearly separates startup from shutdown logic
    """
    settings = get_settings()

    # --- STARTUP ---
    setup_logging(
        environment=settings.environment,
        debug=settings.debug,
    )
    logger.info(
        "Starting application",
        app_name=settings.app_name,
        environment=settings.environment,
        debug=settings.debug,
    )

    yield  # Application runs here

    # --- SHUTDOWN ---
    logger.info("Shutting down application")


def create_app() -> FastAPI:
    """Application factory function.

    Why a factory function instead of a module-level 'app = FastAPI()'?
    - Testability: create fresh app instances for each test
    - Configuration: pass different settings (test vs prod)
    - Delayed initialization: import-time side effects are minimized
    - Multiple instances: useful for multi-process deployments

    Returns:
        Configured FastAPI application ready to serve requests.
    """
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description=(
            "AI-powered LeetCode coaching backend. "
            "Provides personalized tutoring through a LangGraph workflow "
            "powered by Google Gemini."
        ),
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,  # Disable Swagger in prod
        redoc_url="/redoc" if settings.debug else None,
    )

    # --- Middleware ---
    # CORS: Allow the Chrome Extension to make requests to our API
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request ID middleware: attach a unique ID to every request for tracing
    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        """Attach a unique request ID for distributed tracing.

        The ID is:
        - Generated if not provided by the client
        - Bound to structlog context for all log entries in this request
        - Returned in the X-Request-ID response header
        """
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        # Bind request_id to all log entries for this request
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    # --- Exception Handlers ---
    register_exception_handlers(app)

    # --- Routers ---
    app.include_router(v1_router)

    return app


# Create the application instance
# This is what uvicorn points to: uvicorn app.main:app
app = create_app()
