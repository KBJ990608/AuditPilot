import base64
import json
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from auditpilot.core.analytics import analyze, build_computed_values
from auditpilot.core.export import export_markdown, export_xlsx
from auditpilot.core.ingest import DocumentType, classify_document, read_tabular
from auditpilot.core.mapping import apply_mapping, normalize_gl, propose_mapping
from auditpilot.core.reviewer import review_numbers
from auditpilot.core.validate import build_validation_report
from auditpilot.core.workpaper import build_workpaper, render_workpaper_markdown
from auditpilot.data.make_sample import SampleBundle, build_sample_bundle
from auditpilot.llm.client import FixtureClient
from auditpilot.state import can_approve_query, can_approve_workpaper, can_validate, invalidate_downstream

ROOT = Path(__file__).parent
FIXTURE = FixtureClient(ROOT / "fixtures/llm_responses.json")
ALIASES = json.loads((ROOT / "config/header_aliases.json").read_text(encoding="utf-8"))
BOT_IMAGE = base64.b64encode((ROOT / "assets/auditpilot_bot.png").read_bytes()).decode("ascii")
LOGO_PATH = ROOT / "assets/logo2.svg"
LOGO_IMAGE = base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")

st.set_page_config(page_title="AuditPilot", page_icon="🧭", layout="wide")
st.markdown("""
<style>
[data-testid="stSidebar"], [data-testid="collapsedControl"] {display: none}
[data-testid="stAppViewContainer"] > .main {margin-left: 0}
[data-testid="stToolbar"] {display: none}
.stHeading a, [data-testid="stHeading"] a {display: none}
.block-container {padding-top: 1.7rem; max-width: 1280px}
[data-testid="stMetricValue"] {font-size: 1.55rem}
.draft {border:1px solid #d97706; background:#fffbeb; padding:.7rem 1rem; border-radius:.5rem; color:#92400e}
.cache {display:inline-block; padding:.15rem .5rem; border-radius:1rem; background:#e0f2fe; color:#075985; font-size:.78rem}
.app-logo-row {display:flex; align-items:center; gap:.35rem; margin:.15rem 0 .35rem}
.app-logo-row img {width:126px; height:auto; display:block}
.app-logo-row .app-title-text {margin:0 0 0 -1.45rem; color:#2f313d; font-size:2.85rem; font-weight:800; line-height:1; letter-spacing:0}
@media (max-width: 720px) {
  .app-logo-row {gap:.25rem}
  .app-logo-row img {width:96px}
  .app-logo-row .app-title-text {font-size:2.1rem; margin-left:-.85rem}
}
</style>""", unsafe_allow_html=True)

DEFAULTS = {
    "bundle": None, "mapping_confirmed": False, "validation_report": None, "analytics_result": None,
    "registry": None, "query_text": None, "query_review_passed": False, "query_approved": False,
    "workpaper": None, "workpaper_review_passed": False, "workpaper_approved": False,
}
for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value

