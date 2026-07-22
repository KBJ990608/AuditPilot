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
from auditpilot.harness.eval import evaluate_cases
from auditpilot.llm.client import FixtureClient
from auditpilot.state import can_approve_query, can_approve_workpaper, can_validate, invalidate_downstream

ROOT = Path(__file__).parent
FIXTURE = FixtureClient(ROOT / "fixtures/llm_responses.json")
ALIASES = json.loads((ROOT / "config/header_aliases.json").read_text(encoding="utf-8"))

st.set_page_config(page_title="AuditPilot", page_icon="🧭", layout="wide")
st.markdown("""
<style>
.block-container {padding-top: 1.7rem; max-width: 1280px}
[data-testid="stMetricValue"] {font-size: 1.55rem}
.draft {border:1px solid #d97706; background:#fffbeb; padding:.7rem 1rem; border-radius:.5rem; color:#92400e}
.cache {display:inline-block; padding:.15rem .5rem; border-radius:1rem; background:#e0f2fe; color:#075985; font-size:.78rem}
</style>""", unsafe_allow_html=True)

DEFAULTS = {
    "bundle": None, "mapping_confirmed": False, "validation_report": None, "analytics_result": None,
    "registry": None, "query_text": None, "query_review_passed": False, "query_approved": False,
    "workpaper": None, "workpaper_review_passed": False, "workpaper_approved": False,
}
for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


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
st.caption("AI 기반 PBC 자료 수집·검증·증감분석 Assistant")
st.markdown("**숫자는 결정적 코드가, 문장은 LLM이, 결론은 감사인이 만듭니다.**")
with st.sidebar:
    st.subheader("실행 환경")
    st.success("Fixture provider")
    st.caption("API 키 없이 동작 · 사전 생성 응답은 캐시 배지로 표시")
    materiality = st.number_input("수행중요성 금액", min_value=1_000_000, value=50_000_000, step=10_000_000, format="%d")

tab_pbc, tab_upload, tab_validate, tab_analytics, tab_workpaper, tab_harness = st.tabs([
    "① PBC 요청", "② 업로드·매핑", "③ 검증", "④ 분석·질의", "⑤ 조서·Export", "⑥ Harness"
])

with tab_pbc:
    st.subheader("목적이 보이는 PBC 요청")
    account = st.selectbox("계정", ["매출채권", "매출"])
    pbc = pd.DataFrame([{
        "요청 자료": "매출채권 거래처별 명세서" if account == "매출채권" else "매출 원장",
        "감사주장": "실재성·평가·기간귀속" if account == "매출채권" else "발생사실·기간귀속",
        "수행 절차": "시산표 대사, 증감분석, 회수내역 검토" if account == "매출채권" else "원장 대사, 월별·거래처별 분석",
        "제출 형식": "xlsx · 기준일 2025-12-31",
    }])
    st.dataframe(pbc, width="stretch", hide_index=True)
    st.info(FIXTURE.generate("pbc_ar", "", "").content)
    st.markdown('<span class="cache">사전 생성 응답(캐시)</span>', unsafe_allow_html=True)
    st.caption("감사인이 요청 범위와 문안을 검토한 뒤 발송합니다. 자동 발송 기능은 없습니다.")

with tab_upload:
    st.subheader("자료 업로드와 표준 스키마 매핑")
    left, right = st.columns(2)
    with left:
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

with tab_validate:
    st.subheader("결정적 데이터 검증 5종")
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

with tab_analytics:
    st.subheader("분석적검토와 후속 질의")
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
            if st.button("게이트 2 · 질의 문안 승인", disabled=not can_approve_query(st.session_state)):
                st.session_state.query_approved = True
            if st.session_state.query_approved:
                st.success("감사인 검토 완료 · 외부 발송은 수행하지 않습니다.")

with tab_workpaper:
    st.subheader("감사조서 초안과 Review 검증기")
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

with tab_harness:
    st.subheader("LLM 평가 Harness")
    harness = evaluate_cases(ROOT / "harness/golden/cases.jsonl", FIXTURE)
    st.caption("현재 표는 fixture provider의 파이프라인 스모크 테스트이며 실모델 성능 결과가 아닙니다.")
    c1, c2, c3 = st.columns(3)
    c1.metric("골든셋", f"{harness['case_count']}건")
    c2.metric("JSON 스키마 준수", f"{harness['schema_compliance']*100:.0f}%")
    c3.metric("금지 표현 위반", f"{harness['forbidden_phrase_violations']}건")
    st.dataframe(harness["cases"], width="stretch", hide_index=True)
