from auditpilot.core.analytics import score_candidate


def test_score_boundaries_and_cap():
    assert score_candidate({"change_amount": 49_999_999}, 50_000_000) == 0
    assert score_candidate({"change_amount": 50_000_000}, 50_000_000) == 30
    evidence = {"change_amount": 100_000_000, "change_rate": 1.8, "december_ratio": .30, "is_new": True, "year_end_days": 3}
    assert score_candidate(evidence, 50_000_000) == 100

