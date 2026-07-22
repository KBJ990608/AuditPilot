from auditpilot.data.make_sample import build_sample_bundle


def test_sample_generator_invariants():
    bundle = build_sample_bundle()
    duplicated = bundle.current.duplicated(["전표번호", "차변", "대변"], keep=False)
    assert duplicated.sum() == 2
    assert bundle.current["거래처"].isna().sum() == 1
    detail_total = bundle.subledger.loc[bundle.subledger["거래처"] != "합계", "잔액"].sum()
    tb_total = bundle.trial_balance.loc[bundle.trial_balance["계정코드"] == "1100", "차변잔액"].iloc[0]
    assert detail_total - tb_total == 3_000_000
    assert (bundle.current["전표일자"].dt.year == 2026).sum() == 1
    assert "새롬리테일" not in set(bundle.prior["거래처"].dropna())
    assert "정우물산" not in set(bundle.current["거래처"].dropna())
