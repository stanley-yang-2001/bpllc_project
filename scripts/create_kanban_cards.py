"""Create GitHub issues (kanban cards) from docs/kanban/cards.json and add them to a GitHub Project board.

Run on your own machine, in the project folder, with the GitHub CLI installed and signed in (`gh auth login`). Adding to a
Project also needs the project scope once: `gh auth refresh -s project`.

    python scripts/create_kanban_cards.py --repo stanley-yang-2001/bpllc_project --dry-run
    python scripts/create_kanban_cards.py --repo stanley-yang-2001/bpllc_project --project 1 --owner stanley-yang-2001

What it does for each card: makes the issue (title, body with a checklist, labels), closes it when the card is Done (a Project's
built-in workflow moves closed issues to its Done column; open ones land in Todo), and adds it to the Project. With --set-status each card is also moved to its column (the board's Status field); without it "In review" and "Backlog" are labels only.
Cards that already exist (found by title in the repository, and remembered in docs/kanban/created.json) are skipped, so running it again never duplicates anything.
Nothing is created without you running this; no push is involved.
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CARDS = ROOT / "docs" / "kanban" / "cards.json"
STATE = ROOT / "docs" / "kanban" / "created.json"
COLORS = {"status:in-review": "fbca04", "status:backlog": "c5def5", "status:done": "0e8a16"}


def gh(*args, check=True):
    r = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8")
    if check and r.returncode != 0:
        sys.exit(f"gh {' '.join(args[:3])} failed: {(r.stderr or r.stdout).strip()}")
    return r.stdout.strip()


def body(c):
    lines = [c["summary"], ""]
    if c["date"]:
        lines += [f"**Date:** {c['date']}", ""]
    if c["done"]:
        lines += ["### Done"] + [f"- [x] {x}" for x in c["done"]] + [""]
    if c["todo"]:
        lines += ["### To do"] + [f"- [ ] {x}" for x in c["todo"]] + [""]
    lines += [f"_Area: {c['area']} · Status: {c['status']}_"]
    return "\n".join(lines)


def add_to_project(project, owner, url):
    """Adds the issue to the board. A failure is reported but never stops the run: a Project with an auto-add workflow has
    often added the issue already ("Content already exists in this project"), and a missing scope can be fixed afterwards."""
    r = subprocess.run(["gh", "project", "item-add", str(project), "--owner", owner, "--url", url],
                       capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        msg = (r.stderr or r.stdout).strip()
        if "already exists" in msg:
            return "already on the board"
        print(f"    could not add to the board: {msg}")
        return "not added to the board"
    return "added to the board"


WANT = {"Done": ["done"], "In review": ["in review", "review", "in progress"], "Backlog": ["backlog", "todo", "to do"]}


def board_status_setup(project, owner):
    """For --set-status: the project id, the Status field id and its options (name lower case -> id). None if the board has no Status field."""
    pid = json.loads(gh("project", "view", str(project), "--owner", owner, "--format", "json"))["id"]
    fields = json.loads(gh("project", "field-list", str(project), "--owner", owner, "--format", "json", "--limit", "50"))["fields"]
    status = next((f for f in fields if f["name"].lower() == "status" and f.get("options")), None)
    if not status:
        return None
    return pid, status["id"], {o["name"].lower(): o["id"] for o in status["options"]}


def set_status(project, owner, setup, url, status):
    """Moves the card to the column whose name fits (Done; In review or In progress; Backlog or Todo). Reports instead of failing."""
    pid, field_id, options = setup
    items = json.loads(gh("project", "item-list", str(project), "--owner", owner, "--format", "json", "--limit", "500"))["items"]
    item = next((i["id"] for i in items if (i.get("content") or {}).get("url") == url), None)
    option = next((options[w] for w in WANT[status] if w in options), None)
    if not item or not option:
        return f"status not set ({'card is not on the board' if not item else 'no matching column'})"
    r = subprocess.run(["gh", "project", "item-edit", "--id", item, "--project-id", pid, "--field-id", field_id,
                        "--single-select-option-id", option], capture_output=True, text=True, encoding="utf-8")
    return "status set" if r.returncode == 0 else f"status not set: {(r.stderr or r.stdout).strip()[:120]}"


def existing_issues(repo):
    """title -> url of every issue the repository already has, so a rerun never makes a second copy."""
    out = gh("issue", "list", "--repo", repo, "--state", "all", "--limit", "500", "--json", "title,url")
    return {i["title"]: i["url"] for i in json.loads(out or "[]")}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", required=True, help="owner/name of the repository that gets the issues")
    ap.add_argument("--project", type=int, help="number of the GitHub Project (the number in its URL)")
    ap.add_argument("--owner", help="owner (user or organisation) of the Project; defaults to the repo owner")
    ap.add_argument("--set-status", action="store_true",
                    help="also move each card to its column (Status field: Done / In review or In progress / Backlog or Todo); needs --project")
    ap.add_argument("--dry-run", action="store_true", help="print what would be created and change nothing")
    a = ap.parse_args()
    owner = a.owner or a.repo.split("/")[0]
    cards = json.loads(CARDS.read_text(encoding="utf-8"))
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}

    found, setup = {}, None
    if a.set_status and not a.project:
        sys.exit("--set-status needs --project")
    if a.set_status and not a.dry_run:
        setup = board_status_setup(a.project, owner)
        print("Status columns found: " + (", ".join(setup[2]) if setup else "none (the board has no Status field); cards stay where the board puts them"))
    if not a.dry_run:
        gh("auth", "status")
        found = existing_issues(a.repo)
        for name, color in COLORS.items():
            gh("label", "create", name, "--repo", a.repo, "--color", color, "--force", check=False)

    for i, c in enumerate(cards, 1):
        if c["title"] in state or c["title"] in found:
            url = state.get(c["title"]) or found[c["title"]]
            note = add_to_project(a.project, owner, url) if a.project and not a.dry_run else ""
            if setup:
                note += "; " + set_status(a.project, owner, setup, url, c["status"])
            state[c["title"]] = url
            print(f"[{i}/{len(cards)}] already exists, skipped {url}  {c['title']}  {note}".rstrip())
            continue
        status_label = {"Done": "status:done", "In review": "status:in-review", "Backlog": "status:backlog"}[c["status"]]
        labels = sorted(set(c["labels"] + [status_label]))
        if a.dry_run:
            print(f"[{i}/{len(cards)}] would create {c['status']:<9} {c['title']}  labels={labels}")
            continue
        for label in labels:
            gh("label", "create", label, "--repo", a.repo, "--force", check=False)
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(body(c))
            path = f.name
        args = ["issue", "create", "--repo", a.repo, "--title", c["title"], "--body-file", path]
        for label in labels:
            args += ["--label", label]
        url = gh(*args).splitlines()[-1]
        Path(path).unlink(missing_ok=True)
        if c["status"] == "Done":
            gh("issue", "close", url, "--reason", "completed")
        state[c["title"]] = url          # recorded before the board step, so a failure there never causes a duplicate
        STATE.write_text(json.dumps(state, indent=1, ensure_ascii=False), encoding="utf-8")
        note = add_to_project(a.project, owner, url) if a.project else ""
        if setup:
            note += "; " + set_status(a.project, owner, setup, url, c["status"])
        print(f"[{i}/{len(cards)}] {c['status']:<9} {url}  {c['title']}  {note}".rstrip())
    print("done" if not a.dry_run else "dry run only: nothing was created")


if __name__ == "__main__":
    main()
