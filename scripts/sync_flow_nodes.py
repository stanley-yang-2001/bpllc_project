"""Keep the three tool nodes in flows/language-tutor.json in step with custom_components/ (M3).

A node on the Langflow canvas holds its OWN copy of its component's code (and its own field templates), so editing a file
in custom_components/ changes nothing in a flow until the node is updated. This script copies the code of the Add Word,
Story Generator Tool and Word Loader components into their nodes, recomputes each node's code hash, and makes sure the
hidden inputs the API sets through tweaks (`learner_id`, `active_language`) exist as fields on each node (without a field
there is nothing for a tweak to land on).

    python scripts/sync_flow_nodes.py            # update flows/language-tutor.json in place
    python scripts/sync_flow_nodes.py --check    # change nothing; exit 1 and say what differs (the tests run this)

It never touches any other node, the edges, or the Agent's instructions, and it refuses to write a file that still
contains something that looks like an API key.
"""
import argparse
import hashlib
import json
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
FLOW = os.path.join(ROOT, "flows", "language-tutor.json")
COMPONENTS = os.path.join(ROOT, "custom_components")

NODES = {"AddWord-WhP5g": "add_word.py", "StoryGeneratorTool-RQpvc": "story_tool.py", "WordLoader-2zTeQ": "word_loader.py"}
LANGFLOW_VERSION = "1.12.2"
_SECRET = re.compile(r"gsk_\w{20,}|AIza[\w\-]{20,}|sk-[\w\-]{20,}")

# (display name, info) of the hidden inputs; they must match the StrInput definitions in the components.
HIDDEN = {
    "learner_id": ("Learner ID (hidden)",
                   "Set per request by the API through tweaks, as a STRING. The Agent never sees this field. Never name it user_id: "
                   "Langflow reserves that name on every component."),
    "active_language": ("Active language (hidden)",
                        "Set per request by the API through tweaks: the learner's selected language, as an ISO code."),
}


def hidden_field(name):
    """A hidden text field in the format Langflow 1.12.2 generates for `StrInput(advanced=True, tool_mode=False)`."""
    display, info = HIDDEN[name]
    return {
        "_input_type": "StrInput", "advanced": True, "api_editable": False, "display_name": display, "dynamic": False,
        "info": info, "list": False, "list_add_label": "Add More", "load_from_db": False, "name": name, "override_skip": False,
        "placeholder": "", "required": False, "show": True, "title_case": False, "tool_mode": False,
        "trace_as_metadata": True, "track_in_telemetry": False, "type": "str", "value": "",
    }


def tutor_core_version():
    text = open(os.path.join(ROOT, "tutor_core", "pyproject.toml"), encoding="utf-8").read()
    return re.search(r'^version\s*=\s*"([^"]+)"', text, flags=re.M).group(1)


def code_of(filename):
    return open(os.path.join(COMPONENTS, filename), encoding="utf-8").read().rstrip("\n")


def code_hash(code):
    return hashlib.sha256(code.encode("utf-8")).hexdigest()[:12]


def sync(flow, write=True):
    """Returns the list of differences found (and fixes them in `flow` when write=True)."""
    problems = []
    nodes = {n["id"]: n["data"]["node"] for n in flow["data"]["nodes"]}
    for node_id, filename in NODES.items():
        if node_id not in nodes:
            problems.append(f"{node_id}: node is missing from the flow")
            continue
        node = nodes[node_id]
        code = code_of(filename)
        if node["template"]["code"]["value"] != code:
            problems.append(f"{node_id}: the code on the canvas differs from custom_components/{filename}")
            if write:
                node["template"]["code"]["value"] = code
        wanted = code_hash(code)
        if node.get("metadata", {}).get("code_hash") != wanted:
            problems.append(f"{node_id}: code_hash is {node.get('metadata', {}).get('code_hash')}, should be {wanted}")
            if write:
                node.setdefault("metadata", {})["code_hash"] = wanted
        deps = {"dependencies": [{"name": "tutor_core", "version": tutor_core_version()}, {"name": "langflow", "version": LANGFLOW_VERSION}],
                "total_dependencies": 2}
        if node.get("metadata", {}).get("dependencies") != deps:
            problems.append(f"{node_id}: dependency metadata is out of date")
            if write:
                node["metadata"]["dependencies"] = deps
        for name in HIDDEN:
            if node["template"].get(name) != hidden_field(name):
                problems.append(f"{node_id}: hidden field {name} is missing or differs")
                if write:
                    node["template"][name] = hidden_field(name)
            if name not in node.get("field_order", []):
                problems.append(f"{node_id}: {name} is not in field_order")
                if write:
                    node.setdefault("field_order", []).append(name)
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="change nothing; exit 1 if the flow is out of step")
    parser.add_argument("--flow", default=FLOW)
    args = parser.parse_args(argv)

    with open(args.flow, encoding="utf-8") as f:
        flow = json.load(f)
    problems = sync(flow, write=not args.check)
    if args.check:
        for p in problems:
            print("OUT OF STEP:", p)
        print("The flow is in step with custom_components/." if not problems else f"{len(problems)} difference(s). Run: python scripts/sync_flow_nodes.py")
        return 1 if problems else 0

    text = json.dumps(flow, indent=2, ensure_ascii=False) + "\n"
    if _SECRET.search(text):
        print("Refusing to write: the flow contains something that looks like an API key.")
        return 2
    with open(args.flow, "w", encoding="utf-8") as f:
        f.write(text)
    for p in problems:
        print("fixed:", p)
    print(f"Wrote {args.flow}" if problems else "Nothing to change.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
