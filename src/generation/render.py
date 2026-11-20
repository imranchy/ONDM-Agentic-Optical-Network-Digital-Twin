"""Uniform engineering-schematic renderer.

One style for all classes (no class-specific colours, backgrounds or legends). Node positions
come from (real or synthetic) coordinates projected equirectangularly, stretched to fill the
drawing area (bounded aspect distortion) and de-overlapped, so the drawing is a geo-schematic,
not a map: there is no background imagery or coastline and distances are given by the labels.

Labels are placed greedily among candidate positions to minimise overlap with other labels,
node symbols and link lines. The renderer returns a *render manifest* with the pixel bounding
boxes of every drawn node, link label and legend text; the validator uses it to check
completeness, legibility and label leakage.
"""
from __future__ import annotations

import hashlib
import json
import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from .taxonomy import (  # noqa: E402
    MEDIUM_SUBMARINE, ROLE_BU, ROLE_CLS, ROLE_CO, ROLE_DC, ROLE_HUB_ROADM, ROLE_OADM, ROLE_POP,
    ROLE_ROADM,
)

STYLE = {
    "version": 2,
    "fig_w_in": 10.0, "fig_h_in": 7.5, "dpi": 160,
    "font_family": "DejaVu Sans",
    "node_label_pt": 8.0, "edge_label_pt": 7.0, "legend_pt": 7.5, "legend_title_pt": 8.5,
    "line_color": "#2b2b2b", "line_width": 1.5, "submarine_dash": [5, 3],
    "node_face": "#ffffff", "node_edge": "#111111", "node_edge_width": 1.6,
    "marker_size": 13, "bu_marker_size": 7, "amp_marker_size": 5.5, "max_amp_markers": 5,
    "label_box_alpha": 0.9,
    "plot_box": [0.005, 0.01, 0.785, 0.98], "legend_box": [0.80, 0.02, 0.19, 0.96],
    "min_node_sep": 0.085, "max_aspect_stretch": 2.5, "layout_margin": 0.08,
}
STYLE_HASH = hashlib.sha256(json.dumps(STYLE, sort_keys=True).encode()).hexdigest()[:16]

MARKERS = {
    ROLE_ROADM: ("s", STYLE["marker_size"], STYLE["node_face"]),
    ROLE_HUB_ROADM: ("s", STYLE["marker_size"], STYLE["node_face"]),
    ROLE_POP: ("s", STYLE["marker_size"], STYLE["node_face"]),
    ROLE_OADM: ("D", STYLE["marker_size"] * 0.85, STYLE["node_face"]),
    ROLE_CO: ("o", STYLE["marker_size"] * 0.9, STYLE["node_face"]),
    ROLE_DC: ("h", STYLE["marker_size"] * 1.1, STYLE["node_face"]),
    ROLE_CLS: ("p", STYLE["marker_size"] * 1.1, STYLE["node_face"]),
    ROLE_BU: ("o", STYLE["bu_marker_size"], STYLE["node_edge"]),
}

LEGEND_ENTRIES = [  # identical in every image
    ("marker", ROLE_ROADM, "ROADM (n-degree)"),
    ("marker", ROLE_OADM, "OADM add/drop"),
    ("marker", ROLE_CO, "Central office (CO)"),
    ("marker", ROLE_DC, "Data centre (DC)"),
    ("marker", ROLE_CLS, "Cable landing (CLS)"),
    ("marker", ROLE_BU, "Branching unit (BU)"),
    ("line", "terrestrial", "Terrestrial fibre"),
    ("line", "submarine", "Undersea cable"),
    ("amp", None, "Amplifier ILA / RPT"),
    ("text", None, "TRM: transponder"),
    ("text", None, "ZR: 400ZR pluggable"),
    ("text", None, "TRP: ZR+ transponder"),
    ("text", None, "SLTE: line terminal"),
    ("text", None, "Link: km · amplifiers"),
]


