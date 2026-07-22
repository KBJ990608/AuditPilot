from auditpilot.core.ingest import DocumentType, classify_document
from auditpilot.data.make_sample import build_sample_bundle


def test_classify_four_documents():
    bundle = build_sample_bundle()
    assert classify_document(bundle.current, 2025) == DocumentType.CURRENT_GL
    assert classify_document(bundle.prior, 2025) == DocumentType.PRIOR_GL
    assert classify_document(bundle.trial_balance, 2025) == DocumentType.TRIAL_BALANCE
    assert classify_document(bundle.subledger, 2025) == DocumentType.AR_SUBLEDGER
