from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from pydantic import BaseModel, Field

from ..db import connection
from ..deps import current_user, require_language
from ..schemas import DeleteResult, UploadResult, WordOut, WordPage
from ..services import vocab

router = APIRouter(prefix="/words", tags=["words"])


class WordIn(BaseModel):
    language: str
    word: str
    meaning: str | None = None


class WordPatch(BaseModel):
    word: str | None = None
    meaning: str | None = None


class DeleteBody(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)


@router.get("", response_model=WordPage)
def list_words(request: Request, language: str, q: str | None = None, limit: int = Query(50, ge=1, le=200),
               offset: int = Query(0, ge=0), user: dict = Depends(current_user)):
    require_language(language)
    with connection(request.app.state.pool) as conn:
        return vocab.list_words(conn, user["id"], language, q, limit, offset)


@router.post("", status_code=201, response_model=WordOut)
def add_word(body: WordIn, request: Request, user: dict = Depends(current_user)):
    require_language(body.language)
    with connection(request.app.state.pool) as conn:
        return vocab.add_word(conn, user["id"], body.language, body.word, body.meaning)


@router.patch("/{word_id}", response_model=WordOut)
def patch_word(word_id: int, body: WordPatch, request: Request, user: dict = Depends(current_user)):
    fields = body.model_dump(exclude_unset=True)
    with connection(request.app.state.pool) as conn:
        return vocab.update_word(conn, user["id"], word_id, fields)


@router.post("/delete", response_model=DeleteResult)
def delete_words(body: DeleteBody, request: Request, user: dict = Depends(current_user)):
    with connection(request.app.state.pool) as conn:
        return {"deleted": vocab.delete_words(conn, user["id"], body.ids)}


@router.post("/upload", response_model=UploadResult)
def upload(request: Request, language: str = Form(...), file: UploadFile = File(...), user: dict = Depends(current_user)):
    require_language(language)
    s = request.app.state.settings
    raw = file.file.read(s.upload_max_bytes + 1)
    rows = vocab.parse_csv(raw, s.upload_max_bytes, s.upload_max_rows)
    with connection(request.app.state.pool) as conn:
        return vocab.bulk_add(conn, user["id"], language, rows)
