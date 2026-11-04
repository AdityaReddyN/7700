"""Plotly figures for the M9 app — white background, black text, red accents.

Pure functions over a track DataFrame (columns: time, lat, lon, velocity,
vertrate, baroaltitude). Each returns a go.Figure. The red series is always the
anomalous / position-implied quantity so the drift or jump reads at a glance.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from app import loader

RED = "#D7263D"
BLACK = "#111111"
GREY = "#8A8A8A"
BLUE = "#1F6FEB"
GREEN = "#1A7F37"

_LAYOUT = dict(template="plotly_white", font=dict(color=BLACK, size=13),
               paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
               margin=dict(l=50, r=20, t=50, b=40),
               legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0))


def _empty(msg: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(**_LAYOUT, height=300,
                      annotations=[dict(text=msg, showarrow=False, x=0.5, y=0.5,
                                        xref="paper", yref="paper", font=dict(color=GREY))])
    return fig


def _largest_jump_idx(df: pd.DataFrame) -> int | None:
    """Index of the point ending the largest position step (highlighted red)."""
    if len(df) < 2:
        return None
    speeds = loader.implied_speed_kt(df)
    best_i, best_v = None, -1.0
    for i, v in enumerate(speeds):
        if v is not None and v > best_v:
            best_i, best_v = i, v
    return best_i


def track_map(df: pd.DataFrame, title: str = "Ground track (lat / lon)") -> go.Figure:
    if df.empty:
        return _empty("no track data")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["lon"], y=df["lat"], mode="lines+markers",
                             line=dict(color=BLACK, width=2),
                             marker=dict(size=4, color=BLACK), name="reported path"))
    fig.add_trace(go.Scatter(x=[df["lon"].iloc[0]], y=[df["lat"].iloc[0]], mode="markers",
                             marker=dict(size=12, color=GREEN, symbol="circle"), name="start"))
    fig.add_trace(go.Scatter(x=[df["lon"].iloc[-1]], y=[df["lat"].iloc[-1]], mode="markers",
                             marker=dict(size=12, color=RED, symbol="x"), name="end"))
    j = _largest_jump_idx(df)
    if j is not None and j >= 1:
        fig.add_trace(go.Scatter(
            x=[df["lon"].iloc[j - 1], df["lon"].iloc[j]],
            y=[df["lat"].iloc[j - 1], df["lat"].iloc[j]], mode="lines",
            line=dict(color=RED, width=4), name="largest step"))
    fig.update_layout(**_LAYOUT, height=420, title=title,
                      xaxis_title="longitude", yaxis_title="latitude")
    return fig


def _rolling_median(xs: list[float | None], window: int = 5) -> list[float | None]:
    """Centred rolling median over non-null points — smooths finite-difference noise."""
    out: list[float | None] = []
    half = window // 2
    for i in range(len(xs)):
        vals = [v for v in xs[max(0, i - half):i + half + 1] if v is not None]
        out.append(sorted(vals)[len(vals) // 2] if vals else None)
    return out


def speed_drift(df: pd.DataFrame,
                title: str = "Reported speed vs position-implied speed") -> go.Figure:
    """The spoofing/velocity signature: the two speeds diverge; implied line smoothed."""
    if df.empty:
        return _empty("no track data")
    t0 = df["time"].iloc[0]
    mins = [(t - t0) / 60.0 for t in df["time"]]
    implied = loader.implied_speed_kt(df)
    implied_s = _rolling_median(implied)
    reported_kt = [v * 1.943_844 for v in df["velocity"].tolist()]  # m/s -> kt
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=mins, y=reported_kt, mode="lines",
                             line=dict(color=BLACK, width=2.5), name="reported speed (kt)"))
    fig.add_trace(go.Scatter(x=mins, y=implied, mode="markers",
                             marker=dict(color="#F3AEB8", size=4), name="implied (raw)"))
    fig.add_trace(go.Scatter(x=mins, y=implied_s, mode="lines",
                             line=dict(color=RED, width=2.5),
                             name="position-implied speed (smoothed)"))
    fig.update_layout(**_LAYOUT, height=360, title=title,
                      xaxis_title="minutes into window", yaxis_title="ground speed (kt)")
    return fig


def residual(df: pd.DataFrame,
             title: str = "Speed residual (implied − reported)") -> go.Figure:
    if df.empty:
        return _empty("no track data")
    t0 = df["time"].iloc[0]
    mins = [(t - t0) / 60.0 for t in df["time"]]
    implied = loader.implied_speed_kt(df)
    reported_kt = [v * 1.943_844 for v in df["velocity"].tolist()]
    resid = [None if im is None else im - rp for im, rp in zip(implied, reported_kt, strict=True)]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=mins, y=resid, mode="lines", fill="tozeroy",
                             line=dict(color=RED, width=2), name="residual (kt)"))
    fig.add_hline(y=0, line=dict(color=GREY, width=1))
    fig.update_layout(**_LAYOUT, height=300, title=title,
                      xaxis_title="minutes into window", yaxis_title="residual (kt)")
    return fig


def altitude(df: pd.DataFrame, title: str = "Barometric altitude") -> go.Figure:
    if df.empty or "baroaltitude" not in df.columns:
        return _empty("no altitude data")
    t0 = df["time"].iloc[0]
    mins = [(t - t0) / 60.0 for t in df["time"]]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=mins, y=df["baroaltitude"], mode="lines",
                             line=dict(color=BLUE, width=2), name="baro altitude (m)"))
    fig.update_layout(**_LAYOUT, height=280, title=title,
                      xaxis_title="minutes into window", yaxis_title="altitude (m)")
    return fig
