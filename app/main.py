
from contextlib import asynccontextmanager
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.models import Client, Interaction, Project


# ---------- Frontend configuration ----------

APP_DIR = Path(__file__).resolve().parent

TEMPLATES_DIR = APP_DIR / "templates"
STATIC_DIR = APP_DIR / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# ---------- Application startup ----------

@asynccontextmanager
async def lifespan(app: FastAPI):
    if not (TEMPLATES_DIR / "index.html").is_file():
        raise RuntimeError(
            f"Frontend index.html was not found in {TEMPLATES_DIR}"
        )

    if not STATIC_DIR.is_dir():
        raise RuntimeError(
            f"Static directory was not found in {STATIC_DIR}"
        )

    Base.metadata.create_all(bind=engine)

    try:
        yield
    finally:
        engine.dispose()


app = FastAPI(
    title="Felix Business Manager",
    description="Manage clients, projects, and business interactions.",
    version="1.0.0",
    lifespan=lifespan,
)

# Serve CSS, JavaScript, images and other static assets.
app.mount(
    "/static",
    StaticFiles(directory=str(STATIC_DIR)),
    name="static",
)


# ---------- Request and response schemas ----------

class ClientCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=150)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=30)
    company: str | None = Field(default=None, max_length=150)
    notes: str | None = None


class ClientUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=150)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=30)
    company: str | None = Field(default=None, max_length=150)
    notes: str | None = None


class ClientOut(ClientCreate):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProjectCreate(BaseModel):
    client_id: int
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    status: str = Field(
        default="planned",
        pattern=r"^(planned|in_progress|completed|on_hold)$",
    )
    budget: Decimal | None = Field(default=None, ge=0)
    due_date: date | None = None


class ProjectUpdate(BaseModel):
    client_id: int | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    status: str | None = Field(
        default=None,
        pattern=r"^(planned|in_progress|completed|on_hold)$",
    )
    budget: Decimal | None = Field(default=None, ge=0)
    due_date: date | None = None


class ProjectOut(ProjectCreate):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InteractionCreate(BaseModel):
    client_id: int
    project_id: int | None = None
    interaction_type: str = Field(
        pattern=r"^(call|meeting|email|note)$"
    )
    subject: str = Field(min_length=1, max_length=200)
    details: str | None = None
    occurred_at: datetime | None = None


class InteractionUpdate(BaseModel):
    client_id: int | None = None
    project_id: int | None = None
    interaction_type: str | None = Field(
        default=None,
        pattern=r"^(call|meeting|email|note)$",
    )
    subject: str | None = Field(default=None, min_length=1, max_length=200)
    details: str | None = None
    occurred_at: datetime | None = None


class InteractionOut(BaseModel):
    id: int
    client_id: int
    project_id: int | None
    interaction_type: str
    subject: str
    details: str | None
    occurred_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------- Shared helpers ----------

def commit_or_conflict(db: Session, message: str) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=message,
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="The database could not save the changes.",
        ) from exc


def get_client_or_404(db: Session, client_id: int) -> Client:
    client = db.get(Client, client_id)

    if client is None:
        raise HTTPException(
            status_code=404,
            detail="Client not found",
        )

    return client


def get_project_or_404(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)

    if project is None:
        raise HTTPException(
            status_code=404,
            detail="Project not found",
        )

    return project


def validate_interaction_links(
    db: Session,
    client_id: int,
    project_id: int | None,
) -> None:
    get_client_or_404(db, client_id)

    if project_id is not None:
        project = get_project_or_404(db, project_id)

        if project.client_id != client_id:
            raise HTTPException(
                status_code=400,
                detail="The selected project does not belong to this client.",
            )


# ---------- Website and health ----------

@app.get("/", include_in_schema=False)
def homepage(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={},
    )


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "application": "Felix Business Manager",
    }