PBC_CATALOG = {
    "매출": {
        "request": "매출 원장 및 월별 매출 집계표",
        "assertions": "발생사실·정확성·기간귀속",
        "procedures": "원장 대사, 월별·거래처별 증감분석, 컷오프 테스트",
        "format": "xlsx · 거래일자/거래처/전표번호/금액 포함",
        "message": "매출 검토를 위해 당기 매출 원장과 월별 매출 집계표를 제출해 주십시오. 주요 거래처, 전표번호, 출하·검수일, 세금계산서일, 매출 인식일이 확인 가능해야 합니다.",
    },
    "매출채권": {
        "request": "매출채권 거래처별 명세서",
        "assertions": "실재성·평가·기간귀속",
        "procedures": "시산표 대사, 거래처별 증감분석, 회수내역 검토",
        "format": "xlsx · 기준일 2025-12-31",
        "message": "매출채권 검토를 위해 기준일 현재 거래처별 잔액 명세서와 기말 이후 회수내역을 제출해 주십시오. 거래처명, 채권 발생일, 잔액, 회수일, 회수금액이 포함되어야 합니다.",
    },
    "현금및현금성자산": {
        "request": "은행별 잔액명세서 및 은행조회서",
        "assertions": "실재성·완전성·권리와 의무",
        "procedures": "은행조회, 장부-은행잔액 대사, 미결제 수표·입금 검토",
        "format": "xlsx/PDF · 기준일 잔액 및 계좌번호 포함",
        "message": "현금및현금성자산 검토를 위해 기준일 은행별 잔액명세서, 은행조회서, 은행조정표를 제출해 주십시오. 계좌번호, 통화, 장부잔액, 은행잔액, 미결제 항목이 확인 가능해야 합니다.",
    },
    "재고자산": {
        "request": "재고수불부 및 품목별 재고명세서",
        "assertions": "실재성·평가·완전성",
        "procedures": "실사 입회, 수불부 대사, 저가·진부화 검토",
        "format": "xlsx · 품목코드/수량/단가/금액 포함",
        "message": "재고자산 검토를 위해 품목별 재고명세서와 재고수불부를 제출해 주십시오. 품목코드, 보관장소, 수량, 단가, 금액, 입출고일, 진부화 판단 정보가 포함되어야 합니다.",
    },
    "유형자산": {
        "request": "유형자산 명세서 및 취득·처분 증빙",
        "assertions": "실재성·권리와 의무·평가",
        "procedures": "자산대장 대사, 취득·처분 승인 검토, 감가상각 재계산",
        "format": "xlsx/PDF · 자산번호/취득일/취득가액 포함",
        "message": "유형자산 검토를 위해 자산대장, 당기 취득·처분 내역, 주요 계약서와 세금계산서를 제출해 주십시오. 자산번호, 취득일, 취득가액, 내용연수, 감가상각누계액이 확인 가능해야 합니다.",
    },
    "매입채무": {
        "request": "매입채무 거래처별 명세서",
        "assertions": "완전성·기간귀속·평가",
        "procedures": "거래처별 잔액 대사, 기말 이후 지급 검토, 미계상 채무 탐색",
        "format": "xlsx · 기준일 잔액 및 지급일 포함",
        "message": "매입채무 검토를 위해 기준일 거래처별 잔액명세서와 기말 이후 지급내역을 제출해 주십시오. 거래처명, 세금계산서일, 입고일, 잔액, 지급일이 포함되어야 합니다.",
    },
    "미지급비용": {
        "request": "미지급비용 계정별 산출명세서",
        "assertions": "완전성·정확성·기간귀속",
        "procedures": "산출근거 검토, 기말 이후 지급 대사, 전기 대비 증감분석",
        "format": "xlsx/PDF · 산출식 및 지급예정일 포함",
        "message": "미지급비용 검토를 위해 계정별 산출명세서와 기말 이후 지급자료를 제출해 주십시오. 발생기간, 산출근거, 지급예정일, 실제 지급일이 확인 가능해야 합니다.",
    },
    "차입금": {
        "request": "차입금 명세서 및 금융기관 약정서",
        "assertions": "완전성·권리와 의무·표시",
        "procedures": "금융기관 조회, 이자 재계산, 약정사항·유동성 분류 검토",
        "format": "xlsx/PDF · 차입처/만기/이자율 포함",
        "message": "차입금 검토를 위해 차입처별 명세서, 금융기관 조회서, 약정서를 제출해 주십시오. 원금, 이자율, 만기, 담보, 약정 위반 여부와 유동성 분류 근거가 포함되어야 합니다.",
    },
    "매출원가": {
        "request": "매출원가 산출명세서 및 원가 배부표",
        "assertions": "정확성·완전성·기간귀속",
        "procedures": "원가 산출 재계산, 재고수불 대사, 전기 대비·월별 분석",
        "format": "xlsx · 품목/원가요소/배부기준 포함",
        "message": "매출원가 검토를 위해 매출원가 산출명세서, 원가 배부표, 재고수불부를 제출해 주십시오. 품목, 원가요소, 배부기준, 월별 금액이 확인 가능해야 합니다.",
    },
    "판매관리비": {
        "request": "판매관리비 계정별 원장",
        "assertions": "발생사실·정확성·분류",
        "procedures": "계정별 증감분석, 주요 증빙 테스트, 비용 귀속기간 검토",
        "format": "xlsx · 계정/거래처/전표번호/금액 포함",
        "message": "판매관리비 검토를 위해 계정별 원장과 주요 비용 증빙을 제출해 주십시오. 계정명, 거래처, 전표번호, 거래일자, 금액, 적요가 포함되어야 합니다.",
    },
}

AUDIT_BOTTLENECKS = [
    {
        "단계": "Planning",
        "비효율": "전기 PBC를 관성적으로 재사용해 요청 목적과 위험 연결이 흐려짐",
        "디지털 활용": "계정·감사주장·수행절차가 연결된 요청 리스트 생성",
        "기대효과": "불필요한 자료 요청 감소, 클라이언트 커뮤니케이션 명확화",
        "감사인 판단": "중요계정, 위험평가, 요청 범위의 적정성",
    },
    {
        "단계": "Execution",
        "비효율": "회사마다 다른 GL, 명세서, 월보, backdata 양식을 수작업으로 정리",
        "디지털 활용": "헤더 매핑, 표준 스키마 변환, 중복·결측·차대변 검증",
        "기대효과": "클렌징 시간 단축, 오류 조기 발견, 재작업 감소",
        "감사인 판단": "매핑 확정, 예외의 원인 판단, 추가 절차 필요성",
    },
    {
        "단계": "Execution",
        "비효율": "증감분석, 월별 추이, 거래처별 변동을 엑셀에서 반복 확인",
        "디지털 활용": "전기 대비 변동, 이상치, Top 후보 자동 산출과 시각화",
        "기대효과": "의미 있는 변동을 빨리 식별하고 질문 품질 개선",
        "감사인 판단": "변동의 Nature, P/Q 요인, 회사 설명의 타당성",
    },
    {
        "단계": "Execution",
        "비효율": "표본 선정, 조건별 필터링, 재계산 같은 규칙적 테스트를 반복 수행",
        "디지털 활용": "조건 기반 거래 추출, 컷오프·재계산·대사 로직 실행",
        "기대효과": "반복 테스트 속도 향상, 누락 위험 감소",
        "감사인 판단": "테스트 목적, 표본 조건, 예외 해석과 결론",
    },
    {
        "단계": "Completion",
        "비효율": "수행한 절차와 숫자 근거를 조서·리뷰 답변으로 다시 정리",
        "디지털 활용": "조서 초안, 증감분석 문장, 리뷰 답변 구조화",
        "기대효과": "문서화 부담 감소, 수치 불일치와 누락 감소",
        "감사인 판단": "최종 결론, 미해결 이슈 평가, 조서 승인",
    },
]

