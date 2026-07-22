import re
from typing import Mapping

from .models import ComputedValue, NumericToken, ReviewResult

FORBIDDEN = ("문제없음", "적정하다", "왜곡표시가 없다")
TOKEN_RE = re.compile(r"[+-]?\d{1,3}(?:,\d{3})*(?:\.\d+)?\s*(?:%|억원|백만원|천원|원|건)")


def _numeric(raw: str) -> float:
    clean = raw.replace(",", "").replace(" ", "")
    factors = {"억원": 100_000_000, "백만원": 1_000_000, "천원": 1_000, "원": 1, "%": 1, "건": 1}
    for unit in sorted(factors, key=len, reverse=True):
        if clean.endswith(unit):
            return float(clean[:-len(unit)]) * factors[unit]
    raise ValueError(raw)


def extract_numeric_tokens(text: str) -> list[NumericToken]:
    return [NumericToken(match.group(), _numeric(match.group())) for match in TOKEN_RE.finditer(text)]


def contains_forbidden_conclusion(text: str) -> list[str]:
    return [phrase for phrase in FORBIDDEN if phrase in text]


def review_numbers(text: str, allowed: Mapping[str, ComputedValue]) -> ReviewResult:
    tokens = tuple(extract_numeric_tokens(text))
    allowed_values = {_numeric(item.display) for item in allowed.values()}
    mismatches = tuple(token for token in tokens if token.value not in allowed_values)
    forbidden = tuple(contains_forbidden_conclusion(text))
    return ReviewResult(not mismatches and not forbidden, tokens, mismatches, forbidden)

