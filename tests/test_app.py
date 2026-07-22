import pytest
from streamlit.testing.v1 import AppTest


def test_app_renders_six_tabs_without_exception():
    app = AppTest.from_file("app.py", default_timeout=20).run()
    assert not app.exception
    assert len(app.tabs) == 6
    assert app.title[0].value == "AuditPilot"


@pytest.mark.parametrize("rehearsal", range(5))
def test_app_human_in_the_loop_full_flow(rehearsal):
    app = AppTest.from_file("app.py", default_timeout=20).run()

    def click(label):
        nonlocal app
        button = next(item for item in app.button if item.label == label)
        assert not button.disabled
        app = button.click().run()
        assert not app.exception

    click("데모 샘플 불러오기")
    assert next(item for item in app.button if item.label == "검증 실행").disabled
    click("게이트 1 · 매핑 확정")
    click("검증 실행")
    click("분석 실행")
    click("Top 1 후속 질의 생성")
    click("게이트 2 · 질의 문안 승인")
    click("조서 초안 생성")
    assert app.session_state["workpaper_review_passed"]
    click("게이트 3 · 잠정결론 승인")
    assert app.session_state["workpaper_approved"]
    assert len(app.get("download_button")) == 2
