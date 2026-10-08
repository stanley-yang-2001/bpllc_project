from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from ..db import connection, cursor
from ..deps import current_user
from ..schemas import HealthOut, StatusOut

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=StatusOut)
def live():
    return {"status": "ok"}


@router.get("", response_model=HealthOut)
def health(request: Request, _: dict = Depends(current_user)):
    try:
        with connection(request.app.state.pool) as conn, cursor(conn) as cur:
            cur.execute("SELECT 1")
        postgres = {"ok": True}
    except Exception as exc:                                    # report, don't crash the page
        postgres = {"ok": False, "detail": type(exc).__name__}
    # Langflow and Groq checks arrive with the chat (M5) and story (M6) milestones.
    return {"postgres": postgres, "langflow": {"status": "unchecked"}, "groq": {"status": "unchecked"},
            "ai_mode": request.app.state.settings.ai_mode}
