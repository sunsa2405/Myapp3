from datetime import date

import pandas as pd
import streamlit as st

import cache
import db
import io_utils
import ui
from db import PROPERTIES
from validators import normalize_experiment, validate_experiment

PROPERTY_EXAMPLES = {
    "hardness": "예: 38.5",
    "yield_strength": "예: 1050",
    "tensile_strength": "예: 1180",
    "impact_strength": "예: 62",
}

st.title("데이터 관리")
st.caption("실험 결과를 조회하고 추가·수정·삭제합니다. CSV/Excel로 한꺼번에 등록하거나 내려받을 수 있습니다.")
ui.show_flash()

version = st.session_state.setdefault("data_version", 0)


def after_change(message: str) -> None:
    """데이터가 바뀐 뒤: 캐시를 비우고 입력 위젯·선택 상태를 초기화한 뒤 다시 그린다."""
    cache.invalidate()
    st.session_state["data_version"] += 1
    st.session_state.pop("pending_delete", None)
    ui.flash(message)
    st.rerun()


def experiment_fields(prefix: str, grades: list[str], initial: dict | None = None) -> dict:
    """추가·수정 폼의 입력란. 값이 없는 숫자 입력은 None을 반환한다."""
    initial = initial or {}
    data = {}

    c1, c2, c3 = st.columns(3)
    grade = initial.get("grade")
    data["grade"] = c1.selectbox(
        "Grade *",
        grades,
        index=grades.index(grade) if grade in grades else None,
        accept_new_options=True,
        placeholder="선택하거나 새로 입력",
        key=f"{prefix}_grade",
    )
    for column, col in (("q_condition", c2), ("t_condition", c3)):
        data[column] = col.number_input(
            f"{ui.condition_label(column)} *",
            value=initial.get(column),
            min_value=0.0,
            step=10.0,
            format="%g",
            placeholder="예: 850" if column == "q_condition" else "예: 550",
            key=f"{prefix}_{column}",
        )

    for (column, meta), col in zip(PROPERTIES.items(), st.columns(4)):
        data[column] = col.number_input(
            f"{meta['label']} ({meta['unit']})",
            value=initial.get(column),
            min_value=0.0,
            step=1.0,
            format=ui.NUMBER_FORMATS[column],
            placeholder=PROPERTY_EXAMPLES[column],
            help="측정하지 않았으면 비워두세요.",
            key=f"{prefix}_{column}",
        )
    return data


def show_errors(errors: list[str]) -> None:
    st.error("입력값을 확인하세요.\n\n" + "\n".join(f"- {e}" for e in errors), icon=":material/error:")


# ---------------------------------------------------------------------------
# 조회 · 필터 (F1-1, F1-2)
# ---------------------------------------------------------------------------

df = cache.load_experiments()
grades = sorted(df["grade"].unique())

filter_box = st.container(border=True)
c1, c2, c3 = filter_box.columns(3)
sel_grades = c1.multiselect("Grade", grades, placeholder="전체")
scope = df[df["grade"].isin(sel_grades)] if sel_grades else df
sel_q = c2.multiselect(
    ui.condition_label("q_condition"),
    sorted(scope["q_condition"].unique()),
    format_func=ui.fmt,
    placeholder="전체",
)
sel_t = c3.multiselect(
    ui.condition_label("t_condition"),
    sorted(scope["t_condition"].unique()),
    format_func=ui.fmt,
    placeholder="전체",
)

filtered = scope
if sel_q:
    filtered = filtered[filtered["q_condition"].isin(sel_q)]
if sel_t:
    filtered = filtered[filtered["t_condition"].isin(sel_t)]
filtered = filtered.reset_index(drop=True)

st.caption(
    f"**{len(filtered):,}건** 표시 / 전체 {len(df):,}건 · "
    "행 왼쪽 체크박스로 선택하면 아래 '수정'·'삭제' 탭에서 처리할 수 있습니다."
)

