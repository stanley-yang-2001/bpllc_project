"""
Test for custom_components/groq_language_model.py: an empty key field falls back to the
GROQ_API_KEY environment variable (so the flow file in the repo can ship without a key).

Langflow and langchain are not installed outside the Langflow image, so minimal stand-ins are put
in sys.modules before the component is imported. Run from the repo root:
    python tests/test_groq_language_model.py
"""

import os
import sys
import types

failures = []


def check(name, condition, detail=""):
    if condition:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name} {detail}")
        failures.append(name)


def install_stubs():
    def module(name, **attrs):
        mod = types.ModuleType(name)
        mod.__dict__.update(attrs)
        sys.modules[name] = mod
        return mod

    class Component:  # the real one injects input values as attributes
        pass

    class _Input:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class ChatOpenAI:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    module("langflow")
    module("langflow.custom", Component=Component)
    module("langflow.io", SecretStrInput=_Input, StrInput=_Input, Output=_Input)
    module("langflow.field_typing", LanguageModel=object)
    module("langchain_openai", ChatOpenAI=ChatOpenAI)


def build(field_value):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "custom_components")
    sys.path.insert(0, path)
    sys.modules.pop("groq_language_model", None)
    import groq_language_model as g

    component = g.GroqLanguageModel()
    component.api_key, component.model_name = field_value, "openai/gpt-oss-120b"
    return component.build_model().kwargs


def main():
    print("Running Groq language model tests...\n")
    install_stubs()
    saved = os.environ.get("GROQ_API_KEY")
    try:
        os.environ["GROQ_API_KEY"] = "env-key"
        check("a key typed into the field wins", build("field-key")["api_key"] == "field-key")
        check("an empty field falls back to the environment", build("")["api_key"] == "env-key")
        check("a missing field (None) falls back too", build(None)["api_key"] == "env-key")
        del os.environ["GROQ_API_KEY"]
        check("no field and no environment gives an empty string, not a crash", build("")["api_key"] == "")
        kwargs = build("k")
        check("base url and model are unchanged",
              kwargs["base_url"] == "https://api.groq.com/openai/v1" and kwargs["model"] == "openai/gpt-oss-120b")
    finally:
        if saved is not None:
            os.environ["GROQ_API_KEY"] = saved
    print()
    if failures:
        print(f"{len(failures)} test(s) failed: {failures}")
        sys.exit(1)
    print("All tests passed.")


if __name__ == "__main__":
    main()
