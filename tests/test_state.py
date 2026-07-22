from auditpilot.state import can_approve_query, can_approve_workpaper, can_validate, invalidate_downstream


def test_gate_state_machine_and_invalidation():
    state = {"mapping_confirmed": False, "query_review_passed": False, "workpaper_review_passed": False,
             "analytics_result": object(), "workpaper": object(), "workpaper_approved": True}
    assert not can_validate(state)
    assert not can_approve_query(state)
    assert not can_approve_workpaper(state)
    state["mapping_confirmed"] = True
    state["query_review_passed"] = True
    state["workpaper_review_passed"] = True
    assert can_validate(state) and can_approve_query(state) and can_approve_workpaper(state)
    invalidate_downstream(state, "mapping")
    assert state["analytics_result"] is None
    assert state["workpaper"] is None
    assert state["workpaper_approved"] is False
