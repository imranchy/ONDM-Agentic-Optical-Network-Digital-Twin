"""Plotly topology rendering with route / failure / constraint highlighting (dark NOC style)."""
from __future__ import annotations

import plotly.graph_objects as go

from . import topology as topo

PATH_COLORS = ["#00e5ff", "#76ff03", "#ffea00", "#e040fb", "#ff9100"]
BASE_EDGE = "#4a5a70"
NODE_COLOR = "#1e88e5"
BG = "#0b1220"


def _pos(g):
    return {n: (d.get("x") or 0, -(d.get("y") or 0)) for n, d in g.nodes(data=True)}


def topology_figure(sample_id: str, highlight: dict | None = None, height: int = 560,
                    gnpy: list[dict] | None = None) -> go.Figure:
    highlight = highlight or {}
    g = topo.build_graph(sample_id)
    pos = _pos(g)
    fig = go.Figure()
    failed = {tuple(sorted(highlight["failed_link"]))} if highlight.get("failed_link") else set()
    excluded = {tuple(sorted(e)) for e in highlight.get("excluded_links", [])}
    verdicts = {}
    for r in gnpy or []:
        verdicts[tuple(r.get("sites", []))] = r.get("verdict")

    # base edges + km labels
    for u, v, d in g.edges(data=True):
        key = tuple(sorted((u, v)))
        (x0, y0), (x1, y1) = pos[u], pos[v]
        if key in failed:
            color, dash, width, name = "#ff1744", "dash", 5, "failed link"
        elif key in excluded:
            color, dash, width, name = "#ff9100", "dot", 4, "inventory: unusable"
        else:
            color, dash, width, name = BASE_EDGE, "solid", 2, "fiber link"
        fig.add_trace(go.Scatter(x=[x0, x1], y=[y0, y1], mode="lines", line=dict(color=color, width=width, dash=dash),
                                 hoverinfo="text", text=f"{u}-{v}: {d['distance_km']:g} km", showlegend=False))
        fig.add_annotation(x=(x0 + x1) / 2, y=(y0 + y1) / 2, text=f"{d['distance_km']:g} km", showarrow=False,
                           font=dict(size=10, color="#9fb3c8"), bgcolor="rgba(11,18,32,0.75)")
    # highlighted paths (offset slightly so overlapping paths stay visible)
    for i, path in enumerate(highlight.get("paths", [])[:5]):
        off = (i - (len(highlight.get("paths", [])) - 1) / 2) * 9
        xs = [pos[n][0] + off for n in path]
        ys = [pos[n][1] + off for n in path]
        km = topo.path_length_km(g, path)
        v = verdicts.get(tuple(path))
        label = f"#{i + 1} {'-'.join(path)} ({km:g} km)" + (f" — {v}" if v else "")
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=PATH_COLORS[i % 5], width=6 - i * 0.8),
                                 opacity=0.85, name=label, hoverinfo="name"))
    # nodes
    special = set(highlight.get("endpoints", [])) | ({highlight["roadm"]} if highlight.get("roadm") else set())
    xs, ys, txt, colors, sizes, hover = [], [], [], [], [], []
    for n, d in g.nodes(data=True):
        xs.append(pos[n][0]); ys.append(pos[n][1]); txt.append(n)
        colors.append("#ffd600" if n in special else NODE_COLOR)
        sizes.append(34 if n in special else 28)
        hover.append(f"ROADM {n}<br>degree {g.degree(n)}<br>transceiver attached (dataset): "
                     f"{d.get('attached_transceiver')}")
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="markers+text", text=txt, textposition="middle center",
                             textfont=dict(color="#0b1220", size=13, family="Arial Black"),
                             marker=dict(size=sizes, color=colors, line=dict(color="#e3f2fd", width=2),
                                         symbol="square"),
                             hovertext=hover, hoverinfo="text", showlegend=False))
    fig.update_layout(height=height, paper_bgcolor=BG, plot_bgcolor=BG, margin=dict(l=10, r=10, t=30, b=10),
                      xaxis=dict(visible=False), yaxis=dict(visible=False, scaleanchor="x", scaleratio=1),
                      legend=dict(orientation="h", y=-0.02, font=dict(color="#cfd8dc", size=11),
                                  bgcolor="rgba(0,0,0,0)"),
                      title=dict(text=f"{sample_id} · {g.graph.get('topology_type')} · SYNTHETIC",
                                 font=dict(color="#90a4ae", size=13), x=0.01))
    return fig
