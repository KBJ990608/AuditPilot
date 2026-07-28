import logging
import os
from typing import Any

import requests

from auditpilot.settings import get_openai_api_key


logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """당신은 AuditPilot의 감사업무 보조 챗봇 '삼일이 AI'입니다.
사용자의 질문에 자연스러운 한국어로 짧고 명확하게 답하세요.
PBC, 데이터 클렌징, 분석적 검토, 감사조서 작성 절차를 설명할 수 있습니다.
감사인의 전문적 판단이나 최종 결론을 대신하지 말고, 필요한 확인 절차와 증빙을 제안하세요.
사용자가 제공하지 않은 숫자나 사실을 만들어내지 마세요.
답변은 특별한 요청이 없으면 5문장 이내로 작성하세요."""


class OpenAIAPIError(RuntimeError):
    def __init__(
        self,
        user_message: str,
        *,
        status_code: int | None = None,
        error_type: str = "unknown",
    ):
        super().__init__(user_message)
        self.user_message = user_message
        self.status_code = status_code
        self.error_type = error_type


def get_openai_model() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-5").strip() or "gpt-5"


def _extract_output_text(payload: dict[str, Any]) -> str:
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    parts: list[str] = []
    for item in payload.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts).strip()


def _error_type(response: requests.Response) -> str:
    try:
        error = response.json().get("error", {})
    except (ValueError, AttributeError):
        return "unknown"
    return str(error.get("code") or error.get("type") or "unknown")


def _api_error(response: requests.Response) -> OpenAIAPIError:
    status = response.status_code
    error_type = _error_type(response)
    normalized = error_type.lower()

    if status == 401:
        message = "OpenAI API 키가 유효하지 않습니다."
    elif status == 402 or any(
        marker in normalized
        for marker in ("quota", "billing", "credit", "usage_limit")
    ):
        message = "OpenAI API 결제 또는 사용한도를 확인해주세요."
    elif status == 404 or "model_not_found" in normalized:
        message = "설정된 OpenAI 모델을 사용할 수 없습니다."
    elif status == 429:
        message = "OpenAI 요청이 많습니다. 잠시 후 다시 시도해주세요."
    else:
        message = "OpenAI API 연결 중 오류가 발생했습니다."

    logger.warning(
        "OpenAI API request failed: status=%s type=%s",
        status,
        error_type,
    )
    return OpenAIAPIError(
        message,
        status_code=status,
        error_type=error_type,
    )


def ask_openai(question: str) -> str:
    api_key = get_openai_api_key()
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = get_openai_model()
    request_payload: dict[str, Any] = {
        "model": model,
        "instructions": SYSTEM_PROMPT,
        "input": question,
        "max_output_tokens": 600,
    }
    if model.startswith("gpt-5"):
        request_payload["reasoning"] = {"effort": "minimal"}

    try:
        response = requests.post(
            f"{base_url}/responses",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=request_payload,
            timeout=60,
        )
    except requests.Timeout as exc:
        logger.warning("OpenAI API request failed: status=none type=timeout")
        raise OpenAIAPIError(
            "OpenAI 응답 시간이 초과되었습니다.",
            error_type="timeout",
        ) from exc
    except requests.ConnectionError as exc:
        logger.warning("OpenAI API request failed: status=none type=connection_error")
        raise OpenAIAPIError(
            "OpenAI API 서버에 연결할 수 없습니다.",
            error_type="connection_error",
        ) from exc
    except requests.RequestException as exc:
        logger.warning("OpenAI API request failed: status=none type=request_error")
        raise OpenAIAPIError(
            "OpenAI API 연결 중 오류가 발생했습니다.",
            error_type="request_error",
        ) from exc

    if not response.ok:
        raise _api_error(response)

    payload = response.json()
    if payload.get("status") == "incomplete":
        reason = str(
            (payload.get("incomplete_details") or {}).get("reason")
            or "unknown"
        )
        logger.warning(
            "OpenAI API request failed: status=%s type=incomplete_%s",
            response.status_code,
            reason,
        )
        raise OpenAIAPIError(
            "OpenAI 답변 생성이 완료되지 않았습니다. 다시 시도해주세요.",
            status_code=response.status_code,
            error_type=f"incomplete_{reason}",
        )

    answer = _extract_output_text(payload)
    if not answer:
        logger.warning("OpenAI API request failed: status=%s type=empty_response", response.status_code)
        raise OpenAIAPIError(
            "OpenAI가 빈 응답을 반환했습니다. 다시 시도해주세요.",
            status_code=response.status_code,
            error_type="empty_response",
        )
    return answer
