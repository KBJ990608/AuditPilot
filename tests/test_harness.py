import json

from auditpilot.harness.eval import evaluate_cases
from auditpilot.llm.client import FixtureClient


def test_harness_scores_ten_fixture_cases():
    client = FixtureClient("fixtures/llm_responses.json")
    result = evaluate_cases("harness/golden/cases.jsonl", client)
    assert result["provider"] == "fixture"
    assert result["case_count"] == 10
    assert result["schema_compliance"] == 1.0
    assert result["forbidden_phrase_violations"] == 0
