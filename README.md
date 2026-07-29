# AuditPilot

[Live Demo](https://auditpilot.streamlit.app/)

AuditPilot은 감사자료 요청부터 업로드·매핑, 클렌징·검증, 분석·테스트,
문서화까지 반복 업무를 줄이고 감사인이 판단에 집중하도록 돕는 Streamlit 기반
감사업무 보조 앱입니다.

AuditPilot은 감사인의 결론을 대신하지 않습니다. 데이터 정리와 검증, 확인 필요
후보 산출, 질의 문안 및 조서 초안 작성을 지원하고 중요한 결과는 감사인이 직접
검토하고 승인하도록 설계했습니다.

## 주요 기능

AuditPilot은 감사 수행 흐름을 6개 단계로 구성합니다.

1. **병목 진단**
   - Planning, Execution, Completion 단계별 반복 업무와 Digital 활용 지점을
     보여줍니다.
2. **PBC 요청**
   - 계정별 요청자료, 감사주장, 수행절차와 제출 형식을 연결합니다.
3. **업로드·매핑**
   - xlsx 자료를 판별하고 회사마다 다른 원장 헤더를 표준 스키마에 맞춥니다.
   - 자동 매핑 결과는 감사인이 확인한 뒤 확정합니다.
4. **클렌징·검증**
   - 중복, 결측, 차대변 불일치, 기간 외 거래와 명세서 대사 차이를 확인합니다.
   - 예외를 임의로 삭제하지 않고 감사인의 검토 대상으로 남깁니다.
5. **분석·테스트**
   - 전기 대비 변동, 월별 추이와 거래처별 증감을 분석합니다.
   - 확인 필요 후보를 산출하고 고객사 후속 질의 문안을 생성합니다.
6. **문서화·판단**
   - 분석 결과와 숫자 근거를 조서 초안으로 정리합니다.
   - 승인 후 xlsx 또는 Markdown 조서 패키지를 내려받을 수 있습니다.

## 삼일이 AI

화면 오른쪽 아래에는 OpenAI 기반 플로팅 챗봇 `삼일이 AI`가 있습니다.

- 캐릭터를 드래그해 원하는 위치로 옮길 수 있습니다.
- `×` 버튼으로 말풍선을 닫고 캐릭터를 클릭해 다시 열 수 있습니다.
- PBC, 데이터 클렌징, 분석적 검토, 감사 테스트와 조서 작성 등을 질문할 수
  있습니다.
- 질문과 최근 답변은 현재 Streamlit 세션에만 보관됩니다.
- 브라우저에서 입력한 질문은 숨겨진 Streamlit 통로를 거쳐 서버 측
  `ask_openai` 함수로 전달됩니다.
- 서버는 OpenAI `/v1/responses` API를 호출하고 받은 답변을 기존 말풍선 UI에
  표시합니다.

API 키는 브라우저로 전달하지 않으며 Python, JavaScript 또는 설정 예제 파일에
하드코딩하지 않습니다. 삼일이는 감사 판단을 대신하지 않고 사용 흐름과 확인
절차를 안내하는 보조 도구입니다.

## 데모 실행 순서

1. `③ 업로드·매핑`에서 `데모 샘플 불러오기`를 누릅니다.
2. 매핑 결과를 확인하고 `게이트 1 · 매핑 확정`을 누릅니다.
3. `④ 클렌징·검증`에서 `검증 실행`을 누릅니다.
4. `⑤ 분석·테스트`에서 `분석 실행`을 누릅니다.
5. Top 후보를 확인하고 후속 질의 문안을 생성합니다.
6. `게이트 2 · 질의 문안 승인`을 누릅니다.
7. `⑥ 문서화·판단`에서 조서 초안을 생성합니다.
8. `게이트 3 · 잠정결론 승인` 후 조서 패키지를 내려받습니다.

## 로컬 실행

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py --server.port 8502
```

브라우저에서 <http://localhost:8502/>를 엽니다.

### macOS 또는 Linux

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run app.py
```

## OpenAI API 설정

AuditPilot은 다음 우선순위로 `OPENAI_API_KEY`를 읽습니다.

1. 운영체제 환경변수 `OPENAI_API_KEY`
2. Streamlit Secrets의 `OPENAI_API_KEY`
3. 프로젝트 루트의 로컬 `.env`

로컬에서는 운영체제 환경변수를 한 번 등록하거나 `.env.example`을 `.env`로
복사해 사용할 수 있습니다. `.env`와 `.streamlit/secrets.toml`은 Git 추적에서
제외됩니다.

예제 파일에는 실제 키 대신 아래 문자열만 사용합니다.

```text
OPENAI_API_KEY=your_openai_api_key_here
```

모델은 기본적으로 `gpt-5`를 사용합니다. 다른 사용 가능한 모델을 지정하려면
실행 환경에 `OPENAI_MODEL`을 설정할 수 있습니다.

## Streamlit Community Cloud 배포

배포 설정은 다음과 같습니다.

```text
Repository: KBJ990608/AuditPilot
Branch: main
Main file path: app.py
Python version: 3.11
```

Streamlit Community Cloud의 **App settings → Secrets**에 실제 키를 등록합니다.

```toml
OPENAI_API_KEY = "실제 OpenAI API 키"
```

필요한 경우 모델도 함께 설정할 수 있습니다.

```toml
OPENAI_MODEL = "gpt-5"
```

실제 API 키는 GitHub 파일, 커밋 메시지, Actions 로그 또는 오류 메시지에
입력하지 마세요. 저장소에는 안전한 예제인 `.env.example`과
`.streamlit/secrets.toml.example`만 포함됩니다.

## 기술 구성

- Python 3.11
- Streamlit
- pandas
- openpyxl
- requests
- OpenAI Responses API
- pytest

OpenAI 호출은 `requests`로 직접 수행하며 `.env`는 프로젝트의 단일 로더가
읽습니다. 따라서 `openai`와 `python-dotenv` 패키지는 필요하지 않습니다.

## 테스트

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

테스트는 자료 판별, 헤더 매핑, 데이터 검증, 분석 후보 산출, 조서 생성, export,
승인 게이트와 삼일이 서버 연결 통로를 확인합니다.

## 보안 원칙

- 실제 OpenAI API 키는 저장소에 커밋하지 않습니다.
- 키의 전체값이나 일부값을 화면과 로그에 출력하지 않습니다.
- API 오류 로그에는 HTTP 상태코드와 오류 유형만 기록합니다.
- 사용자 화면에는 인증, 한도, 모델, 시간 초과와 기타 연결 오류를 구분해
  안내합니다.
- 업로드한 데이터와 AI 응답은 영구 데이터베이스에 저장하지 않습니다.

## 제한사항

- 샘플 데이터는 기능 검증용 가상 데이터입니다.
- 앱은 확인 필요 후보를 제시할 뿐 왜곡표시 여부나 감사의견을 판단하지
  않습니다.
- 삼일이 응답 품질과 속도는 OpenAI API, 계정 사용 한도와 네트워크 상태에
  영향을 받습니다.
- 실제 업무 적용 시 회사별 계정 구조, 중요성, 산업 특성과 내부 정책에 맞춘
  검증 규칙 및 보안 검토가 필요합니다.
