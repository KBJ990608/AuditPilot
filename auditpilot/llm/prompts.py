COMMON_SYSTEM = """당신은 감사업무 보조 문안 생성기다. 제공된 사실과 수치만 사용하라.
새 수치, 감사의견 또는 단정적 결론을 생성하지 마라. 지정된 JSON 이외의 텍스트를 출력하지 마라."""


def mapping_prompt(headers: list[str]) -> str:
    return f"미지 헤더 {headers!r}를 표준 컬럼에 매핑하고 suggestions 배열 JSON으로 반환하라."


def query_prompt(entity: str, amount: str, rate: str) -> str:
    return f"대상={entity}; 당기금액={amount}; 증감률={rate}. question과 used_keys 배열 JSON으로 반환하라."


def workpaper_prompt(entity: str, amount: str, rate: str) -> str:
    return f"대상={entity}; 당기금액={amount}; 증감률={rate}. narrative와 used_keys 배열 JSON으로 반환하라."
