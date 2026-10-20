from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.api.common import commit_or_conflict, get_client_or_404
from app.database import get_db
from app.models import Client, User
from app.schemas import ClientCreate, ClientOut, ClientUpdate

router = APIRouter(prefix="/api/clients", tags=["Clients"])


@router.get("", response_model=list[ClientOut])
def list_clients(
    search: str | None = Query(default=None, max_length=150),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    statement = (
        select(Client)
        .where(Client.user_id == current_user.id)
        .order_by(Client.created_at.desc())
    )

    if search and search.strip():
        term = f"%{search.strip()}%"
        statement = statement.where(
            Client.full_name.ilike(term)
            | Client.email.ilike(term)
            | Client.company.ilike(term)
        )

    return db.scalars(statement).all()


@router.get("/{client_id}", response_model=ClientOut)
def read_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_client_or_404(db, client_id, current_user.id)


@router.post("", response_model=ClientOut, status_code=status.HTTP_201_CREATED)
def create_client(
    payload: ClientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    client = Client(
        **payload.model_dump(),
        user_id=current_user.id,
    )
    db.add(client)
    commit_or_conflict(db)
    db.refresh(client)
    return client


@router.patch("/{client_id}", response_model=ClientOut)
def update_client(
    client_id: int,
    payload: ClientUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    client = get_client_or_404(db, client_id, current_user.id)
    changes = payload.model_dump(exclude_unset=True)

    for field, value in changes.items():
        setattr(client, field, value)

    commit_or_conflict(db)
    db.refresh(client)
    return client


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    client = get_client_or_404(db, client_id, current_user.id)
    db.delete(client)
    commit_or_conflict(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
