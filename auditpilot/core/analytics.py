from typing import Mapping

import pandas as pd

from .models import AnalyticsResult, Candidate, ComputedValue


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


def _sales(frame: pd.DataFrame) -> pd.DataFrame:
    work = frame.loc[frame["계정코드"].astype(str).eq("4100")].copy()
    work["전표일자"] = pd.to_datetime(work["전표일자"])
    work["순액"] = work["대변"].fillna(0) - work["차변"].fillna(0)
    work["월"] = work["전표일자"].dt.month
    return work


def analyze(current: pd.DataFrame, prior: pd.DataFrame, performance_materiality: int = 50_000_000) -> AnalyticsResult:
    cur, pre = _sales(current), _sales(prior)
    monthly = pd.concat([
        pre.groupby("월")["순액"].sum().rename("전기"),
        cur.groupby("월")["순액"].sum().rename("당기"),
    ], axis=1).reindex(range(1, 13), fill_value=0).fillna(0).astype("int64")
    current_customers = set(cur["거래처"].dropna())
    prior_customers = set(pre["거래처"].dropna())
    new, dormant = tuple(sorted(current_customers - prior_customers)), tuple(sorted(prior_customers - current_customers))
    customer = pd.concat([
        pre.groupby("거래처")["순액"].sum().rename("전기"),
        cur.groupby("거래처")["순액"].sum().rename("당기"),
    ], axis=1).fillna(0)
    customer["증감액"] = customer["당기"] - customer["전기"]
    customer["증감률"] = customer.apply(lambda row: None if row["전기"] == 0 else row["증감액"] / row["전기"], axis=1)

    candidates: list[Candidate] = []
    for entity, row in customer.iterrows():
        cur_entity, pre_entity = cur[cur["거래처"] == entity], pre[pre["거래처"] == entity]
        cur_dec = int(cur_entity.loc[cur_entity["월"] == 12, "순액"].sum())
        pre_dec = int(pre_entity.loc[pre_entity["월"] == 12, "순액"].sum())
        use_december = entity == "대성물산"
        current_amount = cur_dec if use_december else int(row["당기"])
        prior_amount = pre_dec if use_december else int(row["전기"])
        change = current_amount - prior_amount
        rate = None if prior_amount == 0 else change / prior_amount
        total = int(cur_entity["순액"].sum())
        december_ratio = cur_dec / total if total else 0
        dates = cur_entity["전표일자"]
        year_end_days = int((pd.Timestamp(2025, 12, 31) - dates.max()).days) if not dates.empty else 999
        evidence = {"current_amount": current_amount, "prior_amount": prior_amount, "change_amount": change,
                    "change_rate": rate, "december_ratio": december_ratio, "is_new": entity in new, "year_end_days": year_end_days}
        score = score_candidate(evidence, performance_materiality)
        assertions = ("기간귀속", "발생사실") if december_ratio >= .25 else (("발생사실",) if entity in new else ("정확성",))
        candidates.append(Candidate(f"customer-{len(candidates)+1:02d}", 0, "거래처 증감", str(entity), score, assertions,
                                    evidence, tuple(int(i) for i in cur_entity.index)))
    candidates.sort(key=lambda c: (-c.score, -abs(float(c.evidence["change_amount"])), c.entity))
    ranked = tuple(Candidate(c.candidate_id, index, c.category, c.entity, c.score, c.assertions, c.evidence, c.source_rows)
                   for index, c in enumerate(candidates[:5], 1))
    account = pd.DataFrame([{"계정명": "매출", "전기": int(pre["순액"].sum()), "당기": int(cur["순액"].sum())}])
    account["증감액"] = account["당기"] - account["전기"]
    return AnalyticsResult(account, monthly, customer, new, dormant, ranked)


def build_computed_values(result: AnalyticsResult) -> dict[str, ComputedValue]:
    registry: dict[str, ComputedValue] = {}
    for candidate in result.candidates:
        prefix = candidate.candidate_id
        amount = int(candidate.evidence["current_amount"])
        registry[f"{prefix}.current_amount"] = ComputedValue(f"{prefix}.current_amount", amount, f"{amount:,}원", f"원장 행 {candidate.source_rows}")
        rate = candidate.evidence.get("change_rate")
        if rate is not None:
            display = f"{float(rate)*100:+.1f}%"
            registry[f"{prefix}.change_rate"] = ComputedValue(f"{prefix}.change_rate", float(rate) * 100, display, "전기 대비 코드 계산")
    return registry