TEST_LIBRARY = [
    {"테스트": "컷오프 테스트", "대상": "매출·매입", "자동화 포인트": "기말 전후 거래 추출", "감사인 판단": "인식시점과 증빙의 타당성"},
    {"테스트": "전기 대비 증감분석", "대상": "주요 계정", "자동화 포인트": "증감액·증감률·월별 추이 산출", "감사인 판단": "변동 원인의 합리성"},
    {"테스트": "거래처별 이상치 탐지", "대상": "매출채권·매출", "자동화 포인트": "신규·급증 거래처 Top 후보 산출", "감사인 판단": "추가 질의와 증빙 범위"},
    {"테스트": "조회서 대사", "대상": "현금·차입금", "자동화 포인트": "회신잔액과 회사제시자료 비교", "감사인 판단": "차이 원인과 대체절차"},
    {"테스트": "재계산", "대상": "리스·감가상각·이자", "자동화 포인트": "계약조건 기반 계산값 비교", "감사인 판단": "가정과 입력값의 적정성"},
]

JUDGMENT_BOUNDARIES = [
    "AI와 자동화는 자료 정리, 후보 산출, 초안 작성까지 지원합니다.",
    "감사인은 위험평가, 테스트 조건, 예외 해석, 회사 설명의 타당성, 최종 결론을 판단합니다.",
    "승인 게이트를 통과하기 전에는 질의 문안과 조서 결론이 외부 발송 또는 확정되지 않습니다.",
]

def load_bundle(bundle: SampleBundle) -> None:
    st.session_state.bundle = bundle
    st.session_state.mapping_confirmed = False
    invalidate_downstream(st.session_state, "mapping")


def uploaded_bundle(files) -> SampleBundle:
    classified = {}
    for file in files:
        frame = read_tabular(file)
        direct_type = classify_document(frame)
        if direct_type in (DocumentType.TRIAL_BALANCE, DocumentType.AR_SUBLEDGER):
            classified[direct_type] = frame
            continue
        proposed = propose_mapping(list(frame.columns), ALIASES)
        mapping = dict(proposed.mapping)
        # PoC fixture가 제안한 미지 헤더 2개를 감사인이 확정한 결과.
        mapping.update({source: target for source, target in {"Posting Dt": "전표일자", "Amt(CR)": "대변"}.items() if source in frame.columns})
        normalized = normalize_gl(apply_mapping(frame, mapping))
        classified[classify_document(normalized)] = normalized
    required = (DocumentType.CURRENT_GL, DocumentType.PRIOR_GL, DocumentType.TRIAL_BALANCE, DocumentType.AR_SUBLEDGER)
    missing = [kind.value for kind in required if kind not in classified]
    if missing:
        raise ValueError(f"자료 종류를 판별할 수 없습니다: {', '.join(missing)}")
    return SampleBundle(*(classified[kind] for kind in required))


