import streamlit as st

from trend_view import render_trend_page

st.title("T조건 경향")
st.caption("Grade와 Q조건을 고정하고, T조건에 따라 물성이 어떻게 달라지는지 확인합니다.")

render_trend_page(x_col="t_condition", fixed_col="q_condition")
