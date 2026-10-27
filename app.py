"""실험 데이터 관리 및 분석 앱 진입점: 공통 설정, 로그인, 페이지 라우팅."""

from pathlib import Path

import streamlit as st

import auth
import db
import ui

ASSETS = Path(__file__).parent / "assets"

st.set_page_config(
    page_title="실험 데이터 관리 및 분석",
    page_icon=str(ASSETS / "icon.svg"),
    layout="wide",
)

db.init_db()
st.logo(str(ASSETS / "logo.svg"), size="large", icon_image=str(ASSETS / "icon.svg"))
ui.inject_css()

pages = [
    st.Page("views/0_홈.py", title="홈", icon=":material/home:", default=True),
    st.Page("views/1_데이터_관리.py", title="데이터 관리", icon=":material/table_view:"),
    st.Page("views/2_T조건_경향.py", title="T조건 경향", icon=":material/show_chart:"),
    st.Page("views/3_Q조건_경향.py", title="Q조건 경향", icon=":material/stacked_line_chart:"),
]
# 로그인 전에도 navigation을 먼저 만들어야 요청한 페이지 주소가 유지된다.
# 로그인 전에는 메뉴를 숨기고, require_login()이 페이지 실행 전에 멈춘다.
navigation = st.navigation(pages, position="sidebar" if auth.is_authenticated() else "hidden")
auth.require_login()
ui.sidebar_summary(db.get_summary())
auth.logout_button()
navigation.run()