def node_text(n: dict) -> str:
    role, d, ts = n["role"], n["degree"], n.get("terminal_summary")
    if role == ROLE_ROADM:
        eq = f"ROADM-{d}D"
    elif role == ROLE_HUB_ROADM:
        eq = f"HUB ROADM-{d}D"
    elif role == ROLE_POP:
        eq = f"POP ROADM-{d}D"
    elif role == ROLE_OADM:
        eq = "OADM"
    elif role == ROLE_CO:
        eq = f"CO TRM×{ts['count']}"
    elif role == ROLE_DC:
        eq = f"DC {ts['short']}×{ts['count']}"
    elif role == ROLE_CLS:
        eq = "CLS SLTE"
    else:
        eq = "BU"
    return f"{n['id']}\n{eq}"


def edge_text(e: dict) -> str:
    L = e["length_km"]
    km = f"{L:.0f} km" if L >= 10 else f"{L:.1f} km"
    n = e["n_inline_amplifiers"]
    if not n:
        return km
    return f"{km} · {n} {'RPT' if e['medium'] == MEDIUM_SUBMARINE else 'ILA'}"


def layout(nodes: list[dict]) -> dict[str, np.ndarray]:
    lat = np.array([n["lat"] for n in nodes], float)
    lon = np.array([n["lon"] for n in nodes], float)
    lon = (lon - lon[0] + 180) % 360 - 180  # unwrap around the first node (antimeridian-safe)
    x = lon * math.cos(math.radians(float(np.clip(lat.mean(), -70, 70))))
    xy = np.stack([x, lat.copy()], 1)
    xy -= xy.min(0)
    ext = np.maximum(xy.max(0), 1e-9)
    # stretch each axis to fill, but bound the distortion between axes
    s = 1.0 / ext
    s_max = s.min() * STYLE["max_aspect_stretch"]
    s = np.minimum(s, s_max)
    xy *= s
    used = xy.max(0)
    m = STYLE["layout_margin"]
    xy = m + xy * (1 - 2 * m) + (1 - 2 * m) * (1 - used) / 2
    d0 = STYLE["min_node_sep"]
    for _ in range(400):
        moved = False
        for i in range(len(xy)):
            diff = xy[i] - xy
            dist = np.hypot(diff[:, 0], diff[:, 1])
            dist[i] = np.inf
            for j in np.where(dist < d0)[0]:
                if dist[j] < 1e-9:
                    diff[j] = np.array([1e-3 * (j - i + 0.5), 1e-3])
                    dist[j] = np.hypot(*diff[j])
                push = (d0 - dist[j]) / 2 * diff[j] / dist[j]
                xy[i] += push
                xy[j] -= push
                moved = True
        xy = np.clip(xy, 0.04, 0.96)
        if not moved:
            break
    return {n["id"]: xy[k] for k, n in enumerate(nodes)}


# ------------------------------------------------------------------------------------------
# label placement helpers (display / pixel coordinates, origin bottom-left)
# ------------------------------------------------------------------------------------------
def _overlap(a, b) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return w * h if w > 0 and h > 0 else 0.0


def _seg_hits_rect(p, q, r) -> bool:
    """Liang-Barsky segment/rectangle intersection; r = (x0, y0, x1, y1)."""
    x0, y0 = p
    dx, dy = q[0] - p[0], q[1] - p[1]
    t0, t1 = 0.0, 1.0
    for pp, qq in ((-dx, x0 - r[0]), (dx, r[2] - x0), (-dy, y0 - r[1]), (dy, r[3] - y0)):
        if pp == 0:
            if qq < 0:
                return False
        else:
            t = qq / pp
            if pp < 0:
                t0 = max(t0, t)
            else:
                t1 = min(t1, t)
            if t0 > t1:
                return False
    return True


def _bb(artist, renderer):
    b = artist.get_window_extent(renderer=renderer)
    return (b.x0, b.y0, b.x1, b.y1)


def _score(bb, placed, markers, segments, skip_seg, area):
    s = 0.0
    if bb[0] < area[0] or bb[1] < area[1] or bb[2] > area[2] or bb[3] > area[3]:
        s += 1e6
    s += 4.0 * sum(_overlap(bb, o) for o in placed)
    s += 6.0 * sum(_overlap(bb, o) for o in markers)
    hits = sum(1 for k, (p, q) in enumerate(segments) if k not in skip_seg and _seg_hits_rect(p, q, bb))
    return s + 400.0 * hits


