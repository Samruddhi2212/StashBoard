"""Space management API endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Space
from app.schemas import SpaceCreate, SpaceResponse, SpaceUpdate

router = APIRouter()


@router.get("/", response_model=list[SpaceResponse])
async def list_spaces(
    user_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
) -> list[SpaceResponse]:
    """Returns all spaces owned by the user, ordered by sort_order."""
    result = await db.execute(
        select(Space)
        .where(Space.user_id == user_id)
        .order_by(Space.sort_order, Space.created_at)
    )
    return list(result.scalars().all())


@router.post("/", response_model=SpaceResponse, status_code=status.HTTP_201_CREATED)
async def create_space(
    payload: SpaceCreate,
    user_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
) -> SpaceResponse:
    """Creates a new space."""
    space = Space(
        user_id=user_id,
        name=payload.name,
        icon=payload.icon,
        color=payload.color,
    )
    db.add(space)
    await db.flush()
    await db.refresh(space)
    return space


@router.patch("/{space_id}", response_model=SpaceResponse)
async def update_space(
    space_id: uuid.UUID,
    payload: SpaceUpdate,
    user_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
) -> SpaceResponse:
    """Updates space name, icon, or color."""
    result = await db.execute(
        select(Space).where(Space.id == space_id, Space.user_id == user_id)
    )
    space = result.scalar_one_or_none()
    if not space:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Space not found")

    if payload.name is not None:
        space.name = payload.name
    if payload.icon is not None:
        space.icon = payload.icon
    if payload.color is not None:
        space.color = payload.color

    await db.flush()
    await db.refresh(space)
    return space


@router.delete("/{space_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_space(
    space_id: uuid.UUID,
    user_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Deletes a space. Clips in the space are moved to the default (unassigned) state."""
    result = await db.execute(
        select(Space).where(Space.id == space_id, Space.user_id == user_id)
    )
    space = result.scalar_one_or_none()
    if not space:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Space not found")
    if space.is_default:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the default space",
        )

    await db.delete(space)
