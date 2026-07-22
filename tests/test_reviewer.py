from auditpilot.core.models import ComputedValue
from auditpilot.core.reviewer import contains_forbidden_conclusion, review_numbers


def _allowed():
    return {
        "sales": ComputedValue("sales", 280_000_000, "280,000,000원", "당기원장"),
        "rate": ComputedValue("rate", 180.0, "+180.0%", "전기 대비"),
    }


def test_numeric_review_accepts_registered_values():
    result = review_numbers("매출은 280,000,000원이며 전기 대비 +180.0% 증가했습니다.", _allowed())
    assert result.passed
    assert not result.mismatches


def test_numeric_review_blocks_mismatch():
    result = review_numbers("매출은 281,000,000원이며 전기 대비 +180.0% 증가했습니다.", _allowed())
    assert not result.passed
    assert result.mismatches


def test_forbidden_conclusion():
    assert contains_forbidden_conclusion("검토 결과 문제없음.") == ["문제없음"]

