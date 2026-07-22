from typing import Mapping

from .models import AnalyticsResult, ComputedValue, Workpaper

PROVISIONAL_CONCLUSION = "현재까지 확인된 변동 후보에 대해 회사 설명 및 증빙의 추가 확인이 필요하며, 본 초안만으로 감사 결론을 형성하지 않는다."


def build_workpaper(result: AnalyticsResult, narrative: str, registry: Mapping[str, ComputedValue]) -> Workpaper:
    selected_prefix = result.candidates[0].candidate_id if result.candidates else ""
    referenced = [key for key, value in registry.items() if key.startswith(f"{selected_prefix}.") and value.display in narrative]
    return Workpaper(
        title="매출 및 매출채권 분석적절차 조서",
        objective="매출 및 매출채권의 비경상적 변동과 추가 확인 필요 항목을 식별한다.",
        source_documents=["FY2025 매출원장", "FY2024 매출원장", "FY2025 시산표", "매출채권명세서"],
        procedures=["전기 대비 계정·거래처별 증감 계산", "월별 추이 및 기말 집중 거래 검토", "확인 필요 후보 우선순위화"],
        fluctuations_markdown=narrative,
        management_explanation="미수취",
        follow_ups=["회사의 변동 원인 설명과 관련 증빙을 수취하여 수치와 정합성을 확인한다."],
        provisional_conclusion=PROVISIONAL_CONCLUSION,
        referenced_keys=referenced,
    )


def render_workpaper_markdown(workpaper: Workpaper, registry: Mapping[str, ComputedValue]) -> str:
    references = "\n".join(f"- `{key}`: {registry[key].source}" for key in workpaper.referenced_keys)
    return f"""# {workpaper.title}

> DRAFT — 감사인 승인 전

## 수행 목적
{workpaper.objective}

## 사용 자료
{chr(10).join(f'- {item}' for item in workpaper.source_documents)}

## 수행 절차
{chr(10).join(f'- {item}' for item in workpaper.procedures)}

## 주요 변동
{workpaper.fluctuations_markdown}

## 회사 설명
{workpaper.management_explanation}

## 추가 확인사항
{chr(10).join(f'- {item}' for item in workpaper.follow_ups)}

## 잠정 결론
{workpaper.provisional_conclusion}

## 근거 참조
{references}
"""
