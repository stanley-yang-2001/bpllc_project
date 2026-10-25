"""scripts/create_kanban_cards.py: the card file is valid and --set-status picks the right column (gh is replaced, nothing is called)."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import create_kanban_cards as k  # noqa: E402


def test_every_card_has_what_the_script_needs():
    cards = json.loads((ROOT / "docs" / "kanban" / "cards.json").read_text(encoding="utf-8"))
    assert len(cards) >= 40 and len({c["title"] for c in cards}) == len(cards)
    for c in cards:
        assert c["status"] in k.WANT and c["title"] and c["summary"] and c["labels"]
        assert "- [x]" in k.body(c) or c["status"] == "Backlog" or c["done"] == []


def test_set_status_uses_the_matching_column_and_reports_a_missing_one(monkeypatch):
    items = {"items": [{"id": "ITEM1", "content": {"url": "https://github.com/o/r/issues/1"}}]}
    monkeypatch.setattr(k, "gh", lambda *a, **kw: json.dumps(items))
    calls = []
    monkeypatch.setattr(k.subprocess, "run", lambda args, **kw: calls.append(args) or subprocess.CompletedProcess(args, 0, "", ""))
    setup = ("PID", "FID", {"todo": "O1", "in progress": "O2", "done": "O3"})
    assert k.set_status(1, "o", setup, "https://github.com/o/r/issues/1", "In review") == "status set"
    assert "O2" in calls[-1] and "ITEM1" in calls[-1]                 # no "In review" column: In progress is the nearest
    assert k.set_status(1, "o", setup, "https://github.com/o/r/issues/1", "Backlog") == "status set" and "O1" in calls[-1]
    assert "not on the board" in k.set_status(1, "o", setup, "https://github.com/o/r/issues/99", "Done")
    assert "no matching column" in k.set_status(1, "o", ("P", "F", {"x": "1"}), "https://github.com/o/r/issues/1", "Done")
