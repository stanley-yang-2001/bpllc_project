from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from ..db import connection
from ..deps import current_user, require_language
from ..schemas import SetList, SetOut
from ..services import word_sets

router = APIRouter(prefix="/sets", tags=["sets"])


class SetIn(BaseModel):
    language: str
    name: str = Field(max_length=200)


class SetRename(BaseModel):
    name: str = Field(max_length=200)


@router.get("", response_model=SetList)
def list_sets(request: Request, language: str, user: dict = Depends(current_user)):
    require_language(language)
    with connection(request.app.state.pool) as conn:
        return word_sets.list_sets(conn, user["id"], language)


@router.post("", status_code=201, response_model=SetOut)
def create_set(body: SetIn, request: Request, user: dict = Depends(current_user)):
    require_language(body.language)
    with connection(request.app.state.pool) as conn:
        return word_sets.create(conn, user["id"], body.language, body.name)


@router.patch("/{set_id}", response_model=SetOut)
def rename_set(set_id: int, body: SetRename, request: Request, user: dict = Depends(current_user)):
    with connection(request.app.state.pool) as conn:
        return word_sets.rename(conn, user["id"], set_id, body.name)


@router.delete("/{set_id}")
def delete_set(set_id: int, request: Request, user: dict = Depends(current_user)):
    """Its words go back to General; none are deleted."""
    with connection(request.app.state.pool) as conn:
        return {"moved_to_general": word_sets.delete(conn, user["id"], set_id)}