# 표의 행 선택은 위치 기준이다. 표시되는 행 구성이 바뀌면 key를 바꿔 선택을 초기화해서
# 다른 행이 선택된 채로 수정·삭제되는 일을 막는다.
table_key = f"table_{version}_{hash(tuple(filtered['id']))}"
event = st.dataframe(
    ui.table_frame(filtered),
    column_config=ui.column_config(),
    column_order=ui.TABLE_COLUMNS,
    hide_index=True,
    on_select="rerun",
    selection_mode="multi-row",
    key=table_key,
)
selected = filtered.iloc[event.selection.rows]

tab_add, tab_edit, tab_delete, tab_upload, tab_download = st.tabs(
    [
        ":material/add: 추가",
        ":material/edit: 수정",
        ":material/delete: 삭제",
        ":material/upload: 업로드",
        ":material/download: 다운로드",
    ],
    key="manage_tab",  # key가 없으면 파일 업로드 등으로 다시 그릴 때 첫 탭으로 돌아간다
    on_change="rerun",
)

# ---------------------------------------------------------------------------
# 추가 (F1-3)
# ---------------------------------------------------------------------------

with tab_add:
    with st.form(f"add_form_{version}"):
        data = experiment_fields(f"add_{version}", grades)
        submitted = st.form_submit_button("추가", type="primary", icon=":material/add:")
    if submitted:
        errors = validate_experiment(data)
        if errors:
            show_errors(errors)
        else:
            db.add_experiment(normalize_experiment(data))
            after_change("실험 결과를 추가했습니다.")

# ---------------------------------------------------------------------------
# 수정 (F1-4)
# ---------------------------------------------------------------------------

with tab_edit:
    if len(selected) != 1:
        st.info("위 표에서 수정할 행을 **하나만** 선택하세요.", icon=":material/touch_app:")
    else:
        row = {k: (None if pd.isna(v) else v) for k, v in selected.iloc[0].to_dict().items()}
        experiment_id = int(row["id"])
        prefix = f"edit_{experiment_id}_{version}"
        with st.form(f"{prefix}_form"):
            data = experiment_fields(prefix, grades, row)
            submitted = st.form_submit_button("저장", type="primary", icon=":material/save:")
        if submitted:
            errors = validate_experiment(data)
            if errors:
                show_errors(errors)
            elif db.update_experiment(experiment_id, normalize_experiment(data)):
                after_change("실험 결과를 수정했습니다.")
            else:
                cache.invalidate()
                st.error("이미 삭제된 데이터입니다. 화면을 새로고침하세요.")

# ---------------------------------------------------------------------------
# 삭제 (F1-5)
# ---------------------------------------------------------------------------

with tab_delete:
    if selected.empty:
        st.info("위 표에서 삭제할 행을 선택하세요. 여러 행을 선택할 수 있습니다.", icon=":material/touch_app:")
    else:
        ids = [int(i) for i in selected["id"]]
        st.dataframe(
            ui.table_frame(selected),
            column_config=ui.column_config(),
            column_order=ui.TABLE_COLUMNS,
            hide_index=True,
        )
        if st.session_state.get("pending_delete") != ids:
            if st.button(f"선택한 {len(ids)}건 삭제", icon=":material/delete:", key="danger_delete"):
                st.session_state["pending_delete"] = ids
                st.rerun()
        else:
            st.warning(
                f"선택한 {len(ids)}건을 정말 삭제하시겠습니까? 삭제하면 되돌릴 수 없습니다.",
                icon=":material/warning:",
            )
            b1, b2, _ = st.columns([1, 1, 4])
            if b1.button("삭제 확인", icon=":material/delete_forever:", key="danger_confirm"):
                deleted = db.delete_experiments(ids)
                after_change(f"{deleted}건을 삭제했습니다.")
            if b2.button("취소"):
                st.session_state.pop("pending_delete", None)
                st.rerun()

# ---------------------------------------------------------------------------
# 업로드 (F1-8)
# ---------------------------------------------------------------------------

