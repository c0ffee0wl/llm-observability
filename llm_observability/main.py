"""FastAPI application for LLM Observability."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import settings
from .database import Database, DatabaseError

# Get the package directory for templates and static files
PACKAGE_DIR = Path(__file__).parent
TEMPLATES_DIR = PACKAGE_DIR / "templates"
STATIC_DIR = PACKAGE_DIR / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    # Startup
    app.state.db = Database(settings.db_path)
    try:
        app.state.db.validate()
    except DatabaseError as e:
        print(f"Error: {e}")
        raise
    yield
    # Shutdown
    app.state.db.close()


def create_app(db_path: str = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    if db_path:
        settings.db_path = db_path

    app = FastAPI(
        title="LLM Observability",
        description="Web UI for viewing llm database logs",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Mount static files
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # Setup templates
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    app.state.templates = templates

    # Health check endpoint
    @app.get("/health")
    async def health():
        """Health check endpoint."""
        return {"status": "ok", "database": settings.db_path}

    # Exception handler for database errors
    @app.exception_handler(DatabaseError)
    async def database_error_handler(request: Request, exc: DatabaseError):
        return JSONResponse(
            status_code=500,
            content={"error": str(exc)},
        )

    # Import and include routers
    from .api import conversations as api_conversations
    from .api import metrics as api_metrics
    from .api import responses as api_responses
    from .api import search as api_search
    from .api import tools as api_tools
    from .views import conversations as view_conversations
    from .views import dashboard as view_dashboard
    from .views import responses as view_responses
    from .views import search as view_search

    # API routes
    app.include_router(api_responses.router, prefix="/api", tags=["api"])
    app.include_router(api_conversations.router, prefix="/api", tags=["api"])
    app.include_router(api_tools.router, prefix="/api", tags=["api"])
    app.include_router(api_metrics.router, prefix="/api", tags=["api"])
    app.include_router(api_search.router, prefix="/api", tags=["api"])

    # View routes
    app.include_router(view_dashboard.router, tags=["views"])
    app.include_router(view_responses.router, tags=["views"])
    app.include_router(view_conversations.router, tags=["views"])
    app.include_router(view_search.router, tags=["views"])

    return app


# Default app instance for uvicorn
app = create_app()
