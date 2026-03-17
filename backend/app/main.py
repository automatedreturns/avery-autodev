from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.api.v1 import (
    agent_chat,
    agent_jobs,
    auth,
    ci_runs,
    coder_agent,
    contact,
    coverage,
    github,
    issue_polling,
    subscriptions,
    test_generation,
    test_policy,
    test_runs,
    test_suites,
    users,
    workspaces,
    workspace_tasks,
)
from app.core.config import settings
from app.database import Base, engine
from app.engine.plugins import get_plugin, load_plugin
from app.services.scheduler_service import start_scheduler, stop_scheduler


class ProxyHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to handle proxy headers (X-Forwarded-Proto, X-Forwarded-Host)."""

    async def dispatch(self, request: Request, call_next):
        # Update the request scope to use the forwarded protocol
        if "x-forwarded-proto" in request.headers:
            request.scope["scheme"] = request.headers["x-forwarded-proto"]

        if "x-forwarded-host" in request.headers:
            request.scope["server"] = (request.headers["x-forwarded-host"], None)

        response = await call_next(request)
        return response


def _ensure_columns() -> None:
    """Add any missing columns to existing tables.

    SQLAlchemy's create_all() only creates missing tables — it does NOT
    add new columns to tables that already exist.  This helper inspects
    the live schema and issues ALTER TABLE statements for any columns
    defined in the ORM models but absent from the database.

    Works with both SQLite and PostgreSQL.
    """
    import logging
    from sqlalchemy import inspect as sa_inspect, text

    log = logging.getLogger(__name__)
    is_sqlite = settings.DATABASE_URL.startswith("sqlite")

    with engine.connect() as conn:
        inspector = sa_inspect(conn)

        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue  # table doesn't exist yet; create_all handles it

            existing = {col["name"] for col in inspector.get_columns(table.name)}

            for column in table.columns:
                if column.name in existing:
                    continue

                col_type = column.type.compile(dialect=engine.dialect)

                # Resolve default value from server_default or Python-level default
                default_val = None
                if column.server_default is not None:
                    default_val = column.server_default.arg
                elif column.default is not None and column.default.is_scalar:
                    default_val = column.default.arg

                default = f" DEFAULT {default_val!r}" if default_val is not None else ""

                # SQLite: NOT NULL requires a DEFAULT value in ALTER TABLE.
                # PostgreSQL: supports NOT NULL + DEFAULT natively.
                if not column.nullable and default:
                    nullable = " NOT NULL"
                elif not column.nullable and not is_sqlite:
                    # PostgreSQL allows NOT NULL without DEFAULT if we backfill
                    nullable = ""
                else:
                    nullable = ""

                stmt = f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {col_type}{default}{nullable}'
                try:
                    conn.execute(text(stmt))
                    log.info(f"Added column {table.name}.{column.name}")

                    # Backfill NULL rows with default for NOT NULL columns
                    # (covers SQLite where NOT NULL was skipped, and fresh adds)
                    if default_val is not None and not column.nullable:
                        conn.execute(
                            text(
                                f'UPDATE "{table.name}" SET "{column.name}" = :val '
                                f'WHERE "{column.name}" IS NULL'
                            ),
                            {"val": default_val},
                        )
                except Exception as exc:
                    log.warning(f"Could not add column {table.name}.{column.name}: {exc}")

        conn.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    Creates database tables on startup and starts background scheduler.
    """
    # Startup: Load plugin system
    load_plugin(settings.AVERY_PLUGIN_CLASS or None)

    # Startup: Create database tables and add any missing columns
    Base.metadata.create_all(bind=engine)
    _ensure_columns()

    # Start background issue polling (polls every 5 minutes)
    start_scheduler(poll_interval_minutes=5)

    yield

    # Shutdown: Stop background scheduler
    stop_scheduler()


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AutoDev - Open-source AI coding agent engine",
    lifespan=lifespan,
    root_path_in_servers=False,
)

# Add session middleware for OAuth (must be added first)
# Use SESSION_SECRET_KEY if provided, otherwise fall back to SECRET_KEY
session_secret = settings.SESSION_SECRET_KEY or settings.SECRET_KEY
app.add_middleware(SessionMiddleware, secret_key=session_secret)

# Add proxy headers middleware (must be added before CORS)
app.add_middleware(ProxyHeadersMiddleware)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(github.router, prefix="/api/v1")
app.include_router(workspaces.router, prefix="/api/v1")
app.include_router(workspace_tasks.router, prefix="/api/v1/workspaces")
app.include_router(coder_agent.router, prefix="/api/v1/workspaces")
app.include_router(agent_chat.router, prefix="/api/v1/workspaces")
app.include_router(agent_jobs.router, prefix="/api/v1/workspaces", tags=["agent-jobs"])
app.include_router(issue_polling.router, prefix="/api/v1/workspaces", tags=["issue-polling"])
app.include_router(test_suites.router, prefix="/api/v1/workspaces")
app.include_router(test_runs.router, prefix="/api/v1/workspaces")
app.include_router(ci_runs.router, prefix="/api/v1")
app.include_router(subscriptions.router, prefix="/api/v1")
app.include_router(contact.router, prefix="/api/v1")

# Phase 2: Test-Aware Agent API endpoints
app.include_router(test_policy.router, prefix="/api/v1/workspaces", tags=["test-policy"])
app.include_router(coverage.router, prefix="/api/v1", tags=["coverage"])
app.include_router(test_generation.router, prefix="/api/v1", tags=["test-generation"])


@app.get("/")
def root():
    """Root endpoint."""
    return {
        "message": "Welcome to AutoDev API",
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "redoc": "/redoc"
    }


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/api/v1/dashboard/extras")
def dashboard_extras():
    """Return plugin-provided dashboard widgets (empty in CE)."""
    plugin = get_plugin()
    return {"extras": plugin.get_dashboard_extras(), "edition": settings.AVERY_EDITION}
