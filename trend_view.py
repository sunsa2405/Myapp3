"""T조건 경향 / Q조건 경향 페이지 공통 화면 (PRD F2, F3)."""

from __future__ import annotations

import streamlit as st

import cache
import ui
from charts import color_map, has_enough_points, trend_chart
from db import CONDITION_COLUMNS


def render_trend_page(x_col: str, fixed_col: str) -> None:
    """Grade와 fixed_col을 고정하고 x_col에 따른 물성 경향을 그린다."""
    x_label = CONDITION_COLUMNS[x_col]["label"]
    fixed_label = CONDITION_COLUMNS[fixed_col]["label"]

    df = cache.load_experiments()
    if df.empty:
        st.info(
            "등록된 실험 결과가 없습니다. '데이터 관리'에서 먼저 실험 결과를 추가하세요.",
            icon=":material/info:",
        )
        return

    with st.container(border=True):
        left, right = st.columns([1, 2])
        grade = left.selectbox("Grade", sorted(df["grade"].unique()), key=f"trend_{x_col}_grade")
        grade_df = df[df["grade"] == grade]

        options = sorted(grade_df[fixed_col].unique())
        # 키에 Grade를 넣어서, Grade가 바뀌면 이전 선택값 없이 새 목록으로 초기화한다.
        selected = right.multiselect(
            ui.condition_label(fixed_col),
            options,
            default=options[:1],
            format_func=ui.fmt,
            key=f"trend_{x_col}_{fixed_col}_{grade}",
            help=f"여러 개를 고르면 {fixed_label}별로 선을 나눠 한 그래프에서 비교합니다.",
        )

    if not selected:
        st.info(f"{fixed_label}을 하나 이상 선택하세요.", icon=":material/touch_app:")
        return

    sub = grade_df[grade_df[fixed_col].isin(selected)]
    if not has_enough_points(sub, x_col):
        available = ", ".join(ui.fmt(v) for v in sorted(sub[x_col].unique()))
        counts = grade_df.groupby(fixed_col)[x_col].nunique()
        suggest = ", ".join(f"{ui.fmt(v)}℃" for v in counts[counts >= 2].index)
        hint = (
            f"{x_label}이 2개 이상 있는 {fixed_label}: {suggest}"
            if suggest
            else f"이 Grade에는 {x_label}이 2개 이상인 {fixed_label}이 없습니다. 데이터를 더 추가하세요."
        )
        st.info(
            f"경향을 표시하기에 데이터가 부족합니다. 선택한 조건의 {x_label}은 {available}℃ 한 가지뿐입니다.  \n{hint}",
            icon=":material/info:",
        )
    else:
        colors = color_map(options, ui.theme_type())
        st.plotly_chart(trend_chart(sub, x_col, fixed_col, selected, colors))
        st.caption(
            "선은 같은 조건의 평균값, 연한 점은 반복 시험의 개별 측정값입니다. "
            "점에 마우스를 올리면 값과 측정 건수가 보입니다."
        )

    with st.expander(f"데이터 보기 ({len(sub):,}건)", icon=":material/table_view:"):
        st.dataframe(
            ui.table_frame(sub.sort_values([fixed_col, x_col, "id"])),
            column_config=ui.column_config(),
            column_order=ui.TABLE_COLUMNS,
            hide_index=True,
        )
