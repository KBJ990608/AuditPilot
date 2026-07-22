DOWNSTREAM = {
    "mapping": ("validation_report", "analytics_result", "registry", "query_text", "query_review_passed", "query_approved", "workpaper", "workpaper_review_passed", "workpaper_approved"),
    "validation": ("analytics_result", "registry", "query_text", "query_review_passed", "query_approved", "workpaper", "workpaper_review_passed", "workpaper_approved"),
}


def can_validate(state) -> bool:
    return bool(state.get("mapping_confirmed"))


def can_approve_query(state) -> bool:
    return bool(state.get("query_review_passed"))


def can_approve_workpaper(state) -> bool:
    return bool(state.get("workpaper_review_passed"))


def invalidate_downstream(state, stage: str) -> None:
    for key in DOWNSTREAM[stage]:
        state[key] = False if key.endswith(("_passed", "_approved")) else None
