from __future__ import annotations

import colorsys
from itertools import product

import altair as alt
import ibis
from ibis import _
from ibis.expr.types import Table
import ipywidgets
import pandas as pd

from mismo.compare import Comparison, ComparisonLevel, Comparisons
from mismo.fs._plot import LOG_ODDS_COLOR_SCALE
from mismo.fs._util import odds_to_log_odds
from mismo.fs._weights import Weights


def compared_dashboard(
    compared: Table,
    comparisons: Comparisons,
    weights: Weights | None = None,
    *,
    width: int = 500,
) -> ipywidgets.VBox:
    """A dashboard for debugging compared record pairs.

    Used to see which comparison levels are common, which are rare, and which
    Comparisons are related to each other. For example, exact matches should
    appear together across all Comparisons, this probably represents true
    matches.

    Parameters
    ----------
    compared : Table
        The result of a comparison.
    comparisons : Comparisons
        The Comparisons used to compare the records.
    weights : Weights, optional
        The Weights used to score the comparison, by default None
        If provided, the chart will be colored by the odds found from
        the Weights.
    width : int, optional
        The width of the chart, by default 500

    Returns
    -------
    ipywidgets.VBox
        The dashboard.
    """
    cols = [comp.name for comp in comparisons]
    compared = compared.mutate(
        vector_id=ibis.literal(":").join([compared[c] for c in cols]),
    )
    chart = _compared_chart(compared, comparisons, weights, width=width)
    chart_widget = alt.JupyterChart(chart)
    limiter_widget = ipywidgets.IntSlider(
        min=1, max=100, value=5, step=1, description="Show Pairs:"
    )
    vector_title_widget = ipywidgets.HTML()
    table_widget = ipywidgets.HTML()

    def set_table(data: Table):
        df = data.limit(limiter_widget.value).to_pandas()
        table_widget.value = df.to_html(index=False, render_links=True)

    set_table(compared.head(0))

    def on_select(change):
        vector_id = change.new.value[0]["vector_id"]
        filtered = compared[_.vector_id == vector_id]
        vector_values = filtered[cols].limit(1).to_pandas().iloc[0].to_dict()
        vector_title_widget.value = "&nbsp;".join(
            f"<b>{k}</b>: {v}" for k, v in vector_values.items()
        )
        set_table(filtered.drop("vector_id", *cols))

    chart_widget.selections.observe(on_select, ["vector_click"])

    return ipywidgets.VBox(
        [
            chart_widget,
            limiter_widget,
            vector_title_widget,
            table_widget,
        ]
    )


def _compared_chart(
    compared: Table,
    comparisons: Comparisons,
    weights: Weights | None = None,
    *,
    width: int = 500,
) -> alt.Chart:
    cols = [comp.name for comp in comparisons]

    vector_counts = compared.group_by(cols + ["vector_id"]).agg(n_pairs=_.count())
    vector_counts = vector_counts.mutate(
        pct_pairs=_.n_pairs / _.n_pairs.sum(),
    )
    if weights is not None:
        vector_counts = weights.score(vector_counts)
        vector_counts = vector_counts.mutate(odds=_.odds.clip(upper=10**10))
        vector_counts = vector_counts.mutate(log_odds=odds_to_log_odds(_.odds))
        hist_color = alt.Color(
            "log_odds",
            title="Odds",
            scale=LOG_ODDS_COLOR_SCALE,
            legend=alt.Legend(labelExpr=10**alt.datum.value),
        )
        hist_extra_tooltips = [alt.Tooltip("odds", title="Odds", format=",")]
    else:
        hist_color = None
        hist_extra_tooltips = []
    vector_counts = vector_counts.to_pandas()

    scrubber_filter = alt.selection_interval(encodings=["x"])
    vector_fader_mouseover = alt.selection_point(
        name="vector_mouseover", fields=["vector_id"], on="mouseover"
    )
    vector_fader_click = alt.selection_point(
        name="vector_click", fields=["vector_id"], on="click"
    )
    opacity_vector = alt.condition(vector_fader_mouseover, alt.value(1), alt.value(0.8))
    level_color = alt.Color(
        "level_uid",
        title="Comparison:Level",
        scale=_make_level_color_scale(comparisons),
        legend=None,
    )
    x = alt.X(
        "vector_id:N",
        axis=None,
        sort=alt.EncodingSortField(
            "n_pairs" if weights is None else "odds", order="descending"
        ),
    )
    scrubber_chart = (
        alt.Chart(
            vector_counts,
            height=50,
            width=width,
            title=alt.Title(
                text="<drag to select>",
                dy=20,
                anchor="middle",
                fontSize=12,
                color="gray",
            ),
        )
        .mark_rect()
        .encode(
            x=x,
            y=alt.Y(
                "n_pairs:Q",
                title="Number of Pairs",
                scale=alt.Scale(type="log"),
                axis=None,
            ),
            opacity=opacity_vector,
            **{"color": hist_color.legend(None)} if hist_color is not None else {},
        )
        .add_params(scrubber_filter)
        .add_params(vector_fader_mouseover)
    )
    hist = (
        alt.Chart(vector_counts, width=width)
        .mark_rect(stroke=None)
        .encode(
            x=x,
            y=alt.Y(
                "n_pairs:Q",
                title="Number of Pairs",
                scale=alt.Scale(type="log"),
            ),
            opacity=opacity_vector,
            tooltip=[
                alt.Tooltip("n_pairs", title="Number of Pairs", format=","),
                alt.Tooltip("pct_pairs", title="Percent of Pairs", format="%"),
                *hist_extra_tooltips,
                *cols,
            ],
            **{"color": hist_color} if hist_color is not None else {},
        )
        .transform_filter(scrubber_filter)
        .add_params(vector_fader_mouseover)
        .add_params(vector_fader_click)
    )
    vector_chart = (
        alt.Chart(_vector_grid_data(comparisons, vector_counts), height=80, width=width)
        .mark_rect()
        .encode(
            x=x,
            y=alt.Y(
                "comparison",
                title="Comparison",
                sort=cols,
            ),
            color=level_color,
            opacity=opacity_vector,
            tooltip=["level"],
        )
        .transform_filter(scrubber_filter)
        .add_params(vector_fader_mouseover)
        .add_params(vector_fader_click)
    )
    together = alt.vconcat(scrubber_chart, hist, vector_chart, spacing=0)
    together = together.properties(
        title=alt.Title(
            text="Distribution of Comparison Levels",
            subtitle=f"Total Pairs: {vector_counts.n_pairs.sum():,}",
            anchor="middle",
            fontSize=14,
        )
    )
    return together


