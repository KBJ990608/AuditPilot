from io import BytesIO

import pandas as pd

from auditpilot.core.analytics import analyze, build_computed_values
from auditpilot.core.export import export_xlsx
from auditpilot.core.reviewer import review_numbers
from auditpilot.core.validate import build_validation_report
from auditpilot.core.workpaper import build_workpaper, render_workpaper_markdown
from auditpilot.data.make_sample import build_sample_bundle


def test_pipeline_from_sample_to_export():
    bundle = build_sample_bundle()
    report = build_validation_report(bundle.current, bundle.subledger, bundle.trial_balance)
    assert {item.rule_id for item in report.items} == {"V01_DUPLICATE", "V02_REQUIRED", "V03_BALANCE", "V04_PERIOD", "V05_RECONCILE"}
    result = analyze(bundle.current, bundle.prior)
    registry = build_computed_values(result)
    narrative = "대성물산 매출은 280,000,000원으로 전기 대비 +180.0% 증가하여 추가 확인이 필요합니다."
    workpaper = build_workpaper(result, narrative, registry)
    assert review_numbers(render_workpaper_markdown(workpaper, registry), registry).passed
    exported = export_xlsx(workpaper, result.candidates, report)
    assert len(exported) > 1_000
    assert len(pd.ExcelFile(BytesIO(exported)).sheet_names) == 3
