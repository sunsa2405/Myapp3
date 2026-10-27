"""화면에서 쓰는 캐시된 조회 함수.

데이터를 추가·수정·삭제한 뒤에는 반드시 invalidate()를 호출한다.
"""

import pandas as pd
import streamlit as st

import db


@st.cache_data(ttl=60, show_spinner=False)
def load_experiments() -> pd.DataFrame:
    return db.list_experiments()


def invalidate() -> None:
    load_experiments.clear()
