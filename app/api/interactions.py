from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.api.common import (
    commit_or_conflict,
    get_interaction_or_404,
    validate_interaction_links,
)
from app.database import get_db
from app.models import Client, Interaction, User
from app.schemas import InteractionCreate, InteractionOut, InteractionUpdate

router = APIRouter(prefix="/api/interactions", tags=["Interactions"])


@router.get("", response_model=list[InteractionOut])
def list_interactions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    statement = (
        select(Interaction)
        .join(Client, Interaction.client_id == Client.id)
        .where(Client.user_id == current_user.id)
        .order_by(Interaction.occurred_at.desc())
    )
    return db.scalars(statement).all()


@router.get("/{interaction_id}", response_model=InteractionOut)
def read_interaction(
    interaction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_interaction_or_404(
        db, interaction_id, current_user.id
    )


@router.post(
    "",
    response_model=InteractionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_interaction(
    payload: InteractionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = payload.model_dump(exclude_none=True)

    validate_interaction_links(
        db,
        client_id=data["client_id"],
        project_id=data.get("project_id"),
        user_id=current_user.id,
    )

    if current_user.is_guest:
        interaction_count = db.scalar(
            select(func.count(Interaction.id))
            .join(Client, Interaction.client_id == Client.id)
            .where(Client.user_id == current_user.id)
        )

        if interaction_count >= 20:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "You have reached the 20-interaction limit "
                    "for your guest trial. Create a free account "
                    "to continue."
                ),
            )

    interaction = Interaction(**data)
    db.add(interaction)
    commit_or_conflict(db)
    db.refresh(interaction)
    return interaction


@router.patch("/{interaction_id}", response_model=InteractionOut)
def update_interaction(
    interaction_id: int,
    payload: InteractionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    interaction = get_interaction_or_404(
        db, interaction_id, current_user.id
    )
    changes = payload.model_dump(exclude_unset=True)

    new_client_id = changes.get("client_id", interaction.client_id)
    new_project_id = changes.get("project_id", interaction.project_id)

    validate_interaction_links(
        db,
        client_id=new_client_id,
        project_id=new_project_id,
        user_id=current_user.id,
    )

    for field, value in changes.items():
        setattr(interaction, field, value)

    commit_or_conflict(db)
    db.refresh(interaction)
    return interaction


@router.delete(
    "/{interaction_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_interaction(
    interaction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    interaction = get_interaction_or_404(
        db, interaction_id, current_user.id
    )
    db.delete(interaction)
    commit_or_conflict(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
