from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Client, Interaction, Project


def commit_or_conflict(db: Session) -> None:
    """Commit a change and return safe HTTP errors if it fails."""
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This change conflicts with existing database records.",
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="The database could not complete this operation.",
        ) from exc


def get_client_or_404(
    db: Session,
    client_id: int,
    user_id: int,
) -> Client:
    """Return a client only if it belongs to the signed-in user."""
    client = db.scalar(
        select(Client).where(
            Client.id == client_id,
            Client.user_id == user_id,
        )
    )
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found.")
    return client


def get_project_or_404(
    db: Session,
    project_id: int,
    user_id: int,
) -> Project:
    """Return a project only if its client belongs to the signed-in user."""
    project = db.scalar(
        select(Project)
        .join(Client, Project.client_id == Client.id)
        .where(
            Project.id == project_id,
            Client.user_id == user_id,
        )
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project


def get_interaction_or_404(
    db: Session,
    interaction_id: int,
    user_id: int,
) -> Interaction:
    """Return an interaction only if its client belongs to the user."""
    interaction = db.scalar(
        select(Interaction)
        .join(Client, Interaction.client_id == Client.id)
        .where(
            Interaction.id == interaction_id,
            Client.user_id == user_id,
        )
    )
    if interaction is None:
        raise HTTPException(
            status_code=404,
            detail="Interaction not found.",
        )
    return interaction


def validate_interaction_links(
    db: Session,
    client_id: int,
    project_id: int | None,
    user_id: int,
) -> None:
    """Validate that the client and project belong to this workspace."""
    get_client_or_404(db, client_id, user_id)

    if project_id is not None:
        project = get_project_or_404(db, project_id, user_id)

        if project.client_id != client_id:
            raise HTTPException(
                status_code=422,
                detail="The selected project does not belong to this client.",
            )
