import re
from difflib import SequenceMatcher
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

