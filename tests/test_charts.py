import pandas as pd
import pytest

from charts import aggregate, color_map, has_enough_points, trend_chart


@pytest.fixture
def df():
    rows = [
        # grade, q, t, hardness, yield, tensile, impact
        ("A", 850.0, 600.0, 30.0, 900.0, 1000.0, 80.0),
        ("A", 850.0, 500.0, 40.0, 1100.0, 1200.0, 50.0),
        ("A", 850.0, 500.0, 42.0, 1110.0, 1220.0, None),  # 반복 시험, 충격 미측정
        ("A", 850.0, 550.0, None, 1000.0, 1100.0, 65.0),  # 경도 미측정
        ("A", 870.0, 500.0, 41.0, 1120.0, 1210.0, 48.0),
        ("A", 870.0, 600.0, 31.0, 910.0, 1010.0, 78.0),
    ]
    cols = ["grade", "q_condition", "t_condition", "hardness",
            "yield_strength", "tensile_strength", "impact_strength"]
    return pd.DataFrame(rows, columns=cols)


def line_traces(fig, prop_index):
    """prop_index번째 서브플롯(0~3)의 평균 선 trace 목록."""
    xaxis = "x" if prop_index == 0 else f"x{prop_index + 1}"
    return [t for t in fig.data if t.mode == "lines+markers" and t.xaxis == xaxis]


def test_aggregate_mean_count_and_sort(df):
    agg = aggregate(df, "t_condition", "q_condition")
    hardness = agg[(agg.q_condition == 850.0) & (agg.property == "hardness")]
    assert list(hardness.t_condition) == [500.0, 600.0]  # 550은 미측정이라 제외, 오름차순
    assert list(hardness["mean"]) == [41.0, 30.0]
    assert list(hardness["count"]) == [2, 1]


def test_trend_chart_single_group(df):
    fig = trend_chart(df, "t_condition", "q_condition", [850.0])
    tensile = line_traces(fig, 2)
    assert len(tensile) == 1
    assert list(tensile[0].x) == [500.0, 550.0, 600.0]
    assert list(tensile[0].y) == [1210.0, 1100.0, 1000.0]
    assert list(tensile[0].customdata) == [2, 1, 1]
    # 반복 시험의 개별 측정값은 반투명 점으로 따로 표시
    raw = [t for t in fig.data if t.mode == "markers" and t.xaxis == "x3"]
    assert sorted(raw[0].y) == [1200.0, 1220.0]
    # 축 제목에 단위
    assert fig.layout.xaxis.title.text == "T조건 (℃)"
    assert "인장강도 (MPa)" in [a.text for a in fig.layout.annotations]  # 단위는 서브플롯 제목에


def test_trend_chart_multiple_groups_one_legend_each(df):
    fig = trend_chart(df, "t_condition", "q_condition", [870.0, 850.0])
    assert len(line_traces(fig, 0)) == 2
    legend_names = [t.name for t in fig.data if t.showlegend]
    assert legend_names == ["Q조건 850℃", "Q조건 870℃"]


def test_trend_chart_q_axis(df):
    fig = trend_chart(df, "q_condition", "t_condition", [500.0])
    hardness = line_traces(fig, 0)[0]
    assert list(hardness.x) == [850.0, 870.0]
    assert fig.layout.xaxis.title.text == "Q조건 (℃)"


def test_insufficient_subplot_gets_annotation(df):
    # T=500만 고르면 X값이 하나뿐 → 모든 서브플롯에 '데이터 부족'
    sub = df[df.t_condition == 500.0]
    fig = trend_chart(sub, "q_condition", "t_condition", [500.0])
    assert sum(a.text == "데이터 부족" for a in fig.layout.annotations) == 0  # Q가 2개
    fig = trend_chart(df[df.q_condition == 850.0].head(1), "t_condition", "q_condition", [850.0])
    assert sum(a.text == "데이터 부족" for a in fig.layout.annotations) == 4


def test_color_follows_value_not_selection(df):
    colors = color_map([830.0, 850.0, 870.0])
    only_870 = trend_chart(df, "t_condition", "q_condition", [870.0], colors)
    both = trend_chart(df, "t_condition", "q_condition", [850.0, 870.0], colors)
    color_870 = line_traces(only_870, 0)[0].line.color
    assert [t.line.color for t in line_traces(both, 0) if t.name == "Q조건 870℃"] == [color_870]
    assert color_map([1.0], "dark")[1.0][0] != color_map([1.0], "light")[1.0][0]
    assert color_map(list(range(9)))[8][1] == "dash"  # 8개를 넘으면 점선으로 구분


def test_legend_only_for_multiple_groups(df):
    assert not trend_chart(df, "t_condition", "q_condition", [850.0]).layout.showlegend
    assert trend_chart(df, "t_condition", "q_condition", [850.0, 870.0]).layout.showlegend


def test_has_enough_points(df):
    assert has_enough_points(df, "t_condition")
    assert not has_enough_points(df[df.t_condition == 500.0], "t_condition")
    assert not has_enough_points(df.iloc[0:0], "t_condition")
