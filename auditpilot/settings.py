import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class MissingOpenAIAPIKeyError(RuntimeError):
    """Raised when no supported OpenAI API key source is configured."""


def _read_streamlit_secret() -> str | None:
    try:
        import streamlit as st

        value = st.secrets.get("OPENAI_API_KEY")
    except Exception:
        return None
    return str(value).strip() if value else None


def _read_dotenv_key(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        if name.strip() != "OPENAI_API_KEY":
            continue
        value = value.strip().strip("'\"")
        return value or None
    return None


def get_openai_api_key(*, required: bool = True) -> str | None:
    """Load the OpenAI key without printing, logging, or persisting its value."""
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        key = _read_streamlit_secret()
    if not key:
        key = _read_dotenv_key(PROJECT_ROOT / ".env")

    if key:
        return key
    if required:
        raise MissingOpenAIAPIKeyError(
            "OpenAI API 키가 설정되지 않았습니다. 운영체제 환경변수, "
            "Streamlit Secrets 또는 로컬 .env에 OPENAI_API_KEY를 설정해주세요."
        )
    return None
