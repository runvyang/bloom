import requests
import os
from openai import OpenAI

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
DEEPSEEK_API_KEY=os.getenv("DEEPSEEK_API_KEY")

providers = {
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "api_key": DEEPSEEK_API_KEY,
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": OPENROUTER_API_KEY,
    }
}


class OpenRouterClient:
    def __init__(self, model="deepseek-v4-flash"):
        self.model = model

        if model.startswith("deepseek"):
            provider_kwargs = providers["deepseek"]
        else:
            provider_kwargs = providers["openrouter"]

        self.client = OpenAI(**provider_kwargs)

    def chat(self, messages, stream=True, json=False, reasoning=False):
        extra_kwargs = dict()
        if json:
            extra_kwargs = dict(response_format={'type': 'json_object'})
        if not reasoning:
            extra_kwargs.update(
                extra_body={"thinking": {"type": "disabled"}}
            )
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=stream,
            **extra_kwargs
        )

        return completion
