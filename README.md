# AuditPilot

AI 기반 PBC 자료 수집·검증·증감분석 Assistant입니다. 감사자료 요청부터 표준화, 검증, 분석적절차, 질의 문안, 조서 초안 및 Export까지 하나의 Human-in-the-loop 흐름으로 연결합니다.

> **숫자는 결정적 코드가, 문장은 LLM이, 결론은 감사인이 만듭니다.**

## 주요 기능

- 계정–감사주장–수행절차가 연결된 PBC 요청 리스트
- 회사별 원장 헤더의 표준 스키마 매핑과 감사인 확정 게이트
- 중복·결측·차대변·기간·명세서 대사 결정적 검증 5종
- 전기 대비·월별·거래처별 분석과 확인 필요 후보 Top 5
- 코드 산출 수치만 사용하는 고객 질의와 감사조서 초안
- 문서 내 금액·비율 전수 대조 및 불일치 시 승인 차단
- xlsx 3시트와 Markdown Export
- API 키 없이 작동하는 fixture provider와 골든셋 10건 Harness

## 실행

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run app.py
```

브라우저에서 `http://localhost:8501`을 열고 다음 순서로 진행합니다.

1. `데모 샘플 불러오기`
2. `게이트 1 · 매핑 확정`
3. 검증 및 분석 실행
4. 후속 질의 생성 후 `게이트 2` 승인
5. 조서 생성·Review 통과 후 `게이트 3` 승인
6. xlsx 또는 Markdown 다운로드

샘플 xlsx 4종을 직접 업로드해도 동일한 흐름이 작동합니다. 샘플 파일은 `auditpilot/data/samples/`에 있습니다.

## 구조

```text
app.py                         Streamlit UI와 HITL 게이트
auditpilot/core/               결정적 데이터 처리·분석·문서 검증
auditpilot/llm/                Fixture/OpenAI-compatible provider
auditpilot/harness/            결정적 평가 코드
harness/golden/                골든셋 10건
fixtures/                      캐시 응답·오류 조서
tests/                         단위·통합·UI 테스트
docs/기획서.md                  As-Is 분석과 요구사항
docs/설계서.md                  데이터 계약과 함수 설계
```

`core`는 `llm`을 import하지 않습니다. LLM에는 원본 원장이 아니라 코드가 계산한 표시 문자열만 전달됩니다. 모든 LLM 문안은 `reviewer.py`의 수치 전수 검증과 금지 표현 검사를 거칩니다.

## 테스트

```bash
.venv/bin/pytest -q
```

- 단위 테스트: 매핑, 정규화, 검증 룰, 후보 점수, 수치 검증
- 통합 테스트: 샘플 → 검증 → 분석 → 조서 → Review → Export
- UI 테스트: Streamlit 6개 탭 렌더링, 세 승인 게이트, 전체 흐름 5회 반복
- Export 테스트: 생성 xlsx 재개방 및 3개 시트 확인

자세한 결과는 [QA 보고서](docs/QA_REPORT.md)를 참고합니다.

## LLM Provider와 Harness

기본값은 `FixtureClient`입니다. 이는 사전 생성 응답을 반환하며 UI에 캐시임을 명확히 표시합니다. `OpenAICompatibleClient`는 OpenAI 호환 클라우드 API 또는 Ollama의 호환 endpoint를 같은 인터페이스로 사용할 수 있습니다.

현재 저장된 `harness/results/fixture.json`은 **실모델 성능 결과가 아니라 파이프라인 스모크 테스트**입니다. 클라우드 모델과 로컬 모델의 비교 결과는 실제 API 키·Ollama 환경에서만 생성해야 하며 fixture 결과를 실모델 결과로 표현하지 않습니다.

## 한계

- 확인 필요 후보를 제안할 뿐 왜곡표시나 감사의견을 판단하지 않습니다.
- 수행중요성은 데모 기본값이며 실제 업무에서는 감사인이 결정해야 합니다.
- 거래 수준 원장–명세서 매칭, P/Q 분해, 조회서·주석 검토는 범위 밖입니다.
- 샘플 데이터는 기능 검증을 위해 이상 징후를 의도적으로 주입한 가상 자료입니다.
