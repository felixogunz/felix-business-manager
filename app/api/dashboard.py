from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.database import get_db
from app.models import Client, Interaction, Project, User

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("")
def dashboard_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    owned_clients = select(Client.id).where(
        Client.user_id == current_user.id
    )

    owned_projects = (
        select(Project.id)
        .join(Client, Project.client_id == Client.id)
        .where(Client.user_id == current_user.id)
    )

    owned_interactions = (
        select(Interaction.id)
        .join(Client, Interaction.client_id == Client.id)
        .where(Client.user_id == current_user.id)
    )

    total_clients = db.scalar(
        select(func.count()).select_from(Client).where(
            Client.user_id == current_user.id
        )
    ) or 0

    total_projects = db.scalar(
        select(func.count()).select_from(Project).where(
            Project.id.in_(owned_projects)
        )
    ) or 0

    active_projects = db.scalar(
        select(func.count())
        .select_from(Project)
        .where(
            Project.id.in_(owned_projects),
            Project.status == "in_progress",
        )
    ) or 0

    total_interactions = db.scalar(
        select(func.count())
        .select_from(Interaction)
        .where(Interaction.id.in_(owned_interactions))
    ) or 0

    recent_interactions = db.scalars(
        select(Interaction)
        .where(Interaction.id.in_(owned_interactions))
        .order_by(Interaction.occurred_at.desc())
        .limit(5)
    ).all()

    return {
        "clients": total_clients,
        "projects": total_projects,
        "active_projects": active_projects,
        "interactions": total_interactions,
        "recent_interactions": recent_interactions,
    }
