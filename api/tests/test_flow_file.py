"""flows/language-tutor.json: the flow the Langflow image loads (M3).

A node holds its OWN copy of its component's code and field templates, so the repo's components and the flow can drift
apart without anything failing until a learner hits it. These tests make the drift fail here instead. They also tie the
API's default tweak keys to real nodes in the flow."""
import copy
import json
import os
import re
import subprocess
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import sync_flow_nodes as sync  # noqa: E402
from app.config import Settings  # noqa: E402

FLOW_PATH = os.path.join(ROOT, "flows", "language-tutor.json")


@pytest.fixture
def flow():
    with open(FLOW_PATH, encoding="utf-8") as f:
        return json.load(f)


def node(flow, node_id):
    return [n for n in flow["data"]["nodes"] if n["id"] == node_id][0]["data"]["node"]


# --- the repo's flow ----------------------------------------------------------------------------------------

def test_the_flow_is_in_step_with_the_components(flow):
    assert sync.sync(flow, write=False) == []


def test_the_flow_has_an_endpoint_name_and_no_secrets():
    text = open(FLOW_PATH, encoding="utf-8").read()
    assert not re.search(r"gsk_\w{20,}|AIza[\w\-]{20,}|sk-[\w\-]{20,}", text)
    assert json.loads(text)["endpoint_name"] == Settings(database_url="x", jwt_secret="s" * 40).langflow_flow == "language-tutor"


def test_the_default_tweak_keys_are_the_add_word_and_story_nodes(flow):
    keys = Settings(database_url="x", jwt_secret="s" * 40).langflow_tweak_keys
    assert sorted(keys) == sorted(["AddWord-WhP5g", "StoryGeneratorTool-RQpvc"])
    assert sorted(node(flow, k)["display_name"] for k in keys) == ["Add Word", "Story Generator Tool"]


@pytest.mark.parametrize("node_id", sorted(sync.NODES))
def test_the_hidden_inputs_exist_on_every_tool_node_and_the_agent_cannot_see_them(flow, node_id):
    template = node(flow, node_id)["template"]
    for name in ("learner_id", "active_language"):
        f = template[name]
        assert (f["_input_type"], f["type"], f["advanced"], f["tool_mode"], f["value"]) == ("StrInput", "str", True, False, "")
        assert name in node(flow, node_id)["field_order"]
    assert "user_id" not in template                                     # Langflow reserves it


def test_the_agent_still_sees_exactly_one_argument_per_tool(flow):
    visible = {nid: sorted(k for k, v in node(flow, nid)["template"].items()
                           if isinstance(v, dict) and v.get("tool_mode") is True and k != "tools_metadata")
               for nid in ("AddWord-WhP5g", "StoryGeneratorTool-RQpvc")}
    assert visible == {"AddWord-WhP5g": ["word"], "StoryGeneratorTool-RQpvc": ["language"]}


def test_the_word_loader_stays_unwired(flow):
    """It reads a learner's whole list; it is a debugging component and nothing should be able to call it."""
    assert not [e for e in flow["data"]["edges"] if "WordLoader" in e["source"] or "WordLoader" in e["target"]]


def test_the_agent_instructions_are_the_documented_ones(flow):
    doc = open(os.path.join(ROOT, "docs", "AGENT-INSTRUCTIONS.md"), encoding="utf-8").read().split("```")[1].strip()
    agent = [n for n in flow["data"]["nodes"] if n["id"].startswith("Agent-")][0]["data"]["node"]
    assert agent["template"]["system_prompt"]["value"].strip() == doc


# --- the sync script catches drift ---------------------------------------------------------------------------

def test_a_changed_component_is_reported_and_fixed(flow):
    drifted = copy.deepcopy(flow)
    node(drifted, "AddWord-WhP5g")["template"]["code"]["value"] += "\n# edited on the canvas"
    problems = sync.sync(drifted, write=False)
    assert problems == ["AddWord-WhP5g: the code on the canvas differs from custom_components/add_word.py"]
    sync.sync(drifted, write=True)
    assert sync.sync(drifted, write=False) == []


def test_a_stale_code_hash_is_reported_and_fixed(flow):
    stale = copy.deepcopy(flow)
    node(stale, "StoryGeneratorTool-RQpvc")["metadata"]["code_hash"] = "deadbeef0000"
    problems = sync.sync(stale, write=False)
    assert len(problems) == 1 and "code_hash is deadbeef0000" in problems[0]
    sync.sync(stale, write=True)
    assert node(stale, "StoryGeneratorTool-RQpvc")["metadata"]["code_hash"] == sync.code_hash(sync.code_of("story_tool.py"))
    assert sync.sync(stale, write=False) == []


