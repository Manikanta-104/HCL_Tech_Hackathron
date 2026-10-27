"""
Plotly chart builders.

Each function takes a KPI DataFrame and returns a ready to render figure.
Keeping chart code here keeps the page code short and makes every chart
look the same (fonts, margins, colours, legend position).
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.dashboard.components import (
    CHANNEL_COLOURS,
    COLOURS,
    SEGMENT_COLOURS,
    SEQUENTIAL_SCALE,
    SEVERITY_COLOURS,
)

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _style(fig: go.Figure, height: int = 340, legend: bool = True) -> go.Figure:
    """Shared layout for every chart."""
    # Legend sits under the plot so it never collides with the title
    fig.update_layout(
        height=height + (40 if legend else 0),
        margin=dict(l=10, r=10, t=44, b=10),
        font=dict(family="IBM Plex Sans, Segoe UI, sans-serif", size=12),
        title=dict(x=0, xanchor="left", font=dict(size=14)),
        legend=dict(orientation="h", yanchor="top", y=-0.18, xanchor="left", x=0, title=None),
        showlegend=legend,
        hoverlabel=dict(font_size=12),
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="rgba(127,127,127,0.18)", zeroline=False)
    return fig


# ---------------------------------------------------------------------- #
# Segmentation
# ---------------------------------------------------------------------- #
def segment_value_bar(df: pd.DataFrame) -> go.Figure:
    """Total value and customers per segment."""
    fig = px.bar(
        df, x="segment", y="total_value", color="segment", color_discrete_map=SEGMENT_COLOURS,
        text=df["value_share_pct"].map(lambda v: f"{v:.1f}%"),
        hover_data={"customers": True, "transactions": True, "avg_txn_value": ":,.2f"},
        title="Transaction value by segment",
        labels={"total_value": "Total value", "segment": ""},
    )
    fig.update_traces(textposition="outside", cliponaxis=False)
    return _style(fig, legend=False)


def segment_behaviour_bar(df: pd.DataFrame) -> go.Figure:
    """Average spend per customer and transactions per customer by segment."""
    fig = go.Figure()
    fig.add_bar(x=df["segment"], y=df["avg_spend_per_customer"], name="Avg spend per customer",
                marker_color=COLOURS["navy"], yaxis="y")
    fig.add_scatter(x=df["segment"], y=df["txns_per_customer"], name="Transactions per customer",
                    mode="lines+markers", marker=dict(size=10, color=COLOURS["sand"]),
                    line=dict(color=COLOURS["sand"], width=3), yaxis="y2")
    fig.update_layout(
        title="Spend and frequency per customer",
        yaxis=dict(title="Avg spend"),
        yaxis2=dict(title="Txns / customer", overlaying="y", side="right", showgrid=False,
                    rangemode="tozero", tickformat=".1f"),
    )
    return _style(fig)


def value_tier_stacked(df: pd.DataFrame) -> go.Figure:
    """Customers in each value tier, split by segment."""
    fig = px.bar(
        df, x="value_tier", y="customers", color="segment", color_discrete_map=SEGMENT_COLOURS,
        category_orders={"value_tier": ["High Value", "Mid Value", "Low Value"]},
        title="Value tiers by segment (NTILE on spend)", labels={"value_tier": "", "customers": "Customers"},
    )
    return _style(fig)


# ---------------------------------------------------------------------- #
# Peak time
# ---------------------------------------------------------------------- #
def hourly_bar(df: pd.DataFrame) -> go.Figure:
    """Transactions per hour with the peak hour highlighted."""
    full = pd.DataFrame({"txn_hour": range(24)}).merge(df, on="txn_hour", how="left").fillna(0)
    peak = full["transactions"].max()
    colours = [COLOURS["crimson"] if v == peak and peak > 0 else COLOURS["teal"] for v in full["transactions"]]
    fig = go.Figure(go.Bar(
        x=full["txn_hour"], y=full["transactions"], marker_color=colours,
        customdata=full[["total_value"]], hovertemplate="%{x}:00<br>%{y} txns<br>Value %{customdata[0]:,.0f}<extra></extra>",
    ))
    fig.update_layout(title="Transactions by hour of day (peak in red)", xaxis=dict(dtick=2, title="Hour"),
                      yaxis_title="Transactions")
    return _style(fig, legend=False)


def day_hour_heatmap(df: pd.DataFrame) -> go.Figure:
    """Weekday by hour heatmap of transaction counts."""
    grid = (
        df.pivot_table(index="day_of_week", columns="txn_hour", values="transactions", aggfunc="sum", fill_value=0)
        .reindex(index=DAY_ORDER, columns=range(24), fill_value=0)
    )
    fig = go.Figure(go.Heatmap(
        z=grid.values, x=list(grid.columns), y=list(grid.index), colorscale=SEQUENTIAL_SCALE,
        hovertemplate="%{y} %{x}:00<br>%{z} txns<extra></extra>", colorbar=dict(title="Txns"),
    ))
    fig.update_layout(title="When customers transact: weekday x hour", xaxis=dict(dtick=2, title="Hour"))
    return _style(fig, height=320, legend=False)


def time_bucket_donut(df: pd.DataFrame) -> go.Figure:
    """Share of transactions by part of day."""
    fig = go.Figure(go.Pie(
        labels=df["time_bucket"], values=df["transactions"], hole=0.55, sort=False,
        marker=dict(colors=[COLOURS["navy"], COLOURS["teal"], COLOURS["sand"], COLOURS["teal_light"]]),
    ))
    fig.update_layout(title="Share by part of day")
    return _style(fig)


def weekday_bar(df: pd.DataFrame) -> go.Figure:
    """Transactions and average value per weekday."""
    fig = px.bar(df, x="day_of_week", y="transactions", title="Transactions by weekday",
                 color_discrete_sequence=[COLOURS["navy"]], labels={"day_of_week": "", "transactions": "Transactions"},
                 hover_data={"avg_value": ":,.2f", "total_value": ":,.0f"})
    return _style(fig, legend=False)


def daily_trend_line(df: pd.DataFrame) -> go.Figure:
    """Daily transaction value with flagged transaction counts."""
    fig = go.Figure()
    fig.add_bar(x=df["txn_date"], y=df["total_value"], name="Daily value", marker_color=COLOURS["teal_light"])
    fig.add_scatter(x=df["txn_date"], y=df["flagged_transactions"], name="Flagged txns", yaxis="y2",
                    mode="lines+markers", line=dict(color=COLOURS["crimson"], width=2))
    fig.update_layout(title="Daily value and flagged transactions", yaxis_title="Value",
                      yaxis2=dict(title="Flagged", overlaying="y", side="right", showgrid=False,
                                  rangemode="tozero", dtick=1))
    return _style(fig)


# ---------------------------------------------------------------------- #
# Merchants and geo
# ---------------------------------------------------------------------- #
def repeat_by_segment_bar(df: pd.DataFrame) -> go.Figure:
    """Repeat merchant ratio per segment."""
    fig = px.bar(df, x="segment", y="repeat_merchant_ratio_pct", color="segment", color_discrete_map=SEGMENT_COLOURS,
                 text=df["repeat_merchant_ratio_pct"].map(lambda v: f"{v:.1f}%"),
                 title="Repeat merchant ratio by segment", labels={"repeat_merchant_ratio_pct": "Repeat %", "segment": ""})
    fig.update_traces(textposition="outside", cliponaxis=False)
    return _style(fig, legend=False)


def top_merchants_bar(df: pd.DataFrame) -> go.Figure:
    """Top merchants by transaction count, split into first and repeat visits."""
    data = df.sort_values("transactions").copy()
    data["label"] = data["merchant_name"] + " (" + data["merchant_id"] + ")"
    fig = go.Figure()
    fig.add_bar(y=data["label"], x=data["unique_customers"], name="First visits", orientation="h",
                marker_color=COLOURS["teal"], customdata=data[["merchant_category", "merchant_risk_level"]],
                hovertemplate="%{y}<br>%{customdata[0]}, %{customdata[1]} risk<br>%{x} first visits<extra></extra>")
    fig.add_bar(y=data["label"], x=data["repeat_visits"], name="Repeat visits", orientation="h",
                marker_color=COLOURS["sand"])
    fig.update_layout(barmode="stack", title="Top merchants: first vs repeat visits", xaxis_title="Transactions")
    return _style(fig, height=380)


def merchant_risk_exposure_bar(df: pd.DataFrame) -> go.Figure:
    """Share of transactions and value by merchant risk rating."""
    order = ["High", "Medium", "Low", "Unknown"]
    data = df.melt(id_vars="merchant_risk_level", value_vars=["txn_share_pct", "value_share_pct"],
                   var_name="measure", value_name="share")
    data["measure"] = data["measure"].map({"txn_share_pct": "Share of transactions",
                                           "value_share_pct": "Share of value"})
    fig = px.bar(data, x="merchant_risk_level", y="share", color="measure", barmode="group",
                 category_orders={"merchant_risk_level": order},
                 color_discrete_sequence=[COLOURS["navy"], COLOURS["teal"]],
                 text=data["share"].map(lambda v: f"{v:.1f}%"),
                 title="Exposure by merchant risk rating", labels={"merchant_risk_level": "", "share": "Share %"})
    fig.update_traces(textposition="outside", cliponaxis=False)
    return _style(fig)


def merchant_category_heatmap(df: pd.DataFrame) -> go.Figure:
    """Registered merchant category against the category booked on the transaction."""
    grid = df.pivot_table(index="merchant_category", columns="transaction_category", values="transactions",
                          aggfunc="sum", fill_value=0)
    fig = go.Figure(go.Heatmap(z=grid.values, x=list(grid.columns), y=list(grid.index), colorscale=SEQUENTIAL_SCALE,
                               text=grid.values, texttemplate="%{text}", colorbar=dict(title="Txns")))
    fig.update_layout(title="Merchant category (rows) vs booked category (diagonal = match)",
                      xaxis_title="Booked on transaction", yaxis_title="Merchant registered as")
    return _style(fig, legend=False)


def geo_index_histogram(df: pd.DataFrame) -> go.Figure:
    """Distribution of the per customer geo consistency index."""
    data = df[df["transactions"] >= 2]
    fig = px.histogram(data, x="geo_consistency_index", nbins=10, color="segment",
                       color_discrete_map=SEGMENT_COLOURS, barmode="stack",
                       title="Geo consistency index per customer (2+ txns)",
                       labels={"geo_consistency_index": "Share of txns at most used location"})
    fig.update_xaxes(range=[0, 1.05])
    return _style(fig)


def geo_locations_scatter(df: pd.DataFrame) -> go.Figure:
    """Transactions versus distinct locations per customer."""
    fig = px.scatter(df, x="transactions", y="distinct_locations", color="segment", size="transactions",
                     color_discrete_map=SEGMENT_COLOURS, hover_data=["customer_id", "customer_name", "geo_consistency_index"],
                     title="Locations used vs transactions", labels={"distinct_locations": "Distinct locations",
                                                                     "transactions": "Transactions"})
    max_val = max(df["transactions"].max(), 1)
    fig.add_shape(type="line", x0=0, y0=0, x1=max_val, y1=max_val, line=dict(dash="dot", color=COLOURS["slate"]))
    return _style(fig)


# ---------------------------------------------------------------------- #
# Channel mix
# ---------------------------------------------------------------------- #
def channel_donut(df: pd.DataFrame) -> go.Figure:
    """Transaction share by channel."""
    fig = go.Figure(go.Pie(
        labels=df["channel"], values=df["transactions"], hole=0.55,
        marker=dict(colors=[CHANNEL_COLOURS.get(c, COLOURS["slate"]) for c in df["channel"]]),
    ))
    fig.update_layout(title="Channel share of transactions")
    return _style(fig)


def channel_by_segment_bar(df: pd.DataFrame) -> go.Figure:
    """100% stacked channel mix inside each segment."""
    fig = px.bar(df, x="segment", y="share_within_segment_pct", color="channel", color_discrete_map=CHANNEL_COLOURS,
                 title="Channel mix inside each segment", labels={"share_within_segment_pct": "Share %", "segment": ""},
                 text=df["share_within_segment_pct"].map(lambda v: f"{v:.0f}%"))
    fig.update_layout(barmode="stack", yaxis=dict(range=[0, 100]))
    return _style(fig)


def channel_by_month_line(df: pd.DataFrame) -> go.Figure:
    """Channel share over months."""
    fig = px.line(df, x="year_month", y="share_within_month_pct", color="channel", markers=True,
                  color_discrete_map=CHANNEL_COLOURS, title="Channel share by month",
                  labels={"share_within_month_pct": "Share %", "year_month": "Month"})
    return _style(fig)


def preferred_vs_actual_heatmap(df: pd.DataFrame) -> go.Figure:
    """Stated preferred channel versus the channel actually used."""
    grid = df.pivot_table(index="preferred_channel", columns="actual_channel", values="transactions",
                          aggfunc="sum", fill_value=0)
    fig = go.Figure(go.Heatmap(z=grid.values, x=list(grid.columns), y=list(grid.index), colorscale=SEQUENTIAL_SCALE,
                               text=grid.values, texttemplate="%{text}", colorbar=dict(title="Txns")))
    fig.update_layout(title="Preferred channel (rows) vs actual channel used", xaxis_title="Actual", yaxis_title="Preferred")
    return _style(fig, legend=False)


# ---------------------------------------------------------------------- #
# Categories
# ---------------------------------------------------------------------- #
def category_bar(df: pd.DataFrame) -> go.Figure:
    """Spend by transaction category."""
    data = df.sort_values("total_value")
    fig = px.bar(data, y="category", x="total_value", orientation="h", title="Spend by category",
                 color_discrete_sequence=[COLOURS["teal"]], labels={"total_value": "Total value", "category": ""},
                 hover_data={"transactions": True, "avg_value": ":,.2f"})
    return _style(fig, legend=False)


def amount_band_bar(df: pd.DataFrame) -> go.Figure:
    """Transactions per amount band."""
    fig = px.bar(df, x="amount_band", y="transactions", title="Transactions by amount band",
                 color_discrete_sequence=[COLOURS["navy"]], labels={"amount_band": "", "transactions": "Transactions"})
    return _style(fig, legend=False)


# ---------------------------------------------------------------------- #
# Alerts
# ---------------------------------------------------------------------- #
def alerts_by_rule_bar(df: pd.DataFrame) -> go.Figure:
    """Alert counts per rule coloured by severity."""
    data = df.sort_values("alerts")
    fig = px.bar(data, y="rule_name", x="alerts", color="severity", orientation="h",
                 color_discrete_map=SEVERITY_COLOURS, title="Alerts by rule",
                 hover_data={"customers_affected": True, "value_at_risk": ":,.0f"},
                 labels={"rule_name": "", "alerts": "Alerts"})
    return _style(fig, height=360)


def risk_level_bar(df: pd.DataFrame) -> go.Figure:
    """Transactions per risk level."""
    order = ["High", "Medium", "Low", "None"]
    fig = px.bar(df, x="risk_level", y="transactions", color="risk_level", color_discrete_map=SEVERITY_COLOURS,
                 category_orders={"risk_level": order}, title="Transactions by risk level",
                 labels={"risk_level": "", "transactions": "Transactions"}, text="transactions")
    fig.update_traces(textposition="outside", cliponaxis=False)
    return _style(fig, legend=False)


# ---------------------------------------------------------------------- #
# Customer view
# ---------------------------------------------------------------------- #
def customer_timeline(df: pd.DataFrame) -> go.Figure:
    """Each transaction of a customer over time; size shows risk score."""
    data = df.copy()
    data["marker_size"] = 10 + data["risk_score"] * 4
    fig = px.scatter(data, x="txn_datetime", y="amount", color="channel", size="marker_size",
                     color_discrete_map=CHANNEL_COLOURS, symbol="risk_level",
                     hover_data={"transaction_id": True, "merchant_id": True, "location_id": True,
                                 "category": True, "risk_level": True, "marker_size": False},
                     title="Transaction timeline (bigger marker = higher risk)",
                     labels={"txn_datetime": "", "amount": "Amount"})
    return _style(fig)


def customer_category_donut(df: pd.DataFrame) -> go.Figure:
    """Spend split by category for one customer."""
    data = df.groupby("category", as_index=False)["amount"].sum()
    fig = go.Figure(go.Pie(labels=data["category"], values=data["amount"], hole=0.55,
                           marker=dict(colors=[COLOURS["navy"], COLOURS["teal"], COLOURS["sand"],
                                               COLOURS["teal_light"], COLOURS["slate"]])))
    fig.update_layout(title="Spend by category")
    return _style(fig)
