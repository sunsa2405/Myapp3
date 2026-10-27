from io import BytesIO

import pandas as pd

import io_utils


def test_map_columns_accepts_labels_units_and_internal_names():
    mapping, ignored = io_utils.map_columns(
        ["Grade", "Q조건 (℃)", "T조건", "경도 (HRC)", "yield_strength", "인장강도", "비고"]
    )
    assert mapping == {
        "Grade": "grade",
        "Q조건 (℃)": "q_condition",
        "T조건": "t_condition",
        "경도 (HRC)": "hardness",
        "yield_strength": "yield_strength",
        "인장강도": "tensile_strength",
    }
    assert ignored == ["비고"]


def test_prepare_upload_splits_valid_and_error_rows():
    csv = (
        "Grade,Q조건,T조건,경도,충격강도\n"
        "SCM440,850,550,38.5,62\n"
        "S45C,850,600,,\n"            # 물성 비어도 유효
        ",850,600,30,\n"               # Grade 누락
        "S45C,abc,600,30,\n"           # Q조건 숫자 아님
        ",,,,\n"                       # 빈 행은 건너뜀
        "한글강종,870,500,-1,\n"        # 음수
    )
    df = io_utils.read_upload("x.csv", csv.encode("utf-8"))
    result = io_utils.prepare_upload(df)
    assert result.missing_required == []
    assert [r["grade"] for r in result.records] == ["SCM440", "S45C"]
    assert result.records[0]["hardness"] == 38.5
    assert result.records[1]["impact_strength"] is None
    assert list(result.errors["행"]) == [4, 5, 7]


def test_prepare_upload_missing_required_column():
    df = pd.DataFrame({"Grade": ["A"], "Q조건": [850]})
    result = io_utils.prepare_upload(df)
    assert result.missing_required == ["t_condition"]
    assert result.records == []


def test_read_cp949_csv():
    csv = "Grade,Q조건,T조건\n한글강종,850,550\n"
    df = io_utils.read_upload("x.csv", csv.encode("cp949"))
    assert io_utils.prepare_upload(df).records[0]["grade"] == "한글강종"


def test_csv_round_trip_with_bom():
    original = pd.DataFrame(
        [{"id": 1, "grade": "한글강종", "q_condition": 850.0, "t_condition": 550.0,
          "hardness": 38.5, "yield_strength": None, "tensile_strength": 1180.0,
          "impact_strength": 62.0, "created_at": "x", "updated_at": "x"}]
    )
    content = io_utils.to_csv_bytes(original)
    assert content.startswith(b"\xef\xbb\xbf")  # Excel 한글 깨짐 방지
    assert "인장강도 (MPa)" in content.decode("utf-8-sig").splitlines()[0]
    result = io_utils.prepare_upload(io_utils.read_upload("x.csv", content))
    assert result.records == [{
        "grade": "한글강종", "q_condition": 850.0, "t_condition": 550.0, "hardness": 38.5,
        "yield_strength": None, "tensile_strength": 1180.0, "impact_strength": 62.0,
    }]


def test_excel_round_trip():
    original = pd.DataFrame(
        [{"grade": "SCM440", "q_condition": 850.0, "t_condition": 550.0, "hardness": 38.5,
          "yield_strength": 1050.0, "tensile_strength": 1180.0, "impact_strength": None}]
    )
    content = io_utils.to_excel_bytes(original)
    assert pd.read_excel(BytesIO(content)).columns[0] == "Grade"
    result = io_utils.prepare_upload(io_utils.read_upload("x.xlsx", content))
    assert result.records[0]["tensile_strength"] == 1180.0
    assert result.records[0]["impact_strength"] is None
