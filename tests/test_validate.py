import pandas as pd

from auditpilot.core.validate import build_validation_report


def _gl():
    return pd.DataFrame([
        {"전표일자": "2025-12-31", "전표번호": "A", "거래처": "대성", "차변": 100, "대변": 0},
        {"전표일자": "2025-12-31", "전표번호": "A", "거래처": "대성", "차변": 0, "대변": 100},
        {"전표일자": "2026-01-03", "전표번호": "B", "거래처": None, "차변": 0, "대변": 50},
        {"전표일자": "2026-01-03", "전표번호": "B", "거래처": None, "차변": 0, "대변": 50},
    ])


def test_validation_five_rules():
    subledger = pd.DataFrame({"거래처": ["대성", "합계"], "잔액": [103, 103]})
    tb = pd.DataFrame({"계정코드": ["1100"], "계정명": ["매출채권"], "차변잔액": [100], "대변잔액": [0]})
    report = build_validation_report(_gl(), subledger, tb, target_year=2025)
    by_id = {item.rule_id: item for item in report.items}
    assert set(by_id) == {"V01_DUPLICATE", "V02_REQUIRED", "V03_BALANCE", "V04_PERIOD", "V05_RECONCILE"}
    assert len(by_id["V01_DUPLICATE"].exception_rows) == 2
    assert len(by_id["V02_REQUIRED"].exception_rows) == 2
    assert by_id["V03_BALANCE"].passed is False
    assert len(by_id["V04_PERIOD"].exception_rows) == 2
    assert by_id["V05_RECONCILE"].actual - by_id["V05_RECONCILE"].expected == 3

