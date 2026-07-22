import base64
import json
from pathlib import Path

import pandas as pd
import streamlit as st

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
.bot-strip {display:flex; align-items:center; gap:1.1rem; margin:.8rem 0 1.25rem; padding:.9rem 1rem; border:1px solid #e5e7eb; border-radius:.6rem; background:#fff; overflow:hidden}
.bot-avatar {position:relative; flex:0 0 auto; width:96px; height:112px; display:flex; align-items:center; justify-content:center}
.bot-avatar::after {content:""; position:absolute; left:20px; right:20px; bottom:2px; height:10px; border-radius:999px; background:rgba(17,24,39,.12); filter:blur(4px); animation:botShadow 3s ease-in-out infinite}
.bot-avatar img {position:relative; z-index:1; width:86px; height:104px; object-fit:contain; animation:botFloat 3s ease-in-out infinite; transform-origin:50% 90%}
.bot-strip:hover .bot-avatar img {animation:botWave .75s ease-in-out 1, botFloat 3s ease-in-out infinite .75s}
.bot-message {position:relative; max-width:760px; padding:.72rem .9rem; border:1px solid #e5e7eb; border-radius:.75rem; background:#f9fafb}
.bot-message::before {content:""; position:absolute; left:-8px; top:34px; width:14px; height:14px; background:#f9fafb; border-left:1px solid #e5e7eb; border-bottom:1px solid #e5e7eb; transform:rotate(45deg)}
.bot-name {display:flex; align-items:center; gap:.42rem; font-weight:700; color:#111827; margin-bottom:.18rem}
.bot-dot {width:.48rem; height:.48rem; border-radius:50%; background:#ff4b4b; box-shadow:0 0 0 rgba(255,75,75,.34); animation:botPulse 1.8s ease-in-out infinite}
.bot-copy {color:#6b7280; margin:0; line-height:1.55}
@keyframes botFloat {
    0%, 100% {transform:translateY(0) rotate(-1deg)}
    50% {transform:translateY(-8px) rotate(1deg)}
}
@keyframes botShadow {
    0%, 100% {transform:scaleX(.9); opacity:.55}
    50% {transform:scaleX(1.08); opacity:.28}
}
@keyframes botPulse {
    0%, 100% {box-shadow:0 0 0 0 rgba(255,75,75,.28)}
    50% {box-shadow:0 0 0 7px rgba(255,75,75,0)}
}
@keyframes botWave {
    0%, 100% {transform:translateY(-4px) rotate(0)}
    25% {transform:translateY(-7px) rotate(-4deg)}
    55% {transform:translateY(-7px) rotate(4deg)}
    80% {transform:translateY(-5px) rotate(-2deg)}
}
@media (max-width: 640px) {
    .bot-strip {align-items:flex-start}
    .bot-avatar {width:78px; height:96px}
    .bot-avatar img {width:70px; height:88px}
    .bot-message::before {top:30px}
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


st.title("AuditPilot")
st.caption("감사자료 수집부터 클렌징, 분석, 테스트, 문서화까지 반복 업무를 줄이고 감사인 판단에 집중하도록 돕는 Assistant")
st.markdown(f"""
<div class="bot-strip">
    <div class="bot-avatar">
        <img src="data:image/png;base64,{BOT_IMAGE}" alt="AuditPilot AI assistant">
    </div>
    <div class="bot-message">
        <div class="bot-name"><span class="bot-dot"></span>AuditPilot AI Assistant</div>
        <p class="bot-copy">자료 정리, 후보 산출, 질의·조서 초안 작성을 돕습니다. 위험평가와 최종 판단은 감사인이 남깁니다.</p>
    </div>
</div>
""", unsafe_allow_html=True)
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
    st.dataframe([{"구분": idx + 1, "원칙": text} for idx, text in enumerate(JUDGMENT_BOUNDARIES)], width="stretch", hide_index=True)
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
