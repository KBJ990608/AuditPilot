import pandas as pd

from .models import ValidationItem, ValidationReport


def build_validation_report(gl: pd.DataFrame, subledger: pd.DataFrame, trial_balance: pd.DataFrame, target_year: int = 2025) -> ValidationReport:
    work = gl.copy()
    work["전표일자"] = pd.to_datetime(work["전표일자"], errors="coerce")
    duplicate = work.duplicated(["전표번호", "차변", "대변"], keep=False)
    required = work[["전표일자", "전표번호", "거래처", "차변", "대변"]].isna().any(axis=1)
    sums = work.groupby("전표번호")[["차변", "대변"]].sum()
    unbalanced_ids = set(sums.index[sums["차변"] != sums["대변"]])
    unbalanced = work["전표번호"].isin(unbalanced_ids)
    outside = work["전표일자"].dt.year.ne(target_year)
    detail = subledger.loc[subledger["거래처"].astype(str).ne("합계"), "잔액"].sum()
    tb_row = trial_balance.loc[trial_balance["계정코드"].astype(str).eq("1100")].iloc[0]
    expected, actual = int(tb_row["차변잔액"] - tb_row["대변잔액"]), int(detail)
    items = (
        ValidationItem("V01_DUPLICATE", not duplicate.any(), "중복행", tuple(work.index[duplicate])),
        ValidationItem("V02_REQUIRED", not required.any(), "필수값 결측", tuple(work.index[required])),
        ValidationItem("V03_BALANCE", not unbalanced.any(), "전표 차대변", tuple(work.index[unbalanced])),
        ValidationItem("V04_PERIOD", not outside.any(), "기간 외 전표", tuple(work.index[outside])),
        ValidationItem("V05_RECONCILE", expected == actual, "명세서-시산표 대사", expected=expected, actual=actual),
    )
    return ValidationReport(items, all(item.passed for item in items))

