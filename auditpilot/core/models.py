from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class MappingResult:
    mapping: dict[str, str]
    unmapped: tuple[str, ...]
    confidence: dict[str, float]


@dataclass(frozen=True)
class ValidationItem:
    rule_id: str
    passed: bool
    message: str
    exception_rows: tuple[int, ...] = ()
    expected: int | None = None
    actual: int | None = None


@dataclass(frozen=True)
class ValidationReport:
    items: tuple[ValidationItem, ...]
    passed: bool


@dataclass(frozen=True)
class ComputedValue:
    key: str
    value: int | float
    display: str
    source: str


@dataclass(frozen=True)
class NumericToken:
    raw: str
    value: float


@dataclass(frozen=True)
class ReviewResult:
    passed: bool
    tokens: tuple[NumericToken, ...]
    mismatches: tuple[NumericToken, ...]
    forbidden: tuple[str, ...]


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    rank: int
    category: str
    entity: str
    score: int
    assertions: tuple[str, ...]
    evidence: dict[str, int | float | str | bool | None]
    source_rows: tuple[int, ...]


@dataclass(frozen=True)
class AnalyticsResult:
    account_change: pd.DataFrame
    monthly_trend: pd.DataFrame
    customer_change: pd.DataFrame
    new_customers: tuple[str, ...]
    dormant_customers: tuple[str, ...]
    candidates: tuple[Candidate, ...]


@dataclass
class Workpaper:
    title: str
    objective: str
    source_documents: list[str]
    procedures: list[str]
    fluctuations_markdown: str
    management_explanation: str
    follow_ups: list[str]
    provisional_conclusion: str
    referenced_keys: list[str]
    approved: bool = False