@app.get("/api/health/database")
def database_health_check():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "status": "connected",
            "database": "felix_business_manager",
        }

    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="Database connection failed. Check the local configuration.",
        ) from exc


# ---------- Dashboard ----------

@app.get("/api/dashboard")
def dashboard(db: Session = Depends(get_db)):
    client_count = db.scalar(
        select(func.count()).select_from(Client)
    ) or 0

    project_count = db.scalar(
        select(func.count()).select_from(Project)
    ) or 0

    interaction_count = db.scalar(
        select(func.count()).select_from(Interaction)
    ) or 0

    active_projects = db.scalar(
        select(func.count())
        .select_from(Project)
        .where(Project.status == "in_progress")
    ) or 0

    recent = db.scalars(
        select(Interaction)
        .order_by(Interaction.occurred_at.desc())
        .limit(5)
    ).all()

    return {
        "clients": client_count,
        "projects": project_count,
        "interactions": interaction_count,
        "active_projects": active_projects,
        "recent_interactions": [
            {
                "id": item.id,
                "client_id": item.client_id,
                "project_id": item.project_id,
                "interaction_type": item.interaction_type,
                "subject": item.subject,
                "details": item.details,
                "occurred_at": item.occurred_at,
            }
            for item in recent
        ],
    }


# ---------- Clients CRUD ----------

@app.get("/api/clients", response_model=list[ClientOut])
def list_clients(
    search: str | None = Query(default=None, max_length=150),
    db: Session = Depends(get_db),
):
    statement = select(Client).order_by(Client.created_at.desc())

    if search and search.strip():
        term = f"%{search.strip()}%"
        statement = statement.where(
            or_(
                Client.full_name.ilike(term),
                Client.email.ilike(term),
                Client.company.ilike(term),
            )
        )

    return db.scalars(statement).all()


@app.post("/api/clients", response_model=ClientOut, status_code=201)
def create_client(
    payload: ClientCreate,
    db: Session = Depends(get_db),
):
    values = payload.model_dump()
    values["full_name"] = values["full_name"].strip()

    if not values["full_name"]:
        raise HTTPException(
            status_code=422,
            detail="Client name cannot be empty.",
        )

    client = Client(**values)
    db.add(client)

    commit_or_conflict(
        db,
        "A client with that email may already exist.",
    )

    db.refresh(client)
    return client


@app.get("/api/clients/{client_id}", response_model=ClientOut)
def get_client(
    client_id: int,
    db: Session = Depends(get_db),
):
    return get_client_or_404(db, client_id)


@app.patch("/api/clients/{client_id}", response_model=ClientOut)
def update_client(
    client_id: int,
    payload: ClientUpdate,
    db: Session = Depends(get_db),
):
    client = get_client_or_404(db, client_id)
    changes = payload.model_dump(exclude_unset=True)

    if "full_name" in changes and changes["full_name"] is not None:
        changes["full_name"] = changes["full_name"].strip()

        if not changes["full_name"]:
            raise HTTPException(
                status_code=422,
                detail="Client name cannot be empty.",
            )

    for field, value in changes.items():
        setattr(client, field, value)

    commit_or_conflict(
        db,
        "A client with that email may already exist.",
    )

    db.refresh(client)
    return client


@app.delete("/api/clients/{client_id}")
def delete_client(
    client_id: int,
    db: Session = Depends(get_db),
):
    client = get_client_or_404(db, client_id)
    db.delete(client)

    commit_or_conflict(
        db,
        "The client could not be deleted.",
    )

    return {"message": "Client deleted successfully"}


# ---------- Projects CRUD ----------

@app.get("/api/projects", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    return db.scalars(
        select(Project).order_by(Project.created_at.desc())
    ).all()


@app.post("/api/projects", response_model=ProjectOut, status_code=201)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
):
    get_client_or_404(db, payload.client_id)

    values = payload.model_dump()
    values["title"] = values["title"].strip()

    if not values["title"]:
        raise HTTPException(
            status_code=422,
            detail="Project title cannot be empty.",
        )

    project = Project(**values)
    db.add(project)

    commit_or_conflict(db, "The project could not be saved.")

    db.refresh(project)
    return project


