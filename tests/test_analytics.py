from auditpilot.core.analytics import analyze, build_computed_values, score_candidate
from auditpilot.data.make_sample import build_sample_bundle


def test_score_boundaries_and_cap():
    assert score_candidate({"change_amount": 49_999_999}, 50_000_000) == 0
    assert score_candidate({"change_amount": 50_000_000}, 50_000_000) == 30
    evidence = {"change_amount": 100_000_000, "change_rate": 1.8, "december_ratio": .30, "is_new": True, "year_end_days": 3}
    assert score_candidate(evidence, 50_000_000) == 100


def test_analytics_injected_signals():
    bundle = build_sample_bundle()
    result = analyze(bundle.current, bundle.prior, performance_materiality=50_000_000)
    assert result.candidates[0].entity == "대성물산"
    assert "새롬리테일" in result.new_customers
    assert "정우물산" in result.dormant_customers
    assert result.monthly_trend.loc[12, "당기"] > result.monthly_trend.loc[1:11, "당기"].mean() * 2.4
    registry = build_computed_values(result)
    assert registry
    assert all(value.source for value in registry.values())
