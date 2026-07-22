import json

from auditpilot.llm.client import FixtureClient, LLMResponse, safe_generate


class BrokenClient:
    def generate(self, task_key, system, user):
        raise TimeoutError("down")


def test_fixture_client_and_fallback(tmp_path):
    fixture = tmp_path / "responses.json"
    fixture.write_text(json.dumps({"hello": {"provider": "fixture", "model": "cached", "cached": True, "content": "안녕하세요"}}, ensure_ascii=False))
    client = FixtureClient(fixture)
    assert client.generate("hello", "", "").content == "안녕하세요"
    response = safe_generate(BrokenClient(), client, "hello", "", "")
    assert isinstance(response, LLMResponse)
    assert response.cached and response.fallback