def render_assistant_widget() -> None:
    html = """
<script>
(function () {
  const botImage = "__BOT_IMAGE__";
  let doc;
  try {
    doc = window.parent.document;
  } catch (error) {
    return;
  }

  const existing = doc.getElementById("auditpilot-floating-assistant");
  if (existing) existing.remove();

  const existingStyle = doc.getElementById("auditpilot-floating-assistant-style");
  if (existingStyle) existingStyle.remove();

  const style = doc.createElement("style");
  style.id = "auditpilot-floating-assistant-style";
  style.textContent = `
      #auditpilot-floating-assistant {
        position: fixed;
        right: 72px;
        bottom: 72px;
        z-index: 2147483000;
        display: flex;
        flex-direction: row;
        align-items: flex-end;
        gap: 10px;
        user-select: none;
        touch-action: none;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }
      #auditpilot-floating-assistant.ap-dragging .ap-character-wrap { cursor: grabbing; }
      #auditpilot-floating-assistant.ap-hidden {
        gap: 0;
      }
      #auditpilot-floating-assistant.ap-hidden .ap-bubble {
        display: none;
      }
      #auditpilot-floating-assistant.ap-hidden .ap-character-wrap {
        cursor: pointer;
      }
      #auditpilot-floating-assistant.ap-hidden .ap-reopen-hint {
        display: block;
      }
      #auditpilot-floating-assistant .ap-character-wrap {
        position: relative;
        order: 2;
        width: 96px;
        height: 132px;
        display: flex;
        align-items: flex-end;
        justify-content: center;
        cursor: grab;
      }
      #auditpilot-floating-assistant .ap-reopen-hint {
        display: none;
        position: absolute;
        right: 78px;
        bottom: 54px;
        z-index: 2;
        width: max-content;
        max-width: 180px;
        padding: 6px 9px;
        border: 1px solid #fee2e2;
        border-radius: 999px;
        background: rgba(255, 255, 255, .94);
        color: #b91c1c;
        box-shadow: 0 8px 18px rgba(17, 24, 39, .10);
        font-size: 11px;
        font-weight: 800;
        line-height: 1;
        pointer-events: none;
        white-space: nowrap;
      }
      #auditpilot-floating-assistant .ap-reopen-hint::after {
        content: "";
        position: absolute;
        right: -4px;
        top: 50%;
        width: 8px;
        height: 8px;
        border-right: 1px solid #fee2e2;
        border-top: 1px solid #fee2e2;
        background: rgba(255, 255, 255, .94);
        transform: translateY(-50%) rotate(45deg);
      }
      #auditpilot-floating-assistant .ap-character-wrap::after {
        content: "";
        position: absolute;
        left: 18px;
        right: 18px;
        bottom: 3px;
        height: 10px;
        border-radius: 999px;
        background: rgba(17, 24, 39, .18);
        filter: blur(5px);
        animation: apBotShadow 3s ease-in-out infinite;
      }
      #auditpilot-floating-assistant img {
        position: relative;
        z-index: 1;
        width: 92px;
        height: 126px;
        object-fit: contain;
        animation: apBotFloat 3s ease-in-out infinite;
        transform-origin: 50% 90%;
        pointer-events: none;
      }
      #auditpilot-floating-assistant:hover img {
        animation: apBotWave .75s ease-in-out 1, apBotFloat 3s ease-in-out infinite .75s;
      }
      #auditpilot-floating-assistant .ap-bubble {
        position: relative;
        order: 1;
        width: 280px;
        max-width: calc(100vw - 132px);
        margin-bottom: 4px;
        padding: 10px 12px;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        background: rgba(255, 255, 255, .96);
        color: #374151;
        box-shadow: 0 12px 28px rgba(17, 24, 39, .12);
        backdrop-filter: blur(8px);
      }
      #auditpilot-floating-assistant .ap-bubble::before {
        content: "";
        position: absolute;
        right: -7px;
        bottom: 24px;
        width: 12px;
        height: 12px;
        border-right: 1px solid #e5e7eb;
        border-top: 1px solid #e5e7eb;
        background: rgba(255, 255, 255, .96);
        transform: rotate(45deg);
      }
      #auditpilot-floating-assistant .ap-name {
        display: flex;
        align-items: center;
        gap: 6px;
        padding-right: 28px;
        margin-bottom: 3px;
        font-size: 13px;
        font-weight: 800;
        color: #111827;
      }
      #auditpilot-floating-assistant .ap-close {
        position: absolute;
        right: 8px;
        top: 8px;
        width: 22px;
        height: 22px;
        border: 0;
        border-radius: 50%;
        color: #6b7280;
        background: #f3f4f6;
        cursor: pointer;
        font-size: 15px;
        line-height: 20px;
      }
      #auditpilot-floating-assistant .ap-close:hover {
        color: #111827;
        background: #e5e7eb;
      }
      #auditpilot-floating-assistant .ap-dot {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: #ff4b4b;
        animation: apBotPulse 1.8s ease-in-out infinite;
      }
      #auditpilot-floating-assistant .ap-copy {
        display: none;
        margin: 0;
        font-size: 12px;
        line-height: 1.45;
        color: #6b7280;
      }
      #auditpilot-floating-assistant .ap-chat-log {
        display: flex;
        flex-direction: column;
        gap: 7px;
        max-height: 145px;
        overflow-y: auto;
        margin: 8px 0 9px;
        padding-right: 2px;
      }
      #auditpilot-floating-assistant .ap-msg {
        width: fit-content;
        max-width: 92%;
        box-sizing: border-box;
        padding: 7px 9px;
        border-radius: 10px;
        font-size: 12px;
        line-height: 1.45;
        white-space: pre-wrap;
        overflow-wrap: anywhere;
        word-break: break-word;
      }
      #auditpilot-floating-assistant .ap-msg.bot {
        align-self: flex-start;
        background: #f3f4f6;
        color: #374151;
      }
      #auditpilot-floating-assistant .ap-msg.user {
        align-self: flex-end;
        background: #ff4b4b;
        color: white;
      }
      #auditpilot-floating-assistant .ap-chat-form {
        display: flex;
        gap: 6px;
      }
      #auditpilot-floating-assistant .ap-chat-input {
        min-width: 0;
        flex: 1;
        border: 1px solid #d1d5db;
        border-radius: 9px;
        padding: 8px 9px;
        font-size: 12px;
        outline: none;
        color: #111827;
        background: white;
      }
      #auditpilot-floating-assistant .ap-chat-input:focus {
        border-color: #ff4b4b;
        box-shadow: 0 0 0 2px rgba(255, 75, 75, .14);
      }
      #auditpilot-floating-assistant .ap-send {
        border: 0;
        border-radius: 9px;
        padding: 0 10px;
        font-size: 12px;
        font-weight: 800;
        color: white;
        background: #ff4b4b;
        cursor: pointer;
      }
      #auditpilot-floating-assistant .ap-send:hover { background: #e33f3f; }
      @keyframes apBotFloat {
        0%, 100% { transform: translateY(0) rotate(-1deg); }
        50% { transform: translateY(-8px) rotate(1deg); }
      }
      @keyframes apBotShadow {
        0%, 100% { transform: scaleX(.88); opacity: .55; }
        50% { transform: scaleX(1.08); opacity: .28; }
      }
      @keyframes apBotPulse {
        0%, 100% { box-shadow: 0 0 0 0 rgba(255, 75, 75, .32); }
        50% { box-shadow: 0 0 0 7px rgba(255, 75, 75, 0); }
      }
      @keyframes apBotWave {
        0%, 100% { transform: translateY(-4px) rotate(0); }
        25% { transform: translateY(-7px) rotate(-4deg); }
        55% { transform: translateY(-7px) rotate(4deg); }
        80% { transform: translateY(-5px) rotate(-2deg); }
      }
      @media (max-width: 720px) {
        #auditpilot-floating-assistant { right: 12px; bottom: 14px; }
        #auditpilot-floating-assistant .ap-bubble { width: 238px; }
        #auditpilot-floating-assistant .ap-character-wrap { width: 78px; height: 104px; }
        #auditpilot-floating-assistant img { width: 72px; height: 98px; }
      }
  `;
  doc.head.appendChild(style);

  const node = doc.createElement("div");
  node.id = "auditpilot-floating-assistant";
  node.setAttribute("aria-label", "AuditPilot AI assistant. Drag to move.");
  node.innerHTML = `
    <div class="ap-bubble">
      <button class="ap-close" type="button" aria-label="삼일이 숨기기">×</button>
      <div class="ap-name"><span class="ap-dot"></span>삼일이 AI</div>
      <p class="ap-copy">안녕하세요 삼일이 AI 챗봇입니다! 무엇이든 물어보세요!</p>
      <div class="ap-chat-log" aria-live="polite">
        <div class="ap-msg bot">안녕하세요 삼일이 AI입니다! 질문을 감사업무 흐름에 맞춰 빠르게 안내할게요. 글이 가리면 저를 드래그해 옮길 수 있어요.</div>
      </div>
      <form class="ap-chat-form">
        <input class="ap-chat-input" type="text" placeholder="삼일이에게 질문하기" autocomplete="off">
        <button class="ap-send" type="submit">전송</button>
      </form>
    </div>
    <div class="ap-character-wrap" title="드래그해서 위치 이동">
      <span class="ap-reopen-hint">클릭하면 채팅창이 다시 열려요</span>
      <img src="data:image/png;base64,${botImage}" alt="AuditPilot AI assistant">
    </div>
  `;
  doc.body.appendChild(node);

  const parentWindow = window.parent;
  parentWindow.localStorage.removeItem("auditpilotAssistantPositionV2");

  let dragging = false;
  let offsetX = 0;
  let offsetY = 0;
  let dragStartX = 0;
  let dragStartY = 0;
  let wasHiddenOnPointerDown = false;
  const dragHandle = node.querySelector(".ap-character-wrap");
  const closeButton = node.querySelector(".ap-close");
  const chatLog = node.querySelector(".ap-chat-log");
  const chatForm = node.querySelector(".ap-chat-form");
  const chatInput = node.querySelector(".ap-chat-input");

  if (parentWindow.localStorage.getItem("auditpilotAssistantHidden") === "1") {
    node.classList.add("ap-hidden");
  }

  function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }

  function place(clientX, clientY) {
    const rect = node.getBoundingClientRect();
    const maxX = parentWindow.innerWidth - rect.width - 8;
    const maxY = parentWindow.innerHeight - rect.height - 8;
    const x = clamp(clientX - offsetX, 8, Math.max(8, maxX));
    const y = clamp(clientY - offsetY, 8, Math.max(8, maxY));
    node.style.left = x + "px";
    node.style.top = y + "px";
    node.style.right = "auto";
    node.style.bottom = "auto";
  }

  function saveNodePosition() {
    return;
  }

  function keepCharacterAt(characterBefore) {
    const characterAfter = dragHandle.getBoundingClientRect();
    const nodeAfter = node.getBoundingClientRect();
    node.style.left = (nodeAfter.left + characterBefore.left - characterAfter.left) + "px";
    node.style.top = (nodeAfter.top + characterBefore.top - characterAfter.top) + "px";
    node.style.right = "auto";
    node.style.bottom = "auto";
  }

  function updateChatWithoutMovingCharacter(update) {
    const characterBefore = dragHandle.getBoundingClientRect();
    const result = update();
    keepCharacterAt(characterBefore);
    saveNodePosition();
    return result;
  }

  function setBubbleHidden(hidden) {
    const characterBefore = dragHandle.getBoundingClientRect();
    if (hidden) {
      node.classList.add("ap-hidden");
      parentWindow.localStorage.setItem("auditpilotAssistantHidden", "1");
    } else {
      node.classList.remove("ap-hidden");
      parentWindow.localStorage.setItem("auditpilotAssistantHidden", "0");
    }
    keepCharacterAt(characterBefore);
    saveNodePosition();
  }

  function appendMessage(role, text) {
    return updateChatWithoutMovingCharacter(function () {
      const message = doc.createElement("div");
      message.className = "ap-msg " + role;
      message.textContent = text;
      chatLog.appendChild(message);
      chatLog.scrollTop = chatLog.scrollHeight;
      return message;
    });
  }

  function localAssistantAnswer(text) {
    const raw = text.trim();
    const q = text.toLowerCase();
    if (["ㅎㅇ", "하이", "안녕", "안녕하세요", "hi", "hello"].includes(q) || /^[ㅎㅋㅠㅜ]+$/.test(raw)) {
      return "안녕하세요! 삼일이 AI입니다. PBC, 클렌징, 분석, 조서 중 궁금한 걸 물어보면 감사업무 흐름에 맞춰 안내할게요.";
    }
    if (/^[a-z]{1,3}$/i.test(raw)) {
      return "영문으로 짧게 입력된 것 같아요. PBC, 클렌징, 분석, 조서처럼 궁금한 탭 이름을 한글로 물어보면 바로 안내할게요.";
    }
    if (q.includes("ai") || q.includes("gpt") || q.includes("api") || q.includes("연결") || q.includes("끊")) {
      return "끊긴 게 아니에요. 지금 삼일이 AI는 데모 속도를 위해 무료 즉시 응답 방식으로 작동해요. PBC, 클렌징, 분석, 조서 질문은 바로 답할 수 있습니다.";
    }
    if (q.includes("사용") || q.includes("어떻게") || q.includes("방법") || q.includes("뭐하는")) {
      return "③ 업로드·매핑에서 데모 샘플을 불러온 뒤 ④ 검증, ⑤ 분석, ⑥ 문서화 순서로 누르면 전체 흐름을 볼 수 있어요.";
    }
    if (q.includes("pbc") || q.includes("자료요청") || q.includes("요청")) {
      return "PBC 탭에서 계정을 고르면 요청자료, 감사주장, 수행절차가 연결됩니다. 요청 목적이 보이도록 문구를 정리하는 데 초점을 둡니다.";
    }
    if (q.includes("클렌징") || q.includes("검증") || q.includes("오류") || q.includes("중복") || q.includes("결측")) {
      return "클렌징·검증은 중복, 결측, 차대변 불일치, 기간 외 거래를 먼저 잡습니다. 예외는 삭제하지 않고 감사인이 판단하도록 남깁니다.";
    }
    if (q.includes("분석") || q.includes("ar") || q.includes("증감") || q.includes("이상치") || q.includes("추이")) {
      return "분석·테스트는 전기 대비 변동, 월별 추이, 거래처별 변동을 보고 확인 필요 후보를 뽑습니다. 후보는 결론이 아니라 추가 질문 대상입니다.";
    }
    if (q.includes("조서") || q.includes("문서") || q.includes("결론") || q.includes("리뷰")) {
      return "문서화 단계는 수행 절차와 숫자 근거를 조서 초안으로 정리합니다. 최종 결론과 승인은 감사인이 남기도록 설계했습니다.";
    }
    if (q.includes("챗봇") || q.includes("삼일")) {
      return "삼일이 AI는 데모 흐름을 빠르게 안내하는 감사업무 챗봇입니다. 감사 판단은 대신하지 않고 확인할 절차와 증빙을 짚어줍니다.";
    }
    if (q.includes("업로드") || q.includes("매핑") || q.includes("엑셀") || q.includes("원장") || q.includes("gl")) {
      return "업로드·매핑은 회사마다 다른 GL 헤더를 표준 스키마로 맞추는 단계입니다. 자동 제안 후 감사인이 매핑을 확정합니다.";
    }
    return "AuditPilot은 PBC, 업로드·매핑, 클렌징·검증, 분석·테스트, 문서화 흐름을 보여주는 감사업무 데모입니다. 궁금한 탭 이름으로 물어보면 바로 안내할게요.";
  }

  function compactAnswer(text) {
    if (text.length <= 220) return text;
    return text.slice(0, 217).trim() + "...";
  }

  async function sendQuestion(text) {
    if (!text) return;
    appendMessage("user", text);
    chatInput.value = "";
    chatInput.disabled = true;
    const pending = appendMessage("bot", "질문을 분석하고 있어요...");
    parentWindow.setTimeout(function () {
      updateChatWithoutMovingCharacter(function () {
        pending.textContent = compactAnswer(localAssistantAnswer(text));
        chatLog.scrollTop = chatLog.scrollHeight;
      });
      chatInput.disabled = false;
      chatInput.focus();
    }, 240);
  }

  chatForm.addEventListener("submit", async function (event) {
    event.preventDefault();
    await sendQuestion(chatInput.value.trim());
  });

  closeButton.addEventListener("click", function () {
    setBubbleHidden(true);
  });

  dragHandle.addEventListener("pointerdown", function (event) {
    dragging = true;
    wasHiddenOnPointerDown = node.classList.contains("ap-hidden");
    dragStartX = event.clientX;
    dragStartY = event.clientY;
    node.classList.add("ap-dragging");
    const rect = node.getBoundingClientRect();
    offsetX = event.clientX - rect.left;
    offsetY = event.clientY - rect.top;
    node.setPointerCapture(event.pointerId);
  });

  parentWindow.addEventListener("pointermove", function (event) {
    if (!dragging) return;
    place(event.clientX, event.clientY);
  });

  parentWindow.addEventListener("pointerup", function (event) {
    if (!dragging) return;
    const moved = Math.abs(event.clientX - dragStartX) + Math.abs(event.clientY - dragStartY);
    dragging = false;
    node.classList.remove("ap-dragging");
    if (wasHiddenOnPointerDown && moved < 6) {
      setBubbleHidden(false);
    }
    wasHiddenOnPointerDown = false;
    saveNodePosition();
  });
})();
</script>
"""
    components.html(
        html
        .replace("__BOT_IMAGE__", BOT_IMAGE),
        height=0,
    )


