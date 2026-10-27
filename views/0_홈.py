import streamlit as st

import db

st.title("실험 데이터 관리 및 분석")
st.caption(
    "Grade별 열처리 조건(Q조건·T조건)에 따른 경도, 항복강도, 인장강도, 충격강도 "
    "실험 결과를 관리하고, 조건 변화에 따른 물성 경향을 그래프로 확인합니다."
)

summary = db.get_summary(recent_days=7)
c1, c2, c3, c4 = st.columns(4)
c1.metric("총 실험 건수", f"{summary['total']:,}건", border=True)
c2.metric("Grade 수", f"{summary['grades']}개", border=True)
c3.metric(
    "조건 조합 수",
    f"{summary['combos']}개",
    help="Grade × Q조건 × T조건 조합의 수. 같은 조합의 반복 시험은 하나로 셉니다.",
    border=True,
)
c4.metric("최근 7일 추가", f"{summary['recent']:,}건", border=True)

if summary["total"] == 0:
    st.info(
        "아직 등록된 실험 결과가 없습니다. '데이터 관리'에서 추가하거나 CSV/Excel 파일을 업로드하세요.",
        icon=":material/info:",
    )

st.subheader("바로가기")
MENU = [
    (
        "views/1_데이터_관리.py",
        "데이터 관리",
        ":material/table_view:",
        "실험 결과를 추가·수정·삭제하고, CSV/Excel로 한꺼번에 등록하거나 내려받습니다.",
    ),
    (
        "views/2_T조건_경향.py",
        "T조건 경향",
        ":material/show_chart:",
        "Grade와 Q조건을 고정하고, T조건에 따라 물성이 어떻게 달라지는지 봅니다.",
    ),
    (
        "views/3_Q조건_경향.py",
        "Q조건 경향",
        ":material/stacked_line_chart:",
        "Grade와 T조건을 고정하고, Q조건에 따라 물성이 어떻게 달라지는지 봅니다.",
    ),
]
for col, (page, label, icon, description) in zip(st.columns(3), MENU):
    with col.container(border=True, height="stretch"):
        st.page_link(page, label=f"**{label}**", icon=icon)
        st.caption(description)