def _frange(start, stop, n):
    return [start + i * (stop - start) / n for i in range(n)]


def _vector_grid_data(
    comparisons: Comparisons, vector_data: pd.DataFrame
) -> pd.DataFrame:
    records = []
    for levels in product(*comparisons):
        vector_id = ":".join(level.name for level in levels)
        for comp, level in zip(comparisons, levels):
            level_info = {c.name: None for c in comparisons}
            level_info[comp.name] = level.name
            records.append(
                {
                    "vector_id": vector_id,
                    "level_uid": _level_uid(comp, level),
                    "comparison": comp.name,
                    "level": level.name,
                    **level_info,
                }
            )
    result = pd.DataFrame(records)
    # only include vectors that are in the vector_data
    # and add in per-vector info such as n_pairs
    result = vector_data.merge(result, on="vector_id", how="left")
    return result


def _make_level_color_scale(comparisons: Comparisons) -> alt.Scale:
    domain = []
    range = []
    hues = _frange(0, 1, len(comparisons))
    for comp, hue in zip(comparisons, hues):
        shades = _frange(0.2, 0.9, len(comp))
        for level, shade in zip(comp, shades):
            r, g, b = colorsys.hsv_to_rgb(hue, 1, shade)
            r = int(r * 255)
            g = int(g * 255)
            b = int(b * 255)
            hex_color = f"#{r:02x}{g:02x}{b:02x}"
            domain.append(_level_uid(comp, level))
            range.append(hex_color)
    return alt.Scale(domain=domain, range=range)


def _level_uid(comparison: Comparison, level: ComparisonLevel) -> str:
    return comparison.name + ":" + level.name


# TODO: make this work as a filter for the above histogram
def _make_legend_plot(longer: Table, color_map):
    levels = longer.group_by(["comparison", "level"]).agg(
        id=_.id.first(),
        level_idx=_.level_idx.first(),
        vector_ids=_.vector_id.collect(),
    )
    levels = levels.distinct()

    comparison_level_filter = alt.selection_point(fields=["comparison", "level"])
    # Use names based off of https://github.com/altair-viz/altair/issues/2366
    vector_ids_filter = alt.selection_point(fields=["vector_ids"], name="vidf")

    legend_base = (
        alt.Chart(levels.to_pandas(), height=100)
        .mark_rect()
        .encode(
            x=alt.X(
                "level_idx:N", axis=alt.Axis(title="Level", labels=False, ticks=False)
            ),
            y=alt.Y(
                "comparison",
                title="Comparison",
            ),
            opacity=alt.condition(
                comparison_level_filter, alt.value(1), alt.value(0.4)
            ),
            tooltip=["level"],
        )
    )
    legend_rects = legend_base.encode(
        color=alt.Color(
            "id",
            title="Comparison:Level",
            scale=alt.Scale(domain=color_map[0], range=color_map[1]),
            legend=None,
        ),
        tooltip=["level"],
    )
    legend_text = legend_base.mark_text(
        align="center",
        baseline="middle",
        color="white",
    ).encode(
        text="level",
    )
    legend = legend_rects + legend_text
    legend = legend.add_params(comparison_level_filter)
    legend = legend.add_params(vector_ids_filter)
    return legend
