from io import BytesIO
from typing import Mapping, Sequence

import pandas as pd

from .models import Candidate, ComputedValue, ValidationReport, Workpaper
from .workpaper import render_workpaper_markdown


def export_markdown(workpaper: Workpaper, registry: Mapping[str, ComputedValue]) -> bytes:
    return render_workpaper_markdown(workpaper, registry).encode("utf-8")


def export_xlsx(workpaper: Workpaper, candidates: Sequence[Candidate], report: ValidationReport) -> bytes:
    output = BytesIO()
    workpaper_rows = [
        ("수행 목적", workpaper.objective), ("사용 자료", "\n".join(workpaper.source_documents)),
        ("수행 절차", "\n".join(workpaper.procedures)), ("주요 변동", workpaper.fluctuations_markdown),
        ("회사 설명", workpaper.management_explanation), ("추가 확인사항", "\n".join(workpaper.follow_ups)),
        ("잠정 결론", workpaper.provisional_conclusion),
    ]
    candidate_rows = [{"순위": c.rank, "분류": c.category, "대상": c.entity, "점수": c.score,
                       "감사주장": ", ".join(c.assertions), "근거": str(c.evidence)} for c in candidates]
    validation_rows = [{"룰": i.rule_id, "통과": i.passed, "메시지": i.message,
                        "예외행": str(i.exception_rows), "기대값": i.expected, "실제값": i.actual} for i in report.items]
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame(workpaper_rows, columns=["항목", "내용"]).to_excel(writer, sheet_name="조서 초안", index=False)
        pd.DataFrame(candidate_rows).to_excel(writer, sheet_name="확인 필요 후보", index=False)
        pd.DataFrame(validation_rows).to_excel(writer, sheet_name="검증 결과", index=False)
    return output.getvalue()
