from typing import Mapping


def score_candidate(evidence: Mapping[str, object], performance_materiality: int) -> int:
    score = 0
    if abs(float(evidence.get("change_amount", 0))) >= performance_materiality:
        score += 30
    rate = evidence.get("change_rate")
    if rate is not None and abs(float(rate)) >= .5:
        score += 25
    if rate is not None and abs(float(rate)) >= 1:
        score += 10
    if float(evidence.get("december_ratio", 0)) >= .25:
        score += 20
    if evidence.get("is_new"):
        score += 15
    if int(evidence.get("year_end_days", 999)) <= 5:
        score += 10
    return min(score, 100)

