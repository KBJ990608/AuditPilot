from dataclasses import dataclass
from pathlib import Path
import random

import pandas as pd


CUSTOMERS = [
    "대성물산", "새롬리테일", "한강마트", "동서상사", "미래유통", "청운상회", "가온마켓", "중앙유통",
    "세진상사", "태양마트", "명진유통", "우리상회", "삼우물산", "제일마트", "백두상사", "한빛리테일",
    "성진유통", "대양상사", "보람마트", "정우물산",
]


@dataclass(frozen=True)
class SampleBundle:
    current: pd.DataFrame
    prior: pd.DataFrame
    trial_balance: pd.DataFrame
    subledger: pd.DataFrame


def _journal(year: int, voucher: str, date: pd.Timestamp, customer: str | None, amount: int) -> list[dict]:
    common = {"전표일자": date, "전표번호": voucher, "거래처": customer, "적요": "상품 매출", "전표유형": "자동"}
    return [
        {**common, "계정코드": "1100", "계정명": "매출채권", "차변": amount, "대변": 0},
        {**common, "계정코드": "4100", "계정명": "매출", "차변": 0, "대변": amount},
    ]


def _year(year: int) -> pd.DataFrame:
    rng = random.Random(20250722 + year)
    rows: list[dict] = []
    active = [c for c in CUSTOMERS if c != ("새롬리테일" if year == 2024 else "정우물산")]
    voucher = 1
    for month in range(1, 13):
        for customer in active:
            if year == 2025 and customer == "새롬리테일" and month < 7:
                continue
            if customer == "대성물산":
                amount = 280_000_000 if (year, month) == (2025, 12) else 100_000_000 if (year, month) == (2024, 12) else 20_000_000
                day = 29 if (year, month) == (2025, 12) else 15
            else:
                amount = 1_000_000 if (year, month) == (2025, 12) else (8_000_000 if customer == "새롬리테일" else 5_000_000)
                day = rng.randint(3, 24)
            rows.extend(_journal(year, f"{year}-{voucher:04d}", pd.Timestamp(year, month, day), customer, amount))
            voucher += 1
    target = 600 if year == 2025 else 550
    while len(rows) + 2 <= target:
        date = pd.Timestamp(year, rng.randint(1, 11), rng.randint(1, 25))
        common = {"전표일자": date, "전표번호": f"{year}-F{voucher:04d}", "거래처": "사내", "적요": "운영비", "전표유형": "자동"}
        amount = rng.randint(10, 100) * 10_000
        rows.extend([
            {**common, "계정코드": "5100", "계정명": "판매관리비", "차변": amount, "대변": 0},
            {**common, "계정코드": "1000", "계정명": "현금", "차변": 0, "대변": amount},
        ])
        voucher += 1
    return pd.DataFrame(rows)


def build_sample_bundle() -> SampleBundle:
    current = _year(2025)
    prior = _year(2024)
    # 데이터 품질 예외: 중복 2행, 결측 1행, 기간 외 1행.
    duplicate_source = current[(current["계정코드"] == "4100") & (current["거래처"] == "한강마트")].iloc[[0]].copy()
    current = pd.concat([current, duplicate_source], ignore_index=True)
    current.loc[duplicate_source.index[0], "거래처"] = None
    outside = _journal(2026, "2026-X001", pd.Timestamp(2026, 1, 3), "대성물산", 9_000_000)[0]
    current = pd.concat([current, pd.DataFrame([outside])], ignore_index=True)
    current["전표일자"] = pd.to_datetime(current["전표일자"])
    prior["전표일자"] = pd.to_datetime(prior["전표일자"])

    ar_balance = 420_000_000
    detail = pd.DataFrame({"거래처": ["대성물산", "한강마트", "새롬리테일"], "잔액": [300_000_000, 80_000_000, 43_000_000]})
    subledger = pd.concat([detail, pd.DataFrame([{"거래처": "합계", "잔액": int(detail["잔액"].sum())}])], ignore_index=True)
    trial_balance = pd.DataFrame([
        {"계정코드": "1100", "계정명": "매출채권", "차변잔액": ar_balance, "대변잔액": 0},
        {"계정코드": "4100", "계정명": "매출", "차변잔액": 0, "대변잔액": int(current.loc[current["계정코드"] == "4100", "대변"].sum())},
    ])
    return SampleBundle(current, prior, trial_balance, subledger)


def write_sample_files(directory: str | Path) -> list[Path]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    bundle = build_sample_bundle()
    current_raw = bundle.current.rename(columns={
        "전표일자": "Posting Dt", "전표번호": "Voucher No", "계정코드": "Acct Cd", "계정명": "계정과목",
        "거래처": "Customer", "차변": "Debit Amount", "대변": "Amt(CR)", "적요": "Description", "전표유형": "Entry Type",
    })
    files = [directory / "한빛유통_FY2025_매출원장_raw.xlsx", directory / "한빛유통_FY2024_매출원장.xlsx",
             directory / "한빛유통_FY2025_시산표.xlsx", directory / "한빛유통_FY2025_매출채권명세서.xlsx"]
    for frame, path in zip((current_raw, bundle.prior, bundle.trial_balance, bundle.subledger), files):
        frame.to_excel(path, index=False)
    return files


if __name__ == "__main__":
    write_sample_files(Path(__file__).parent / "samples")