def _bbox_px(artist, renderer, H: float) -> list[float]:
    bb = artist.get_window_extent(renderer=renderer)
    return [round(bb.x0, 1), round(H - bb.y1, 1), round(bb.x1, 1), round(H - bb.y0, 1)]


def render(sc: dict, out_png: str) -> dict:
    plt.rcParams["font.family"] = STYLE["font_family"]
    fig = plt.figure(figsize=(STYLE["fig_w_in"], STYLE["fig_h_in"]), dpi=STYLE["dpi"])
    fig.patch.set_facecolor("white")
    ax = fig.add_axes(STYLE["plot_box"])
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    pos = layout(sc["nodes"])
    nodes = {n["id"]: n for n in sc["nodes"]}
    renderer = fig.canvas.get_renderer()
    W, H = fig.canvas.get_width_height()
    to_px = ax.transData.transform
    pbox = ax.get_window_extent(renderer)
    area = (pbox.x0 + 2, pbox.y0 + 2, pbox.x1 - 2, pbox.y1 - 2)

    segments, edge_items = [], []
    for e in sc["edges"]:
        a, b = pos[e["u"]], pos[e["v"]]
        ls = (0, STYLE["submarine_dash"]) if e["medium"] == MEDIUM_SUBMARINE else "solid"
        ax.plot([a[0], b[0]], [a[1], b[1]], color=STYLE["line_color"], lw=STYLE["line_width"],
                linestyle=ls, zorder=1, solid_capstyle="round")
        pa, pb = to_px(a), to_px(b)
        segments.append((tuple(pa), tuple(pb)))
        m = min(e["n_inline_amplifiers"], STYLE["max_amp_markers"])
        ang = math.degrees(math.atan2(pb[1] - pa[1], pb[0] - pa[0])) - 90
        for k in range(m):
            f = 0.3 + 0.4 * (k + 1) / (m + 1)
            p = a + f * (b - a)
            ax.plot(p[0], p[1], marker=(3, 0, ang), ms=STYLE["amp_marker_size"], color=STYLE["node_edge"],
                    zorder=2, markeredgewidth=0)
        edge_items.append({"edge_id": e["id"], "u": e["u"], "v": e["v"], "text": edge_text(e),
                           "amp_markers_drawn": m, "dashed": e["medium"] == MEDIUM_SUBMARINE})

    markers, node_items = [], []
    for nid, p in pos.items():
        n = nodes[nid]
        mk, ms, fc = MARKERS[n["role"]]
        ax.plot(p[0], p[1], marker=mk, ms=ms, mfc=fc, mec=STYLE["node_edge"],
                mew=STYLE["node_edge_width"], zorder=5, linestyle="none")
        c = to_px(p)
        r = ms * STYLE["dpi"] / 72 / 2 + 2
        markers.append((c[0] - r, c[1] - r, c[0] + r, c[1] + r))

    placed = []
    # node labels: 16 candidates (8 directions x 2 distances), offset in points
    dirs = [(0, -1), (0, 1), (1, 0), (-1, 0), (1, -1), (-1, -1), (1, 1), (-1, 1)]
    for nid, p in pos.items():
        n = nodes[nid]
        t = ax.annotate(node_text(n), xy=p, xytext=(0, 0), textcoords="offset points",
                        fontsize=STYLE["node_label_pt"], zorder=6, linespacing=1.05, color="#000000",
                        bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none", alpha=STYLE["label_box_alpha"]))
        best = None
        for dist in (11, 20):
            for dx, dy in dirs:
                ha = "left" if dx > 0 else ("right" if dx < 0 else "center")
                va = "bottom" if dy > 0 else ("top" if dy < 0 else "center")
                t.xyann = (dx * dist, dy * dist)
                t.set_ha(ha); t.set_va(va)
                bb = _bb(t, renderer)
                own = [k for k, mk_ in enumerate(markers) if list(pos).index(nid) == k]
                sc_ = _score(bb, placed, [mk_ for k, mk_ in enumerate(markers) if k not in own], segments, set(), area)
                if best is None or sc_ < best[0]:
                    best = (sc_, (dx * dist, dy * dist), ha, va, bb)
            if best[0] == 0:
                break
        t.xyann = best[1]; t.set_ha(best[2]); t.set_va(best[3])
        placed.append(best[4])
        node_items.append({"node_id": nid, "role": n["role"], "xy_axes": [round(float(p[0]), 4), round(float(p[1]), 4)],
                           "text": node_text(n), "artist": t, "placement_score": round(best[0], 1)})

    # link labels: positions along the link, both sides
    for k, (e, it) in enumerate(zip(sc["edges"], edge_items)):
        a, b = pos[e["u"]], pos[e["v"]]
        d = b - a
        nrm = np.array([-d[1], d[0]]) / (np.hypot(*d) + 1e-9)
        t = ax.text(0, 0, it["text"], fontsize=STYLE["edge_label_pt"], ha="center", va="center", zorder=4,
                    color="#111111",
                    bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=STYLE["label_box_alpha"]))
        best = None
        for f in (0.5, 0.4, 0.6, 0.3, 0.7, 0.22, 0.78):
            for side in (0, 1, -1, 2, -2):
                q = a + f * d + side * 0.016 * nrm
                t.set_position((q[0], q[1]))
                bb = _bb(t, renderer)
                sc_ = _score(bb, placed, markers, segments, {k}, area)
                if best is None or sc_ < best[0]:
                    best = (sc_, (q[0], q[1]), bb)
            if best[0] == 0:
                break
        t.set_position(best[1])
        placed.append(best[2])
        it["artist"] = t
        it["placement_score"] = round(best[0], 1)

    # fixed legend
    lax = fig.add_axes(STYLE["legend_box"])
    lax.set_xlim(0, 1); lax.set_ylim(0, 1); lax.axis("off")
    lax.add_patch(plt.Rectangle((0.0, 0.0), 1, 1, fill=False, ec="#888888", lw=0.8))
    legend_texts = [lax.text(0.06, 0.975, "Legend", fontsize=STYLE["legend_title_pt"], weight="bold", va="top")]
    y = 0.915
    for kind, key, label in LEGEND_ENTRIES:
        if kind == "marker":
            mk, ms, fc = MARKERS[key]
            lax.plot(0.13, y, marker=mk, ms=ms * 0.8, mfc=fc, mec=STYLE["node_edge"], mew=1.3, linestyle="none")
        elif kind == "line":
            ls = (0, STYLE["submarine_dash"]) if key == "submarine" else "solid"
            lax.plot([0.05, 0.21], [y, y], color=STYLE["line_color"], lw=STYLE["line_width"], linestyle=ls)
        elif kind == "amp":
            lax.plot([0.05, 0.21], [y, y], color=STYLE["line_color"], lw=STYLE["line_width"])
            lax.plot(0.13, y, marker=(3, 0, -90), ms=STYLE["amp_marker_size"], color=STYLE["node_edge"], markeredgewidth=0)
        x0 = 0.06 if kind == "text" else 0.27
        legend_texts.append(lax.text(x0, y, label, fontsize=STYLE["legend_pt"], va="center"))
        y -= 0.064

    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for it in node_items + edge_items:
        it["bbox_px"] = _bbox_px(it.pop("artist"), renderer, H)
    legend = [{"text": t.get_text(), "bbox_px": _bbox_px(t, renderer, H)} for t in legend_texts]
    lb = lax.get_window_extent(renderer)
    fig.savefig(out_png, dpi=STYLE["dpi"], facecolor="white", metadata={"Software": None})
    plt.close(fig)
    return {
        "image_px": [W, H], "style_hash": STYLE_HASH,
        "font_px": {"node": STYLE["node_label_pt"] * STYLE["dpi"] / 72, "edge": STYLE["edge_label_pt"] * STYLE["dpi"] / 72,
                    "legend": STYLE["legend_pt"] * STYLE["dpi"] / 72},
        "plot_area_px": [round(pbox.x0, 1), round(H - pbox.y1, 1), round(pbox.x1, 1), round(H - pbox.y0, 1)],
        "legend_area_px": [round(lb.x0, 1), round(H - lb.y1, 1), round(lb.x1, 1), round(H - lb.y0, 1)],
        "nodes": node_items, "edges": edge_items, "legend": legend,
    }
