"""간단한 비밀번호 접근 제어 (PRD 6장).

st.secrets["app_password"]가 있을 때만 로그인을 요구한다. 없으면(로컬 개발) 건너뛴다.
"""

import hmac

import streamlit as st


def _app_password() -> str | None:
    try:
        return st.secrets.get("app_password")
    except Exception:  # secrets.toml이 없으면 예외가 난다
        return None


def is_authenticated() -> bool:
    return not _app_password() or bool(st.session_state.get("authenticated"))


def require_login() -> None:
    """로그인하지 않았으면 로그인 폼을 그리고 실행을 멈춘다."""
    if is_authenticated():
        return
    password = _app_password()

    st.title("실험 데이터 관리 및 분석")
    with st.form("login"):
        entered = st.text_input("비밀번호", type="password")
        if st.form_submit_button("로그인", type="primary"):
            if hmac.compare_digest(entered.encode(), str(password).encode()):
                st.session_state["authenticated"] = True
                st.rerun()
            st.error("비밀번호가 올바르지 않습니다.")
    st.stop()


def logout_button() -> None:
    if _app_password() and st.session_state.get("authenticated"):
        if st.sidebar.button("로그아웃"):
            st.session_state.pop("authenticated", None)
            st.rerun()
