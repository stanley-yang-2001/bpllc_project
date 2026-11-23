from __future__ import annotations

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile

from ..db import connection
from ..deps import current_user
from ..schemas import EmojiIn, PictureOut
from ..services import pictures

router = APIRouter(prefix="/words", tags=["pictures"])


@router.put("/{word_id}/picture/emoji", response_model=PictureOut)
def put_emoji(word_id: int, body: EmojiIn, request: Request, user: dict = Depends(current_user)):
    """Gives the word an emoji as its picture (replacing any picture it had)."""
    with connection(request.app.state.pool) as conn:
        return pictures.set_emoji(conn, user["id"], word_id, body.emoji)


@router.put("/{word_id}/picture/photo", response_model=PictureOut)
def put_photo(word_id: int, request: Request, file: UploadFile = File(...), user: dict = Depends(current_user)):
    """Gives the word the learner's own photo (replacing any picture it had). The photo is checked, made smaller and stripped of its
    camera and location data before it is kept, so what is stored is not the file that was sent."""
    raw = file.file.read(pictures.MAX_UPLOAD_BYTES + 1)
    with connection(request.app.state.pool) as conn:
        return pictures.set_photo(conn, user["id"], word_id, raw)


@router.get("/{word_id}/picture", responses={200: {"content": {"image/jpeg": {"schema": {"type": "string", "format": "binary"}}}}})
def get_photo(word_id: int, request: Request, size: str = Query("full", pattern="^(full|thumb)$"), v: int | None = Query(None),
              user: dict = Depends(current_user)):
    """The word's photo as a JPEG (`size=thumb`: the small copy). `v` only makes the address change when the photo does."""
    with connection(request.app.state.pool) as conn:
        data = pictures.photo(conn, user["id"], word_id, small=size == "thumb")
    return Response(content=data, media_type="image/jpeg")


@router.delete("/{word_id}/picture", status_code=204)
def delete_picture(word_id: int, request: Request, user: dict = Depends(current_user)):
    with connection(request.app.state.pool) as conn:
        pictures.remove(conn, user["id"], word_id)
    return Response(status_code=204)
