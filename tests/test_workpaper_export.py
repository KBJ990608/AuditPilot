from io import BytesIO

import pandas as pd

from auditpilot.core.analytics import analyze, build_computed_values
from auditpilot.core.export import export_markdown, export_xlsx
from auditpilot.core.reviewer import review_numbers
from auditpilot.core.validate import build_validation_report
from auditpilot.core.workpaper import build_workpaper, render_workpaper_markdown
from auditpilot.data.make_sample import build_sample_bundle


def test_workpaper_review_and_export_three_sheets():
    bundle = build_sample_bundle()
    analytics = analyze(bundle.current, bundle.prior)
    registry = build_computed_values(analytics)
    narrative = "대성물산 매출은 280,000,000원으로 전기 대비 +180.0% 증가하여 추가 확인이 필요합니다."
    workpaper = build_workpaper(analytics, narrative, registry)
    assert workpaper.referenced_keys == [
        f"{analytics.candidates[0].candidate_id}.current_amount",
        f"{analytics.candidates[0].candidate_id}.change_rate",
    ]
    markdown = render_workpaper_markdown(workpaper, registry)
    review = review_numbers(markdown, registry)
    assert review.passed
    report = build_validation_report(bundle.current, bundle.subledger, bundle.trial_balance)
    xlsx = export_xlsx(workpaper, analytics.candidates, report)
    book = pd.ExcelFile(BytesIO(xlsx))
    assert book.sheet_names == ["조서 초안", "확인 필요 후보", "검증 결과"]
    assert export_markdown(workpaper, registry).startswith(b"# ")
