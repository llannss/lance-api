"""Favorite GPUs saved to the signed-in account.

Every route takes the account from the login token, never from the
request, so nobody can read or change another account's favorites.
"""

from fastapi import APIRouter, Depends, HTTPException, Path, Response
from pydantic import BaseModel

from database import (
    FavoriteRepository,
    GPURepository,
    get_favorite_repository,
    get_repository,
)
from models import GPU, MAX_ID
from security import get_current_user

router = APIRouter(prefix="/me/favorites", tags=["Favorites"])

MAX_FAVORITES = 200
GpuId = Path(ge=1, le=MAX_ID, description="The ID of the GPU.")


class FavoriteList(BaseModel):
    count: int
    gpu_ids: list[int]
    gpus: list[GPU]


@router.get("", response_model=FavoriteList)
def list_favorites(
    user: dict = Depends(get_current_user),
    favorites: FavoriteRepository = Depends(get_favorite_repository),
    gpus: GPURepository = Depends(get_repository),
):
    """The account's favorite GPUs, newest first."""
    ids = favorites.list_ids(user["id"])
    by_id = {g["id"]: g for g in gpus.get_many(ids)}
    ordered = [by_id[i] for i in ids if i in by_id]
    return {"count": len(ordered), "gpu_ids": [g["id"] for g in ordered], "gpus": ordered}


@router.put("/{gpu_id}", status_code=204)
def add_favorite(
    gpu_id: int = GpuId,
    user: dict = Depends(get_current_user),
    favorites: FavoriteRepository = Depends(get_favorite_repository),
    gpus: GPURepository = Depends(get_repository),
):
    """Save a GPU as a favorite. Saving it again is harmless."""
    if gpus.get(gpu_id) is None:
        raise HTTPException(status_code=404, detail="GPU not found.")
    current = favorites.list_ids(user["id"])
    if gpu_id not in current and len(current) >= MAX_FAVORITES:
        raise HTTPException(status_code=409, detail=f"You can save up to {MAX_FAVORITES} favorites.")
    favorites.add(user["id"], gpu_id)
    return Response(status_code=204)


@router.delete("/{gpu_id}", status_code=204)
def remove_favorite(
    gpu_id: int = GpuId,
    user: dict = Depends(get_current_user),
    favorites: FavoriteRepository = Depends(get_favorite_repository),
):
    """Remove a favorite. Removing one that isn't saved is harmless."""
    favorites.remove(user["id"], gpu_id)
    return Response(status_code=204)
