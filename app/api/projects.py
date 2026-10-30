from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.api.common import (
    commit_or_conflict,
    get_client_or_404,
    get_project_or_404,
)
from app.database import get_db
from app.models import Client, Project, User
from app.schemas import ProjectCreate, ProjectOut, ProjectUpdate

router = APIRouter(prefix="/api/projects", tags=["Projects"])


@router.get("", response_model=list[ProjectOut])
def list_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    statement = (
        select(Project)
        .join(Client, Project.client_id == Client.id)
        .where(Client.user_id == current_user.id)
        .order_by(Project.created_at.desc())
    )
    return db.scalars(statement).all()


@router.get("/{project_id}", response_model=ProjectOut)
def read_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_project_or_404(db, project_id, current_user.id)


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_client_or_404(db, payload.client_id, current_user.id)

    if current_user.is_guest:
        project_count = db.scalar(
            select(func.count(Project.id))
            .join(Client, Project.client_id == Client.id)
            .where(Client.user_id == current_user.id)
        )

        if project_count >= 5:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "You have reached the 5-project limit "
                    "for your guest trial. Create a free account "
                    "to continue."
                ),
            )

    project = Project(**payload.model_dump())
    db.add(project)
    commit_or_conflict(db)
    db.refresh(project)
    return project


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = get_project_or_404(db, project_id, current_user.id)
    changes = payload.model_dump(exclude_unset=True)

    new_client_id = changes.get("client_id", project.client_id)
    if new_client_id is not None:
        get_client_or_404(db, new_client_id, current_user.id)

    for field, value in changes.items():
        setattr(project, field, value)

    commit_or_conflict(db)
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = get_project_or_404(db, project_id, current_user.id)
    db.delete(project)
    commit_or_conflict(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
