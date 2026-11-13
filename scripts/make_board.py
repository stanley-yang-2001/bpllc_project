"""Write docs/kanban/BOARD.md from docs/kanban/cards.json (the same file create_kanban_cards.py uploads).

    python scripts/make_board.py          # rewrite BOARD.md
    python scripts/make_board.py --check  # change nothing; exit 1 if BOARD.md is out of date
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CARDS = ROOT / "docs" / "kanban" / "cards.json"
BOARD = ROOT / "docs" / "kanban" / "BOARD.md"
HEAD = ("# Kanban board\n\nGenerated from `cards.json` (the same file `scripts/create_kanban_cards.py` uploads). "
        "Needs your decision = waiting for your choice; Done = built and run or verified; In review = built, waiting for your run; Backlog = not built.\n\n")


def render(cards) -> str:
    out = [HEAD]
    for status in ("Needs your decision", "Backlog", "In review", "Done"):
        mine = [c for c in cards if c["status"] == status]
        out.append(f"\n## {status} ({len(mine)})\n\n")
        out.extend(f"- **{c['title']}** ({c.get('date') or 'no date'}) — {c['summary']}\n" for c in mine)
    return "".join(out)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    text = render(json.loads(CARDS.read_text(encoding="utf-8")))
    if "--check" in argv:
        return 0 if BOARD.read_text(encoding="utf-8") == text else 1
    BOARD.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