@app.get("/api/projects/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
):
    return get_project_or_404(db, project_id)


@app.patch("/api/projects/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
):
    project = get_project_or_404(db, project_id)
    changes = payload.model_dump(exclude_unset=True)

    if changes.get("client_id") is not None:
        get_client_or_404(db, changes["client_id"])

    if "title" in changes and changes["title"] is not None:
        changes["title"] = changes["title"].strip()

        if not changes["title"]:
            raise HTTPException(
                status_code=422,
                detail="Project title cannot be empty.",
            )

    for field, value in changes.items():
        setattr(project, field, value)

    commit_or_conflict(db, "The project could not be updated.")

    db.refresh(project)
    return project


@app.delete("/api/projects/{project_id}")
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
):
    project = get_project_or_404(db, project_id)
    db.delete(project)

    commit_or_conflict(db, "The project could not be deleted.")

    return {"message": "Project deleted successfully"}


# ---------- Client interaction history ----------

@app.get("/api/interactions", response_model=list[InteractionOut])
def list_interactions(
    client_id: int | None = None,
    db: Session = Depends(get_db),
):
    statement = select(Interaction).order_by(
        Interaction.occurred_at.desc()
    )

    if client_id is not None:
        statement = statement.where(
            Interaction.client_id == client_id
        )

    return db.scalars(statement).all()


@app.post(
    "/api/interactions",
    response_model=InteractionOut,
    status_code=201,
)
def create_interaction(
    payload: InteractionCreate,
    db: Session = Depends(get_db),
):
    data = payload.model_dump()

    # Allow the database's timestamp default to apply when omitted or null.
    if data["occurred_at"] is None:
        data.pop("occurred_at")

    validate_interaction_links(
        db,
        data["client_id"],
        data["project_id"],
    )

    if not data["subject"].strip():
        raise HTTPException(
            status_code=422,
            detail="Interaction subject cannot be empty.",
        )

    data["subject"] = data["subject"].strip()

    interaction = Interaction(**data)
    db.add(interaction)

    commit_or_conflict(db, "The interaction could not be saved.")

    db.refresh(interaction)
    return interaction


@app.patch(
    "/api/interactions/{interaction_id}",
    response_model=InteractionOut,
)
def update_interaction(
    interaction_id: int,
    payload: InteractionUpdate,
    db: Session = Depends(get_db),
):
    interaction = db.get(Interaction, interaction_id)

    if interaction is None:
        raise HTTPException(
            status_code=404,
            detail="Interaction not found",
        )

    changes = payload.model_dump(exclude_unset=True)

    client_id = changes.get("client_id", interaction.client_id)
    project_id = changes.get("project_id", interaction.project_id)

    validate_interaction_links(db, client_id, project_id)

    if "subject" in changes and changes["subject"] is not None:
        changes["subject"] = changes["subject"].strip()

        if not changes["subject"]:
            raise HTTPException(
                status_code=422,
                detail="Interaction subject cannot be empty.",
            )

    # Explicit null means use the database's default timestamp.
    if changes.get("occurred_at", object()) is None:
        changes.pop("occurred_at")

    for field, value in changes.items():
        setattr(interaction, field, value)

    commit_or_conflict(db, "The interaction could not be updated.")

    db.refresh(interaction)
    return interaction


@app.delete("/api/interactions/{interaction_id}")
def delete_interaction(
    interaction_id: int,
    db: Session = Depends(get_db),
):
    interaction = db.get(Interaction, interaction_id)

    if interaction is None:
        raise HTTPException(
            status_code=404,
            detail="Interaction not found",
        )

    db.delete(interaction)

    commit_or_conflict(db, "The interaction could not be deleted.")

    return {"message": "Interaction deleted successfully"}
