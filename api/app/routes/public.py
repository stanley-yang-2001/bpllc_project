"""What anyone may read without signing in: what the sign-up and privacy pages need, and the list of languages."""
from __future__ import annotations

from fastapi import APIRouter, Query, Request
from tutor_core.languages import LANGUAGES, stories_enabled

from .. import policy
from ..policy import POLICY_VERSION
from ..schemas import LanguageOut, MetaOut, PolicyOut

router = APIRouter(tags=["public"])


@router.get("/meta", response_model=MetaOut)
def meta(request: Request):
    """Public: what the privacy page and sign-up form need to show."""
    return {"policy_version": POLICY_VERSION, "privacy_contact": request.app.state.settings.privacy_contact,
            "policy_languages": policy.languages()}


@router.get("/policy", response_model=PolicyOut)
def policy_copy(lang: str | None = Query(default=None, max_length=8)):
    """Public: the privacy policy copy to show for `lang`. Only an approved, current copy is ever served; otherwise
    the English copy, with fallback=true (design 3I)."""
    doc, fallback = policy.select(lang)
    return {"language": doc["language"], "version": doc["version"], "fallback": fallback, "doc": doc}


@router.get("/languages", response_model=list[LanguageOut])
def languages():
    """Public: the registration form needs it, and it contains nothing private."""
    return [{"code": l.code, "name": l.name, "native": l.native, "tier": l.tier, "stories_enabled": stories_enabled(l.code)}
            for l in LANGUAGES.values()]