with tab_upload:
    st.markdown(
        "CSV 또는 Excel(.xlsx) 파일로 여러 건을 한 번에 등록합니다. "
        "**Grade, Q조건, T조건** 열은 필수이고, 물성 열은 비워둘 수 있습니다. "
        "열 이름은 `인장강도`, `인장강도 (MPa)`, `tensile_strength` 형태를 모두 인식합니다."
    )
    st.download_button(
        "빈 양식 내려받기 (CSV)",
        io_utils.to_csv_bytes(df.iloc[0:0]),
        icon=":material/description:",
        file_name="실험결과_양식.csv",
        mime="text/csv",
        on_click="ignore",
    )
    uploaded = st.file_uploader("파일 선택", type=["csv", "xlsx"], key=f"upload_{version}")
    if uploaded is not None:
        try:
            raw = io_utils.read_upload(uploaded.name, uploaded.getvalue())
        except Exception as e:  # 빈 파일, 손상된 파일, 인코딩 문제 등
            st.error(
                "파일을 읽을 수 없습니다. 비어 있거나 손상된 파일이 아닌지, "
                "CSV(쉼표 구분) 또는 Excel(.xlsx) 형식이 맞는지 확인하세요.",
                icon=":material/error:",
            )
            st.caption(f"상세: {e}")
        else:
            result = io_utils.prepare_upload(raw)
            if result.missing_required:
                missing = ", ".join(db.COLUMN_LABELS[c] for c in result.missing_required)
                st.error(f"필수 열을 찾을 수 없습니다: {missing}")
            else:
                if result.ignored:
                    st.caption(f"인식하지 못해 무시하는 열: {', '.join(result.ignored)}")
                m1, m2, _ = st.columns([1, 1, 2])
                m1.metric("등록 가능", f"{len(result.records):,}건")
                m2.metric("오류", f"{len(result.errors):,}건")
                if result.records:
                    st.markdown("**등록할 데이터 미리보기**")
                    st.dataframe(
                        ui.table_frame(pd.DataFrame(result.records)),
                        column_config=ui.column_config(),
                        hide_index=True,
                    )
                if not result.errors.empty:
                    st.markdown("**오류 행 (등록하지 않음)**")
                    st.dataframe(result.errors, hide_index=True)
                if not result.records and result.errors.empty:
                    st.info("파일에 등록할 데이터 행이 없습니다.", icon=":material/info:")

                # 같은 업로드를 두 번 등록하지 않는다. 등록 버튼을 빠르게 두 번 누르면 업로더가
                # 초기화되기 전에 두 번째 클릭이 처리되어 같은 행이 중복 등록됐다.
                registered = st.session_state.setdefault("registered_uploads", set())
                if uploaded.file_id in registered:
                    st.info("이 파일은 이미 등록했습니다.", icon=":material/check_circle:")
                elif result.records and st.button(
                    f"유효한 {len(result.records):,}건 등록", type="primary", icon=":material/upload:"
                ):
                    registered.add(uploaded.file_id)
                    count = db.add_experiments(result.records)
                    after_change(f"{count:,}건을 등록했습니다.")

# ---------------------------------------------------------------------------
# 다운로드 (F1-9)
# ---------------------------------------------------------------------------

with tab_download:
    st.markdown(f"현재 표에 보이는 **{len(filtered):,}건**을 내려받습니다. 내려받은 파일은 그대로 다시 업로드할 수 있습니다.")
    stamp = date.today().strftime("%Y%m%d")
    d1, d2, _ = st.columns([1, 1, 3])
    # 파일은 버튼을 눌렀을 때만 만든다. 매 실행마다 만들면 1만 건에서 Excel 생성만 0.7초가 걸린다.
    d1.download_button(
        "CSV 다운로드",
        lambda: io_utils.to_csv_bytes(filtered),
        icon=":material/download:",
        file_name=f"실험결과_{stamp}.csv",
        mime="text/csv",
        disabled=filtered.empty,
        on_click="ignore",
    )
    d2.download_button(
        "Excel 다운로드",
        lambda: io_utils.to_excel_bytes(filtered),
        icon=":material/download:",
        file_name=f"실험결과_{stamp}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        disabled=filtered.empty,
        on_click="ignore",
    )
