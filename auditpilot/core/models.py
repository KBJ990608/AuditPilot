from dataclasses import dataclass


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

