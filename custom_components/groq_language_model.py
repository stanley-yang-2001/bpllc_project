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
        return ChatOpenAI(
            api_key=self.api_key,
            base_url="https://api.groq.com/openai/v1",
            model=self.model_name,
        )