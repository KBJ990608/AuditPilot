import re
from difflib import SequenceMatcher
import json
from pathlib import Path
from typing import Mapping, Sequence

import pandas as pd

from .models import MappingResult


def _key(value: object) -> str:
    return re.sub(r"[\s_()]+", "", str(value)).lower()


def propose_mapping(headers: Sequence[str], aliases: Mapping[str, Sequence[str]], threshold: float = .82) -> MappingResult:
    candidates = [(canonical, _key(alias)) for canonical, values in aliases.items() for alias in (canonical, *values)]
    mapping, confidence, unmapped = {}, {}, []
    for header in headers:
        normalized = _key(header)
        exact = next((canonical for canonical, alias in candidates if normalized == alias), None)
        if exact:
            mapping[header], confidence[header] = exact, 1.0
            continue
        canonical, score = max(((c, SequenceMatcher(None, normalized, a).ratio()) for c, a in candidates), key=lambda x: x[1])
        if score >= threshold:
            mapping[header], confidence[header] = canonical, score
        else:
            unmapped.append(header)
    return MappingResult(mapping, tuple(unmapped), confidence)


def normalize_amount(series: pd.Series) -> pd.Series:
    def parse(value):
        if pd.isna(value):
            return pd.NA
        text = str(value).strip().replace(",", "")
        negative = text.startswith("(") and text.endswith(")")
        text = text.strip("()")
        number = float(text or 0)
        return int(-number if negative else number)
    return series.map(parse).astype("Int64")


def apply_mapping(df: pd.DataFrame, mapping: Mapping[str, str]) -> pd.DataFrame:
    return df.rename(columns=dict(mapping)).copy()


def normalize_gl(df: pd.DataFrame) -> pd.DataFrame:
    required = ["전표일자", "전표번호", "계정코드", "계정명", "거래처", "차변", "대변", "적요", "전표유형"]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"필수 컬럼 미매핑: {', '.join(missing)}")
    work = df[required].copy()
    work["전표일자"] = pd.to_datetime(work["전표일자"], errors="coerce")
    work["차변"] = normalize_amount(work["차변"])
    work["대변"] = normalize_amount(work["대변"])
    for column in ("전표번호", "계정코드", "계정명", "거래처", "적요", "전표유형"):
        work[column] = work[column].astype("string")
    work["원본행"] = df.index + 2
    return work


def save_confirmed_mapping(result: MappingResult, file_hash: str, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{file_hash[:12]}.json"
    path.write_text(json.dumps({"mapping": result.mapping, "unmapped": result.unmapped, "confidence": result.confidence}, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
