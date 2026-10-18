"""The privacy policy as separate approved copies (design 3I): shape, safety rule, selection and the public route."""
from __future__ import annotations

import copy
import json
import re

import pytest

from app import policy

DIR = policy._DIR
FILES = sorted(DIR.glob("*.json"))
EN = json.loads((DIR / "en.json").read_text(encoding="utf-8"))
HOLES = re.compile(r"\{(\w+)\}")


def shape(doc: dict):
    """Everything about a copy's structure that must be the same in every language."""
    out = [("summary", len(doc["summary"]["items"])), ("sections", [s["id"] for s in doc["sections"]])]
    for s in doc["sections"]:
        for b in s["blocks"]:
            if b["type"] == "p":
                out.append((s["id"], "p", sorted(b)))
            elif b["type"] == "list":
                out.append((s["id"], "list", len(b["items"])))
            else:
                out.append((s["id"], "table", len(b["head"]), len(b["rows"])))
    return out


def strings(doc):
    if isinstance(doc, str):
        yield doc
    elif isinstance(doc, dict):
        for v in doc.values():
            yield from strings(v)
    elif isinstance(doc, list):
        for v in doc:
            yield from strings(v)


def holes(doc):
    return sorted(set(h for s in strings(doc) for h in HOLES.findall(s)))


def test_there_is_at_least_the_english_copy_and_every_file_parses():
    assert (DIR / "en.json").exists()
    for f in FILES:
        assert json.loads(f.read_text(encoding="utf-8"))["language"] == f.stem


def test_english_is_approved_and_current():
    assert policy.shown(EN) and EN["version"] == policy.POLICY_VERSION
    assert policy.languages()[0] == "en"


@pytest.mark.parametrize("f", FILES, ids=lambda f: f.stem)
def test_every_copy_has_the_english_shape_and_no_empty_strings(f):
    doc = json.loads(f.read_text(encoding="utf-8"))
    assert shape(doc) == shape(EN)
    assert all(s.strip() for s in strings(doc))
    assert holes(doc) == holes(EN)
    assert doc["governing"].strip()


@pytest.mark.parametrize("f", FILES, ids=lambda f: f.stem)
def test_approved_copies_carry_an_approver_and_a_date(f):
    doc = json.loads(f.read_text(encoding="utf-8"))
    assert doc["status"] in ("draft", "approved")
    if doc["status"] == "approved":
        assert doc["approved_by"].strip() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", doc["approved_on"])


def test_the_english_copy_says_what_the_code_does_about_display_preferences():
    text = " ".join(strings(EN))
    for claim in ["display preferences", "temporary copy", "removed when you sign out", "English copy governs", "saved on your account"]:
        assert claim in text


# ---- the selection rule, with made-up copies so it does not depend on what is on disk ----------------------------------
def fake(monkeypatch, **docs):
    base = copy.deepcopy(EN)
    built = {"en": base}
    for code, change in docs.items():
        d = copy.deepcopy(EN) | {"language": code} | change
        built[code] = d
    monkeypatch.setattr(policy, "_all", lambda: built)
    return built


def test_a_draft_is_never_served(monkeypatch):
    fake(monkeypatch, es={"status": "draft", "approved_by": "A. Person", "approved_on": "2026-10-17"})   # even with a name and date
    assert policy.select("es") == (policy._all()["en"], True)
    assert "es" not in policy.languages()


def test_a_stale_approved_copy_is_never_served(monkeypatch):
    fake(monkeypatch, es={"status": "approved", "approved_by": "A. Person", "approved_on": "2026-01-01", "version": "2025-01-01"})
    doc, fallback = policy.select("es")
    assert doc["language"] == "en" and fallback is True
    assert policy.languages() == ["en"]


def test_an_approved_current_copy_is_served_and_listed(monkeypatch):
    fake(monkeypatch, es={"status": "approved", "approved_by": "A. Person", "approved_on": "2026-10-17"},
         de={"status": "approved", "approved_by": "B. Person", "approved_on": "2026-10-17"})
    doc, fallback = policy.select("es")
    assert doc["language"] == "es" and fallback is False
    assert policy.languages() == ["en", "de", "es"]


def test_approval_without_an_approver_or_a_date_is_not_enough(monkeypatch):
    fake(monkeypatch, es={"status": "approved", "approved_by": "", "approved_on": "2026-10-17"},
         fr={"status": "approved", "approved_by": "X", "approved_on": ""})
    assert policy.languages() == ["en"]


def test_unknown_or_missing_language_falls_back_to_english(monkeypatch):
    fake(monkeypatch)
    assert policy.select("xx")[1] is True
    assert policy.select(None) == (policy._all()["en"], False)
    assert policy.select("en")[1] is False


# ---- the public route ------------------------------------------------------------------------------------------------
def test_policy_route_is_public_and_returns_the_english_copy(client):
    r = client.get("/api/policy")
    assert r.status_code == 200
    body = r.json()
    assert body["language"] == "en" and body["version"] == policy.POLICY_VERSION and body["fallback"] is False
    assert body["doc"]["title"] == "Privacy Policy"


def test_policy_route_falls_back_with_a_flag_for_a_language_without_an_approved_copy(client):
    body = client.get("/api/policy?lang=ja").json()
    assert body["language"] == "en" and body["fallback"] is True


def test_policy_route_serves_an_approved_copy_when_there_is_one(client, monkeypatch):
    fake(monkeypatch, es={"status": "approved", "approved_by": "A", "approved_on": "2026-10-17", "title": "Política"})
    body = client.get("/api/policy?lang=es").json()
    assert body["language"] == "es" and body["fallback"] is False and body["doc"]["title"] == "Política"
    assert client.get("/api/meta").json()["policy_languages"] == ["en", "es"]


def test_meta_lists_only_approved_current_languages(client, monkeypatch):
    fake(monkeypatch, es={"status": "draft", "approved_by": "", "approved_on": ""})
    assert client.get("/api/meta").json()["policy_languages"] == ["en"]