def test_stale_dependency_metadata_is_reported_and_fixed(flow):
    stale = copy.deepcopy(flow)
    node(stale, "AddWord-WhP5g")["metadata"]["dependencies"] = {"dependencies": [{"name": "psycopg2", "version": "2.9"}], "total_dependencies": 1}
    assert any("dependency metadata" in p for p in sync.sync(stale, write=False))
    sync.sync(stale, write=True)
    names = [d["name"] for d in node(stale, "AddWord-WhP5g")["metadata"]["dependencies"]["dependencies"]]
    assert names == ["tutor_core", "langflow"] and sync.sync(stale, write=False) == []


def test_a_missing_hidden_field_is_reported_and_restored(flow):
    broken = copy.deepcopy(flow)
    del node(broken, "StoryGeneratorTool-RQpvc")["template"]["learner_id"]
    assert any("learner_id" in p and "missing" in p for p in sync.sync(broken, write=False))
    sync.sync(broken, write=True)
    assert "learner_id" in node(broken, "StoryGeneratorTool-RQpvc")["template"]


def test_a_tampered_hidden_field_is_reported(flow):
    tampered = copy.deepcopy(flow)
    node(tampered, "AddWord-WhP5g")["template"]["learner_id"]["tool_mode"] = True       # would expose it to the Agent
    assert any("learner_id" in p for p in sync.sync(tampered, write=False))


def test_sync_only_touches_the_three_tool_nodes(flow):
    drifted = copy.deepcopy(flow)
    for nid in sync.NODES:
        node(drifted, nid)["template"]["code"]["value"] = "x"
    sync.sync(drifted, write=True)
    others = lambda f: json.dumps([n for n in f["data"]["nodes"] if n["id"] not in sync.NODES], sort_keys=True)  # noqa: E731
    assert others(drifted) == others(flow) and drifted["data"]["edges"] == flow["data"]["edges"]


def test_the_command_line_check_exits_nonzero_on_drift(tmp_path, flow):
    ok = tmp_path / "ok.json"
    ok.write_text(json.dumps(flow))
    run = lambda *a: subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "sync_flow_nodes.py"), *a], capture_output=True, text=True)  # noqa: E731
    assert run("--check", "--flow", str(ok)).returncode == 0
    bad = copy.deepcopy(flow)
    node(bad, "WordLoader-2zTeQ")["template"]["code"]["value"] = "old code"
    drifted = tmp_path / "drifted.json"
    drifted.write_text(json.dumps(bad))
    r = run("--check", "--flow", str(drifted))
    assert r.returncode == 1 and "WordLoader-2zTeQ" in r.stdout
    assert json.loads(drifted.read_text()) == bad                          # --check changes nothing
    assert run("--flow", str(drifted)).returncode == 0 and run("--check", "--flow", str(drifted)).returncode == 0


def test_a_flow_with_a_key_in_it_is_refused(tmp_path, flow):
    dirty = copy.deepcopy(flow)
    node(dirty, "AddWord-WhP5g")["template"]["code"]["value"] = "old"
    dirty["data"]["nodes"][2]["data"]["node"]["template"]["api_key"]["value"] = "gsk_" + "a" * 40
    p = tmp_path / "dirty.json"
    p.write_text(json.dumps(dirty))
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "sync_flow_nodes.py"), "--flow", str(p)], capture_output=True, text=True)
    assert r.returncode == 2 and "API key" in r.stdout
    assert "gsk_" + "a" * 40 in p.read_text()           # refused means unchanged, so the leak is the user's to see and fix


# --- running the check inside the langflow container (found on the author's machine) -------------------------
# The container mounts scripts/, flows/, custom_components/ and tests/ but NOT tutor_core/, so
# /app/tutor_core/pyproject.toml does not exist there; the package is installed into the interpreter instead.

def test_the_tutor_core_version_comes_from_the_repo_when_its_pyproject_is_there(tmp_path, monkeypatch):
    (tmp_path / "tutor_core").mkdir()
    (tmp_path / "tutor_core" / "pyproject.toml").write_text('[project]\nname = "tutor_core"\nversion = "1.2.3"\n')
    monkeypatch.setattr(sync.metadata, "version", lambda name: "9.9.9")             # must not be consulted
    assert sync.tutor_core_version(str(tmp_path)) == "1.2.3"


def test_the_tutor_core_version_comes_from_the_installed_package_when_there_is_no_pyproject(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(sync.metadata, "version", lambda name: seen.append(name) or "4.5.6")
    assert sync.tutor_core_version(str(tmp_path)) == "4.5.6" and seen == ["tutor_core"]


def test_a_missing_tutor_core_is_explained_not_a_traceback(tmp_path, monkeypatch):
    def not_installed(name):
        raise sync.metadata.PackageNotFoundError(name)
    monkeypatch.setattr(sync.metadata, "version", not_installed)
    with pytest.raises(SystemExit) as e:
        sync.tutor_core_version(str(tmp_path))
    assert "tutor_core" in str(e.value) and "pyproject.toml" in str(e.value)
