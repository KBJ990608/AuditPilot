import os
from typing import Any

import requests

from auditpilot.settings import get_openai_api_key


SYSTEM_PROMPT = """당신은 AuditPilot의 감사업무 보조 챗봇 '삼일이 AI'입니다.
사용자의 질문에 자연스러운 한국어로 짧고 명확하게 답하세요.
PBC, 데이터 클렌징, 분석적 검토, 감사조서 작성 절차를 설명할 수 있습니다.
감사인의 전문적 판단이나 최종 결론을 대신하지 말고, 필요한 확인 절차와 증빙을 제안하세요.
사용자가 제공하지 않은 숫자나 사실을 만들어내지 마세요.
답변은 특별한 요청이 없으면 5문장 이내로 작성하세요."""


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


def ask_openai(question: str) -> str:
    api_key = get_openai_api_key()
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("OPENAI_MODEL", "gpt-5.6-sol")
    response = requests.post(
        f"{base_url}/responses",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "instructions": SYSTEM_PROMPT,
            "input": question,
            "max_output_tokens": 300,
        },
        timeout=30,
    )
    response.raise_for_status()
    answer = _extract_output_text(response.json())
    if not answer:
        raise RuntimeError("OpenAI가 빈 응답을 반환했습니다.")
    return answer
