import pytest

from auditpilot import settings


def test_environment_variable_has_highest_priority(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "environment-value")
    monkeypatch.setattr(settings, "_read_streamlit_secret", lambda: "secret-value")
    (tmp_path / ".env").write_text("OPENAI_API_KEY=dotenv-value\n", encoding="utf-8")

    assert settings.get_openai_api_key() == "environment-value"


def test_streamlit_secret_precedes_dotenv(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "PROJECT_ROOT", tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(settings, "_read_streamlit_secret", lambda: "secret-value")
    (tmp_path / ".env").write_text("OPENAI_API_KEY=dotenv-value\n", encoding="utf-8")

    assert settings.get_openai_api_key() == "secret-value"


def test_dotenv_is_local_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "PROJECT_ROOT", tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(settings, "_read_streamlit_secret", lambda: None)
    (tmp_path / ".env").write_text(
        "OPENAI_API_KEY='dotenv-value'\n",
        encoding="utf-8",
    )

    assert settings.get_openai_api_key() == "dotenv-value"


def test_missing_key_has_clear_error(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "PROJECT_ROOT", tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(settings, "_read_streamlit_secret", lambda: None)

    with pytest.raises(settings.MissingOpenAIAPIKeyError, match="설정되지 않았습니다"):
        settings.get_openai_api_key()
