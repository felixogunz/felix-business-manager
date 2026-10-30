from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api import auth, clients, dashboard, interactions, projects, diagnostics
from app.database import Base, engine, get_db
from app.models import Client, Interaction, Project


PROJECT_ROOT = Path(__file__).resolve().parent
TEMPLATES_DIR = PROJECT_ROOT / "templates"
STATIC_DIR = PROJECT_ROOT / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not (TEMPLATES_DIR / "index.html").is_file():
        raise RuntimeError(
            f"Frontend template not found: {TEMPLATES_DIR / 'index.html'}"
        )

    if not STATIC_DIR.is_dir():
        raise RuntimeError(f"Static directory not found: {STATIC_DIR}")

    # Create missing tables only; this does not migrate existing tables.
    Base.metadata.create_all(bind=engine)

    yield


app = FastAPI(
    title="Felix Business Manager",
    description=(
        "A business management API for clients, projects, "
        "and client interactions."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.mount(
    "/static",
    StaticFiles(directory=str(STATIC_DIR)),
    name="static",
)


@app.get("/", include_in_schema=False)
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"request": request},
    )


@app.get("/api/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "application": "Felix Business Manager",
    }


@app.get("/api/health/database", tags=["Health"])
def database_health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "database": "connected",
        }
    except Exception:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "database": "unavailable",
            },
        )


from app.api.auth import get_current_user

app.include_router(
    auth.router,
)

app.include_router(
    dashboard.router,
    dependencies=[Depends(get_current_user)],
)

app.include_router(
    clients.router,
    dependencies=[Depends(get_current_user)],
)

app.include_router(
    projects.router,
    dependencies=[Depends(get_current_user)],
)

app.include_router(
    interactions.router,
    dependencies=[Depends(get_current_user)],
)

app.include_router(
    diagnostics.router
)