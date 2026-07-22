from enum import StrEnum
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

import pandas as pd


class DocumentType(StrEnum):
    CURRENT_GL = "당기원장"
    PRIOR_GL = "전기원장"
    TRIAL_BALANCE = "시산표"
    AR_SUBLEDGER = "매출채권명세서"
    UNKNOWN = "미분류"


def normalize_header(value: object) -> str:
    return "".join(ch for ch in str(value).lower() if ch not in " _()\n\t")


def read_tabular(source: str | Path | BinaryIO | bytes, sheet_name: str | int = 0) -> pd.DataFrame:
    if isinstance(source, bytes):
        source = BytesIO(source)
    name = str(getattr(source, "name", source)).lower()
    if name.endswith(".csv"):
        return pd.read_csv(source)
    return pd.read_excel(source, sheet_name=sheet_name)


def classify_document(df: pd.DataFrame, target_year: int = 2025) -> DocumentType:
    columns = {normalize_header(c) for c in df.columns}
    if {"계정코드", "차변잔액", "대변잔액"} <= columns:
        return DocumentType.TRIAL_BALANCE
    if {"거래처", "잔액"} <= columns and "전표번호" not in columns:
        return DocumentType.AR_SUBLEDGER
    gl_signature = {"전표일자", "전표번호", "차변", "대변"}
    if len(columns & gl_signature) / len(gl_signature) >= .75:
        date_col = next((c for c in df.columns if normalize_header(c) == "전표일자"), None)
        if date_col is None:
            return DocumentType.UNKNOWN
        years = pd.to_datetime(df[date_col], errors="coerce").dt.year.dropna()
        if years.empty or years.mode().empty:
            return DocumentType.UNKNOWN
        return DocumentType.CURRENT_GL if int(years.mode().iloc[0]) == target_year else DocumentType.PRIOR_GL
    return DocumentType.UNKNOWN
