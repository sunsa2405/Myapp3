"""경향 그래프 생성 (PRD F2, F3, F4)."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from db import COLUMN_LABELS, CONDITION_COLUMNS, PROPERTIES

MIN_POINTS = 2  # 경향을 그리기 위한 최소 X값 개수

# 색각이상 구분 검증을 통과한 순서. 순서를 바꾸지 말 것 (.streamlit/config.toml과 동일).
PALETTES = {
    "light": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"],
    "dark": ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"],
}
MUTED = "#898781"  # 축·보조 텍스트 (라이트·다크 공통)


def format_value(value: float) -> str:
    return f"{value:g}"


def aggregate(df: pd.DataFrame, x_col: str, group_col: str) -> pd.DataFrame:
    """그룹·물성·X값별 평균과 측정 건수. 빈 물성 값은 제외한다.

    반환 열: group_col, property, x_col, mean, count
    """
    long = df.melt(
        id_vars=[group_col, x_col],
        value_vars=list(PROPERTIES),
        var_name="property",
        value_name="value",
    ).dropna(subset=["value"])
    return (
        long.groupby([group_col, "property", x_col])["value"]
        .agg(mean="mean", count="count")
        .reset_index()
        .sort_values([group_col, "property", x_col], ignore_index=True)
    )


def has_enough_points(df: pd.DataFrame, x_col: str) -> bool:
    return df[x_col].nunique() >= MIN_POINTS


def color_map(all_values: list[float], theme: str = "light") -> dict[float, tuple[str, str]]:
    """조건 값 → (색, 선 모양).

    색은 선택 순서가 아니라 그 Grade의 전체 조건 목록에서의 위치로 정한다. 그래야 다른 조건을
    더 고르거나 빼도 남은 선의 색이 바뀌지 않는다. 8개를 넘으면 색을 다시 쓰되 점선으로 구분한다.
    """
    palette = PALETTES.get(theme, PALETTES["light"])
    return {
        value: (palette[i % len(palette)], "solid" if i < len(palette) else "dash")
        for i, value in enumerate(sorted(all_values))
    }


def trend_chart(
    df: pd.DataFrame,
    x_col: str,
    group_col: str,
    group_values: list[float],
    colors: dict[float, tuple[str, str]] | None = None,
) -> go.Figure:
    """4개 물성의 2×2 경향 그래프.

    X축은 x_col(오름차순), group_values마다 선을 하나씩 그린다. 같은 X값에 측정이
    여러 건이면 평균을 선으로, 개별 측정값을 반투명 점으로 표시한다.
    colors는 color_map()의 결과. 없으면 group_values 기준으로 만든다.
    """
    colors = colors or color_map(group_values)
    sub = df[df[group_col].isin(group_values)]
    agg = aggregate(sub, x_col, group_col)
    group_meta = CONDITION_COLUMNS[group_col]
    x_label = COLUMN_LABELS[x_col]

    fig = make_subplots(
        rows=2,
        cols=2,
        # 단위는 서브플롯 제목에 둔다. 서브플롯 사이에 Y축 제목을 두면 옆 그래프의 눈금과 겹친다.
        subplot_titles=[COLUMN_LABELS[prop] for prop in PROPERTIES],
        horizontal_spacing=0.14,
        vertical_spacing=0.2,
    )

    for group_value in sorted(group_values):
        color, dash = colors[group_value]
        name = f"{group_meta['label']} {format_value(group_value)}{group_meta['unit']}"
        group_raw = sub[sub[group_col] == group_value]
        legend_shown = False

        for pi, (prop, meta) in enumerate(PROPERTIES.items()):
            row, col = pi // 2 + 1, pi % 2 + 1
            unit = meta["unit"]

            raw = group_raw[[x_col, prop]].dropna()
            repeated = raw[raw.groupby(x_col)[prop].transform("count") > 1]
            if not repeated.empty:
                fig.add_trace(
                    go.Scatter(
                        x=repeated[x_col],
                        y=repeated[prop],
                        mode="markers",
                        marker={"color": color, "size": 8, "opacity": 0.35},
                        name=name,
                        legendgroup=name,
                        showlegend=False,
                        hovertemplate=(
                            f"{x_label}: %{{x:g}}<br>측정값: %{{y:.4g}} {unit}<extra>{name}</extra>"
                        ),
                    ),
                    row=row,
                    col=col,
                )

            points = agg[(agg[group_col] == group_value) & (agg["property"] == prop)]
            if points.empty:
                continue
            fig.add_trace(
                go.Scatter(
                    x=points[x_col],
                    y=points["mean"],
                    customdata=points["count"],
                    mode="lines+markers",
                    line={"color": color, "width": 2, "dash": dash},
                    marker={"color": color, "size": 9},
                    name=name,
                    legendgroup=name,
                    showlegend=not legend_shown,
                    hovertemplate=(
                        f"{x_label}: %{{x:g}}<br>평균: %{{y:.4g}} {unit}"
                        f"<br>측정 건수: %{{customdata}}<extra>{name}</extra>"
                    ),
                ),
                row=row,
                col=col,
            )
            legend_shown = True

    for pi, prop in enumerate(PROPERTIES):
        row, col = pi // 2 + 1, pi % 2 + 1
        fig.update_xaxes(title_text=x_label, row=row, col=col)
        if agg.loc[agg["property"] == prop, x_col].nunique() < MIN_POINTS:
            fig.add_annotation(
                text="데이터 부족",
                xref="x domain",
                yref="y domain",
                x=0.5,
                y=0.5,
                showarrow=False,
                font={"size": 14, "color": MUTED},
                row=row,
                col=col,
            )

    subplot_titles = {COLUMN_LABELS[prop] for prop in PROPERTIES}
    for annotation in fig.layout.annotations:
        if annotation.text in subplot_titles:
            annotation.font.size = 15
    # 눈금은 실제 측정한 조건 값에만 둔다 (830, 850, 870 사이에 840 같은 값이 생기지 않게).
    x_ticks = sorted(sub[x_col].unique())
    fig.update_xaxes(
        showgrid=False,
        ticks="outside",
        tickcolor=MUTED,
        tickmode="array",
        tickvals=x_ticks,
        ticktext=[format_value(v) for v in x_ticks],
        title_font_color=MUTED,
    )
    fig.update_yaxes(gridwidth=1, zeroline=False)
    # 선이 하나뿐이면 범례 대신 위쪽 선택 상자가 무엇인지 알려준다.
    fig.update_layout(
        height=740,
        hovermode="closest",
        showlegend=len(group_values) > 1,
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.05, "x": 0, "title_text": ""},
        margin={"t": 70, "b": 40, "l": 50, "r": 20},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig
