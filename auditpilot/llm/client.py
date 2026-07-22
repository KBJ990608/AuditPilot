from dataclasses import dataclass, replace
import json
from pathlib import Path
from typing import Protocol, Union

import requests


@dataclass(frozen=True)
class LLMResponse:
    content: str
    provider: str
    model: str
    cached: bool = False
    fallback: bool = False


class LLMClient(Protocol):
    def generate(self, task_key: str, system: str, user: str) -> LLMResponse: ...


class FixtureClient:
    def __init__(self, path: Union[str, Path]):
        self.path = Path(path)
        self.responses = json.loads(self.path.read_text(encoding="utf-8"))

    def generate(self, task_key: str, system: str, user: str) -> LLMResponse:
        item = self.responses[task_key]
        return LLMResponse(item["content"], item.get("provider", "fixture"), item.get("model", "cached"), True)


class OpenAICompatibleClient:
    def __init__(self, base_url: str, api_key: str, model: str, timeout: int = 20, max_tokens: int = 220):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_tokens = max_tokens

    def generate(self, task_key: str, system: str, user: str) -> LLMResponse:
        response = requests.post(f"{self.base_url}/chat/completions", headers={"Authorization": f"Bearer {self.api_key}"},
                                 json={"model": self.model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}], "temperature": 0, "max_tokens": self.max_tokens}, timeout=self.timeout)
        response.raise_for_status()
        return LLMResponse(response.json()["choices"][0]["message"]["content"], "openai_compat", self.model)


def safe_generate(primary: LLMClient, fallback: FixtureClient, task_key: str, system: str, user: str) -> LLMResponse:
    try:
        return primary.generate(task_key, system, user)
    except Exception:
        return replace(fallback.generate(task_key, system, user), fallback=True)
