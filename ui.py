"""여러 페이지에서 함께 쓰는 화면 요소."""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from charts import format_value
from db import COLUMN_LABELS, CONDITION_COLUMNS, DATA_COLUMNS

TABLE_COLUMNS = [*DATA_COLUMNS, "updated_at"]

NUMBER_FORMATS = {
    "q_condition": "%g",
    "t_condition": "%g",
    "hardness": "%.1f",
    "yield_strength": "%.0f",
    "tensile_strength": "%.0f",
    "impact_strength": "%.1f",
}
# 표 표시 형식. 강도는 천 단위 쉼표("localized"), 나머지는 입력 폼과 같은 자릿수.
TABLE_FORMATS = {**NUMBER_FORMATS, "yield_strength": "localized", "tensile_strength": "localized"}
EMPTY = "–"  # 측정하지 않은 값 표시 (사이드바 등 텍스트용)

DANGER_CSS = """
<style>
/* 삭제 버튼은 경고 색으로 구분 (key가 danger_로 시작하는 버튼) */
[class*="st-key-danger_"] button {
    background-color: #d03b3b; border-color: #d03b3b; color: #ffffff;
}
[class*="st-key-danger_"] button:hover {
    background-color: #b52f2f; border-color: #b52f2f; color: #ffffff;
}
</style>
"""


def fmt(value: float) -> str:
    return format_value(value)


def format_datetime(value: str | None) -> str:
    """'2026-10-27T14:05:37' → '2026-10-27 14:05'"""
    if not value:
        return EMPTY
    try:
        return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return str(value)


def column_config() -> dict:
    """st.dataframe용 열 설정: 한국어+단위 열 이름, 숫자·일시 표시 형식. table_frame()과 함께 쓴다.

    pandas Styler는 쓰지 않는다. 셀마다 표시 문자열을 만들어 보내서 1만 건에서 수 초가 걸린다.
    """
    config = {
        "id": None,  # 숨김
        "grade": st.column_config.TextColumn(COLUMN_LABELS["grade"]),
    }
    for col in ("created_at", "updated_at"):
        config[col] = st.column_config.DatetimeColumn(COLUMN_LABELS[col], format="YYYY-MM-DD HH:mm")
    for col, number_format in TABLE_FORMATS.items():
        config[col] = st.column_config.NumberColumn(COLUMN_LABELS[col], format=number_format)
    return config


def table_frame(df: pd.DataFrame) -> pd.DataFrame:
    """표 표시용 사본: 일시 문자열을 datetime으로 바꿔 DatetimeColumn 형식이 적용되게 한다."""
    out = df.copy()
    for col in ("created_at", "updated_at"):
        if col in out.columns:
            out[col] = pd.to_datetime(out[col], errors="coerce")
    return out


def condition_label(col: str) -> str:
    meta = CONDITION_COLUMNS[col]
    return f"{meta['label']} ({meta['unit']})"


def theme_type() -> str:
    """현재 화면 테마('light' 또는 'dark')."""
    try:
        return st.context.theme.type or "light"
    except Exception:
        return "light"


def inject_css() -> None:
    st.html(DANGER_CSS)


def sidebar_summary(summary: dict) -> None:
    """사이드바 하단: 데이터 총 건수와 마지막 등록·수정 시각."""
    with st.sidebar:
        st.caption(
            f"데이터 **{summary['total']:,}건** · Grade {summary['grades']}개  \n"
            f"마지막 등록·수정: {format_datetime(summary['last_updated'])}"
        )


def flash(message: str) -> None:
    """다음 실행(st.rerun 후)에 보여줄 성공 메시지를 저장한다."""
    st.session_state["_flash"] = message


def show_flash() -> None:
    # 메시지가 없어도 자리(container)를 항상 만든다. 메시지가 있을 때만 요소가 끼어들면
    # 아래 요소들의 위치가 한 칸씩 밀리고, key가 있는 st.tabs가 옛 위치에 중복으로 남는다.
    slot = st.container()
    message = st.session_state.pop("_flash", None)
    if message:
        with slot:
            st.success(message, icon=":material/check_circle:")
            st.toast(message, icon=":material/check_circle:")
