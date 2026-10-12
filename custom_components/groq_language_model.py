import os

from langflow.custom import Component
from langflow.io import SecretStrInput, StrInput, Output
from langflow.field_typing import LanguageModel
from langchain_openai import ChatOpenAI

class GroqLanguageModel(Component):
    display_name = "Groq (via OpenAI-compatible)"
    description = "Connects to Groq's API using its OpenAI-compatible interface."

    inputs = [
        SecretStrInput(name="api_key", display_name="Groq API Key"),
        StrInput(name="model_name", display_name="Model Name", value="openai/gpt-oss-20b"),
    ]

    outputs = [
        Output(display_name="Language Model", name="model", method="build_model"),
    ]

    def build_model(self) -> LanguageModel:
        # The key field is left empty in the flow file kept in the repo (an exported flow once
        # carried a live key). An empty field falls back to the container's GROQ_API_KEY.
        return ChatOpenAI(
            api_key=self.api_key or os.environ.get("GROQ_API_KEY", ""),
            base_url="https://api.groq.com/openai/v1",
            model=self.model_name,
        )