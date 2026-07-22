import json
from pathlib import Path
import time

from auditpilot.llm.client import LLMClient


def _cases(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def evaluate_cases(path: str | Path, client: LLMClient) -> dict:
    cases, rows = _cases(path), []
    started = time.perf_counter()
    for case in cases:
        before = time.perf_counter()
        response = client.generate(case["id"], "", json.dumps(case["input"], ensure_ascii=False))
        try:
            parsed = json.loads(response.content)
            schema_ok = all(key in parsed for key in case["expected_keys"])
        except (json.JSONDecodeError, TypeError):
            schema_ok = False
        forbidden = [phrase for phrase in case.get("forbidden_phrases", []) if phrase in response.content]
        rows.append({"id": case["id"], "schema_ok": schema_ok, "forbidden": forbidden,
                     "latency_ms": round((time.perf_counter() - before) * 1000, 3)})
    provider = client.generate(cases[0]["id"], "", "").provider if cases else "unknown"
    return {"provider": provider, "case_count": len(cases), "schema_compliance": sum(r["schema_ok"] for r in rows) / len(rows),
            "forbidden_phrase_violations": sum(bool(r["forbidden"]) for r in rows),
            "total_latency_ms": round((time.perf_counter() - started) * 1000, 3), "cases": rows}


def save_result(result: dict, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