st.markdown(
    f"""
    <div class="app-logo-row" aria-label="AuditPilot">
      <img src="data:image/svg+xml;base64,{LOGO_IMAGE}" alt="PwC logo">
      <div class="app-title-text">AuditPilot</div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.caption("감사자료 수집부터 클렌징, 분석, 테스트, 문서화까지 반복 업무를 줄이고 감사인 판단에 집중하도록 돕는 Assistant")
render_assistant_widget()
materiality = 50_000_000

tab_bottleneck, tab_pbc, tab_upload, tab_validate, tab_analytics, tab_workpaper = st.tabs([
    "① 병목 진단", "② PBC 요청", "③ 업로드·매핑", "④ 클렌징·검증", "⑤ 분석·테스트", "⑥ 문서화·판단"
])

with tab_bottleneck:
    st.subheader("감사업무 병목과 Digital 활용 지점")
    st.caption("반복 업무를 줄이는 목적은 감사인의 판단을 대체하는 것이 아니라, 판단에 도달하기 전의 자료 정리와 확인 비용을 줄이는 것입니다.")
    c1, c2, c3 = st.columns(3)
    c1.metric("핵심 병목", "5개")
    c2.metric("중심 단계", "Execution")
    c3.metric("판단 게이트", "3단계")
    st.dataframe(AUDIT_BOTTLENECKS, width="stretch", hide_index=True)

with tab_pbc:
    st.subheader("목적이 보이는 자료 요청")
    st.caption("전기 PBC를 그대로 복사하는 대신, 요청자료가 어떤 감사목적과 절차에 연결되는지 먼저 보여줍니다.")
    account = st.selectbox("계정", list(PBC_CATALOG))
    selected_pbc = PBC_CATALOG[account]
    pbc = pd.DataFrame([{
        "요청 자료": selected_pbc["request"],
        "감사주장": selected_pbc["assertions"],
        "수행 절차": selected_pbc["procedures"],
        "제출 형식": selected_pbc["format"],
    }])
    st.dataframe(pbc, width="stretch", hide_index=True)
    st.info(selected_pbc["message"])
    st.caption("주요 감사 계정 템플릿 · 계정 선택에 따라 요청자료와 안내문이 함께 바뀝니다.")
    st.caption("감사인이 요청 범위와 문안을 검토한 뒤 발송합니다. 자동 발송 기능은 없습니다.")

with tab_upload:
    st.subheader("자료 업로드와 표준 스키마 매핑")
    st.caption("회사마다 다른 GL, 계정명세서, 월보, backdata 형식을 표준 컬럼으로 맞추는 단계입니다.")
    left, right = st.columns(2, vertical_alignment="top")
    with left:
        st.caption("샘플 데이터로 빠르게 흐름 확인")
        if st.button("데모 샘플 불러오기", type="primary", width="stretch"):
            load_bundle(build_sample_bundle())
            st.rerun()
    with right:
        uploads = st.file_uploader("xlsx 4개 업로드", type=["xlsx"], accept_multiple_files=True)
        if st.button("업로드 파일 처리", disabled=len(uploads) != 4, width="stretch"):
            try:
                load_bundle(uploaded_bundle(uploads))
                st.rerun()
            except Exception as exc:
                st.error(f"파일 처리 실패: {exc}")
    if st.session_state.bundle is not None:
        st.success("당기원장 · 전기원장 · 시산표 · 매출채권명세서 4종 준비 완료")
        mapping_rows = [{"원본 헤더": source, "표준 컬럼": target, "처리": "LLM 제안(캐시)" if source in ("Posting Dt", "Amt(CR)") else "사전/퍼지"}
                        for source, target in {"Posting Dt":"전표일자","Voucher No":"전표번호","Acct Cd":"계정코드","계정과목":"계정명","Customer":"거래처","Debit Amount":"차변","Amt(CR)":"대변","Description":"적요","Entry Type":"전표유형"}.items()]
        st.dataframe(mapping_rows, width="stretch", hide_index=True)
        st.markdown('<span class="cache">미지 헤더 2개 · confidence 포함 사전 생성 제안</span>', unsafe_allow_html=True)
        if st.button("게이트 1 · 매핑 확정", type="primary"):
            st.session_state.mapping_confirmed = True
            st.success("감사인이 매핑을 확정했습니다. 검증 단계가 활성화됩니다.")
        st.caption("판단 지점: 자동 매핑 결과를 그대로 확정하지 않고, 감사인이 열 의미와 자료 완전성을 확인합니다.")

with tab_validate:
    st.subheader("클렌징 결과 검증")
    st.caption("중복, 결측, 차대변 불일치, 기간 외 거래, 명세서 대사 차이를 먼저 잡아 재작업을 줄입니다.")
    if not can_validate(st.session_state):
        st.warning("게이트 1에서 열 매핑을 먼저 확정해 주세요.")
    if st.button("검증 실행", disabled=not can_validate(st.session_state), type="primary"):
        b = st.session_state.bundle
        st.session_state.validation_report = build_validation_report(b.current, b.subledger, b.trial_balance)
    report = st.session_state.validation_report
    if report:
        columns = st.columns(5)
        for column, item in zip(columns, report.items):
            column.metric(item.rule_id, "통과" if item.passed else "예외", f"{len(item.exception_rows)}행")
        st.dataframe([{"검증": i.message, "상태": "통과" if i.passed else "확인 필요", "예외행": str(i.exception_rows),
                       "기대값": i.expected, "실제값": i.actual} for i in report.items], width="stretch", hide_index=True)
        st.caption("LLM 미개입 · 예외는 자동 삭제하지 않습니다.")
        st.caption("판단 지점: 예외가 오류인지, 정상 거래인지, 추가 증빙이나 대체절차가 필요한지는 감사인이 판단합니다.")

with tab_analytics:
    st.subheader("분석적검토와 테스트 설계")
    st.caption("전기 대비 변동, 월별 추이, 거래처별 이상치를 먼저 보여주고 후속 질의 초안을 만듭니다.")
    st.dataframe(TEST_LIBRARY, width="stretch", hide_index=True)
    if st.session_state.validation_report is None:
        st.warning("검증을 먼저 실행해 주세요.")
    if st.button("분석 실행", disabled=st.session_state.validation_report is None, type="primary"):
        b = st.session_state.bundle
        result = analyze(b.current, b.prior, int(materiality))
        st.session_state.analytics_result = result
        st.session_state.registry = build_computed_values(result)
    result = st.session_state.analytics_result
    if result:
        c1, c2 = st.columns(2)
        with c1:
            st.caption("월별 매출 추이")
            st.bar_chart(result.monthly_trend)
        with c2:
            st.caption("거래처별 증감 Top 10")
            st.bar_chart(result.customer_change.nlargest(10, "증감액")[["증감액"]])
        st.dataframe([{"순위": c.rank, "대상": c.entity, "점수": c.score, "감사주장": ", ".join(c.assertions),
                       "당기 금액": f"{int(c.evidence['current_amount']):,}", "증감률": "신규" if c.evidence['change_rate'] is None else f"{float(c.evidence['change_rate'])*100:+.1f}%"}
                      for c in result.candidates], width="stretch", hide_index=True)
        if st.button("Top 1 후속 질의 생성"):
            payload = json.loads(FIXTURE.generate("query_daesung", "", "").content)
            st.session_state.query_text = payload["question"]
            st.session_state.query_review_passed = review_numbers(payload["question"], st.session_state.registry).passed
        if st.session_state.query_text:
            st.text_area("고객사 질의 문안", st.session_state.query_text, height=120)
            st.markdown('<span class="cache">사전 생성 응답(캐시) · 수치 전수 검증 완료</span>', unsafe_allow_html=True)
            st.caption("판단 지점: 질의의 필요성, 질문 범위, 회사 설명의 충분성은 감사인이 판단합니다.")
            if st.button("게이트 2 · 질의 문안 승인", disabled=not can_approve_query(st.session_state)):
                st.session_state.query_approved = True
            if st.session_state.query_approved:
                st.success("감사인 검토 완료 · 외부 발송은 수행하지 않습니다.")

with tab_workpaper:
    st.subheader("문서화 지원과 감사인 판단")
    st.caption("AI는 조서 초안과 문장 구조를 돕고, 최종 결론과 승인은 감사인이 남깁니다.")
    st.dataframe(
        [{"구분": str(idx + 1), "원칙": text} for idx, text in enumerate(JUDGMENT_BOUNDARIES)],
        width=760,
        hide_index=True,
        column_config={
            "구분": st.column_config.TextColumn("구분", width="small"),
            "원칙": st.column_config.TextColumn("원칙", width="large"),
        },
    )
    if st.session_state.analytics_result is None:
        st.warning("분석을 먼저 실행해 주세요.")
    if st.button("조서 초안 생성", disabled=st.session_state.analytics_result is None, type="primary"):
        payload = json.loads(FIXTURE.generate("workpaper_ar", "", "").content)
        wp = build_workpaper(st.session_state.analytics_result, payload["narrative"], st.session_state.registry)
        markdown = render_workpaper_markdown(wp, st.session_state.registry)
        review = review_numbers(markdown, st.session_state.registry)
        st.session_state.workpaper, st.session_state.workpaper_review_passed = wp, review.passed
    wp = st.session_state.workpaper
    if wp:
        markdown = render_workpaper_markdown(wp, st.session_state.registry)
        st.markdown('<div class="draft">DRAFT — 감사인 승인 전</div>', unsafe_allow_html=True)
        st.markdown(markdown)
        st.success("Review 검증기: 문서 내 수치가 원천 계산값과 모두 일치합니다." if st.session_state.workpaper_review_passed else "수치 불일치 · 승인 차단")
        if st.button("게이트 3 · 잠정결론 승인", disabled=not can_approve_workpaper(st.session_state)):
            st.session_state.workpaper_approved = True
        if st.session_state.workpaper_approved:
            report = st.session_state.validation_report
            st.download_button("조서 패키지 xlsx", export_xlsx(wp, st.session_state.analytics_result.candidates, report), "AuditPilot_조서패키지.xlsx")
            st.download_button("조서 Markdown", export_markdown(wp, st.session_state.registry), "AuditPilot_조서.md")
