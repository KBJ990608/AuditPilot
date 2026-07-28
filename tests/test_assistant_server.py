import pytest
import requests

from auditpilot import assistant_server


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.ok = 200 <= status_code < 400

    def json(self):
        return self._payload


def test_default_model_and_environment_override(monkeypatch):
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    assert assistant_server.get_openai_model() == "gpt-5"

    monkeypatch.setenv("OPENAI_MODEL", "custom-model")
    assert assistant_server.get_openai_model() == "custom-model"


def test_ask_openai_uses_responses_api_and_parses_output(monkeypatch):
    captured = {}

    def fake_post(url, *, headers, json, timeout):
        captured.update(
            url=url,
            authorization_present=bool(headers.get("Authorization")),
            payload=json,
            timeout=timeout,
        )
        return FakeResponse(
            payload={
                "output": [
                    {
                        "content": [
                            {"type": "output_text", "text": "안녕하세요, 삼일이 AI입니다."}
                        ]
                    }
                ]
            }
        )

    monkeypatch.setattr(assistant_server, "get_openai_api_key", lambda: "test-key")
    monkeypatch.setattr(assistant_server.requests, "post", fake_post)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    answer = assistant_server.ask_openai("안녕하세요. 너는 누구야?")

    assert answer == "안녕하세요, 삼일이 AI입니다."
    assert captured["url"] == "https://api.openai.com/v1/responses"
    assert captured["authorization_present"]
    assert captured["payload"]["model"] == "gpt-5"
    assert captured["payload"]["input"] == "안녕하세요. 너는 누구야?"
    assert captured["payload"]["max_output_tokens"] == 600
    assert captured["payload"]["reasoning"] == {"effort": "minimal"}
    assert captured["timeout"] == 60


def test_non_gpt5_override_omits_reasoning_option(monkeypatch):
    captured = {}

    def fake_post(url, *, headers, json, timeout):
        captured["payload"] = json
        return FakeResponse(payload={"output_text": "정상 응답"})

    monkeypatch.setattr(assistant_server, "get_openai_api_key", lambda: "test-key")
    monkeypatch.setattr(assistant_server.requests, "post", fake_post)
    monkeypatch.setenv("OPENAI_MODEL", "custom-model")

    assert assistant_server.ask_openai("질문") == "정상 응답"
    assert "reasoning" not in captured["payload"]


@pytest.mark.parametrize(
    ("status", "error_type", "expected"),
    [
        (401, "invalid_api_key", "API 키가 유효하지 않습니다"),
        (402, "billing_error", "결제 또는 사용한도"),
        (429, "insufficient_quota", "결제 또는 사용한도"),
        (404, "model_not_found", "모델을 사용할 수 없습니다"),
        (400, "model_not_found", "모델을 사용할 수 없습니다"),
        (429, "rate_limit_exceeded", "요청이 많습니다"),
        (500, "server_error", "연결 중 오류"),
    ],
)
def test_api_error_is_safely_classified(status, error_type, expected):
    response = FakeResponse(
        status_code=status,
        payload={"error": {"type": error_type}},
    )

    error = assistant_server._api_error(response)

    assert expected in error.user_message
    assert error.status_code == status
    assert error.error_type == error_type


def test_timeout_has_safe_user_message(monkeypatch):
    monkeypatch.setattr(assistant_server, "get_openai_api_key", lambda: "test-key")
    monkeypatch.setattr(
        assistant_server.requests,
        "post",
        lambda *args, **kwargs: (_ for _ in ()).throw(requests.Timeout()),
    )

    with pytest.raises(assistant_server.OpenAIAPIError, match="시간이 초과"):
        assistant_server.ask_openai("질문")


def test_incomplete_response_has_safe_user_message(monkeypatch):
    monkeypatch.setattr(assistant_server, "get_openai_api_key", lambda: "test-key")
    monkeypatch.setattr(
        assistant_server.requests,
        "post",
        lambda *args, **kwargs: FakeResponse(
            payload={
                "status": "incomplete",
                "incomplete_details": {"reason": "max_output_tokens"},
                "output": [{"type": "reasoning"}],
            }
        ),
    )

    with pytest.raises(
        assistant_server.OpenAIAPIError,
        match="답변 생성이 완료되지 않았습니다",
    ) as caught:
        assistant_server.ask_openai("질문")

    assert caught.value.error_type == "incomplete_max_output_tokens"


def test_error_log_never_contains_api_key(monkeypatch, caplog):
    secret_value = "sensitive-test-value"
    monkeypatch.setattr(
        assistant_server,
        "get_openai_api_key",
        lambda: secret_value,
    )
    monkeypatch.setattr(
        assistant_server.requests,
        "post",
        lambda *args, **kwargs: FakeResponse(
            status_code=401,
            payload={"error": {"type": "invalid_api_key"}},
        ),
    )

    with pytest.raises(assistant_server.OpenAIAPIError):
        assistant_server.ask_openai("질문")

    assert secret_value not in caplog.text
    assert "status=401" in caplog.text
    assert "type=invalid_api_key" in caplog.text
