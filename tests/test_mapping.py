import pandas as pd

from auditpilot.core.mapping import normalize_amount, propose_mapping


def test_mapping_exact_fuzzy_unknown():
    aliases = {"전표일자": ["전표일", "postingdate"], "대변": ["creditamount"]}
    result = propose_mapping(["전표일", "postingdat", "unrelated"], aliases, threshold=0.82)
    assert result.mapping["전표일"] == "전표일자"
    assert result.mapping["postingdat"] == "전표일자"
    assert "unrelated" in result.unmapped


def test_normalize_amount_parentheses():
    series = pd.Series(["1,200", "(1,200)", "-300", None])
    assert normalize_amount(series).tolist()[:3] == [1200, -1200, -300]

