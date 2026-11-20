"""Scientific figures and contact sheets for a generated dataset (PNG + PDF).

Usage:
    python -m src.reporting.figures --data data/pilot/ONDM_pilot_125 --reports reports/pilot_125 \
        --out figures/pilot_125

Class names appear only in figure captions/axes OUTSIDE the individual diagrams (inspection use).
Class colours (validated categorical palette, every class also named on an axis) are used only
in these figures, never in dataset images.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from src.generation.taxonomy import CLASS_DISPLAY, CLASSES  # noqa: E402

COL = dict(zip(CLASSES, ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]))  # validated (dataviz)
INK, INK2, GRID, SURF = "#1f1f1e", "#52514e", "#e1e0d9", "#ffffff"
SHORT = {"long_haul_core": "Long-haul /\nCore", "metro_ring": "Metro\nring", "metro_aggregation": "Metro\naggregation",
         "dci": "DCI", "submarine": "Submarine"}

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9, "axes.titlesize": 10, "axes.labelsize": 9,
    "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.6, "axes.axisbelow": True, "savefig.dpi": 300, "figure.facecolor": SURF,
    "legend.frameon": False, "pdf.fonttype": 42,
})


def save(fig, out: Path, name: str) -> None:
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / f"{name}.png", bbox_inches="tight", dpi=200)
    fig.savefig(out / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)


def load(data: Path, reports: Path):
    rows = list(csv.DictReader(open(reports / "structural_statistics.csv", encoding="utf-8")))
    for r in rows:
        for k in ("n_nodes", "n_edges", "errors", "warnings", "inline_amplifiers", "equipment_items", "label_overlaps", "n_bridges", "cycle_rank"):
            r[k] = int(r[k])
        for k in ("mean_degree", "density", "mean_link_km", "max_link_km", "total_fiber_km", "extent_km", "frac_deg2"):
            r[k] = float(r[k])
    links = defaultdict(list)
    for r in rows:
        g = json.loads((data / "networks" / f"{r['scenario_id']}.graph.json").read_text(encoding="utf-8"))
        links[r["category"]] += [(e["length_km"], e["medium"]) for e in g["edges"]]
    eq = list(csv.reader(open(reports / "equipment_summary.csv", encoding="utf-8")))
    summary = json.loads((reports / "validation_summary.json").read_text(encoding="utf-8"))
    issues = list(csv.DictReader(open(reports / "validation_issues.csv", encoding="utf-8")))
    return rows, links, eq, summary, issues


def thumb(path: Path, w: int) -> np.ndarray:
    im = Image.open(path).convert("RGB")
    h = int(im.height * w / im.width)
    return np.asarray(im.resize((w, h), Image.LANCZOS))


def contact_sheet(data: Path, rows: list, out: Path, name: str, cols: int, title: str, tw: int, caption) -> None:
    n = len(rows)
    nr = int(np.ceil(n / cols))
    fig, axes = plt.subplots(nr, cols, figsize=(cols * 2.6, nr * 2.15 + 0.4))
    axes = np.atleast_1d(axes).ravel()
    for ax in axes:
        ax.axis("off")
    for ax, r in zip(axes, rows):
        ax.imshow(thumb(data / "networks" / f"{r['scenario_id']}.png", tw))
        ax.set_title(caption(r), fontsize=6.5, color=INK, pad=2)
        for s in ax.spines.values():
            s.set_visible(True); s.set_color(GRID)
    fig.suptitle(title, fontsize=11, color=INK, y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.985), h_pad=0.6, w_pad=0.3)
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / f"{name}.png", dpi=170, bbox_inches="tight")
    fig.savefig(out / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)


def box_strip(ax, rows, key, ylabel, log=False):
    data = [[r[key] for r in rows if r["category"] == c] for c in CLASSES]
    bp = ax.boxplot(data, widths=0.5, patch_artist=True, showfliers=False,
                    medianprops=dict(color=INK, lw=1.6), whiskerprops=dict(color=INK2), capprops=dict(color=INK2))
    for p, c in zip(bp["boxes"], CLASSES):
        p.set_facecolor(COL[c] + "40"); p.set_edgecolor(COL[c]); p.set_linewidth(1.2)
    rng = np.random.default_rng(0)
    for i, (d, c) in enumerate(zip(data, CLASSES), start=1):
        ax.scatter(i + rng.uniform(-0.15, 0.15, len(d)), d, s=12, color=COL[c], edgecolor="white", linewidth=0.5, zorder=3)
    ax.set_xticks(range(1, 6), [SHORT[c] for c in CLASSES])
    ax.set_ylabel(ylabel)
    if log:
        ax.set_yscale("log")
    ax.grid(axis="x", visible=False)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/pilot/ONDM_pilot_125")
    ap.add_argument("--reports", default="reports/pilot_125")
    ap.add_argument("--out", default="figures/pilot_125")
    a = ap.parse_args()
    data, reports, out = Path(a.data), Path(a.reports), Path(a.out)
    rows, links, eq, summary, issues = load(data, reports)
    rows.sort(key=lambda r: r["scenario_id"])
    N = len(rows)

    # 1-2. contact sheets
    contact_sheet(data, rows, out, "01_contact_sheet_all", 13, f"All {N} pilot diagrams (ID · class shown outside images for inspection only)", 360,
                  lambda r: f"{r['scenario_id'][-4:]} · {CLASS_DISPLAY[r['category']]}")
    for i, c in enumerate(CLASSES, start=2):
        sub = [r for r in rows if r["category"] == c]
        contact_sheet(data, sub, out, f"0{i}_contact_sheet_{c}", 5, f"{CLASS_DISPLAY[c]} — {len(sub)} networks", 520,
                      lambda r: f"{r['scenario_id']} · {r['family'].replace(r['category'] + '_', '').replace('_', ' ')} · N={r['n_nodes']}")

    # 3. representative figure: median-size scenario per class
    fig, axes = plt.subplots(2, 3, figsize=(15, 7.6))
    axes = axes.ravel()
    for ax, c in zip(axes, CLASSES):
        sub = sorted([r for r in rows if r["category"] == c and r["errors"] == 0], key=lambda r: r["n_nodes"])
        r = sub[len(sub) // 2]
        ax.imshow(Image.open(data / "networks" / f"{r['scenario_id']}.png").convert("RGB"))
        ax.set_title(f"{CLASS_DISPLAY[c]}  ({r['scenario_id']}, N={r['n_nodes']}, E={r['n_edges']})", fontsize=10)
        ax.axis("off")
    axes[-1].axis("off")
    axes[-1].text(0.02, 0.6, "One schematic per class (median node count).\nIdentical style, symbols, fonts and legend\nin every class; class names are never drawn\ninside dataset images.",
                  fontsize=10, color=INK2, va="center")
    fig.tight_layout()
    save(fig, out, "07_representative_per_class")

    # 4. category distribution
    fig, ax = plt.subplots(figsize=(6, 3.2))
    cnt = [sum(1 for r in rows if r["category"] == c) for c in CLASSES]
    bars = ax.bar(range(5), cnt, color=[COL[c] for c in CLASSES], width=0.6, edgecolor="white", linewidth=2)
    for b_, v in zip(bars, cnt):
        ax.text(b_.get_x() + b_.get_width() / 2, v + 0.4, str(v), ha="center", va="bottom", color=INK, fontsize=9)
    ax.set_xticks(range(5), [SHORT[c] for c in CLASSES]); ax.set_ylabel("Networks"); ax.set_ylim(0, max(cnt) * 1.18)
    ax.set_title(f"Category distribution (N = {N})"); ax.grid(axis="x", visible=False)
    save(fig, out, "08_category_distribution")

    # 5-6. node and link counts
    fig, axs = plt.subplots(1, 2, figsize=(10, 3.6))
    box_strip(axs[0], rows, "n_nodes", "Sites (nodes) per network"); axs[0].set_title("Node count per category")
    box_strip(axs[1], rows, "n_edges", "Fibre links (edges) per network"); axs[1].set_title("Link count per category")
    fig.tight_layout(); save(fig, out, "09_node_link_counts")

    # 7. fibre distance distribution (log x, per class, step histograms + per-medium)
    fig, axs = plt.subplots(1, 2, figsize=(11, 3.8), gridspec_kw={"width_ratios": [1.5, 1]})
    bins = np.logspace(np.log10(0.5), np.log10(12000), 40)
    for c in CLASSES:
        L = [x for x, _ in links[c]]
        axs[0].hist(L, bins=bins, histtype="step", lw=2, color=COL[c], label=f"{CLASS_DISPLAY[c]} (n={len(L)})")
    axs[0].set_xscale("log"); axs[0].set_xlabel("Fibre link length (km, log scale)"); axs[0].set_ylabel("Links")
    axs[0].legend(fontsize=7.5, loc="upper left"); axs[0].set_title("Fibre link length distribution")
    box_strip(axs[1], rows, "total_fiber_km", "Total fibre per network (km, log)", log=True)
    axs[1].set_title("Total fibre length per network")
    fig.tight_layout(); save(fig, out, "10_fiber_distance_distribution")

    # 8. equipment-type distribution (mean items per network, heatmap)
    head, body = eq[0][1:], eq[1:]
    M = np.array([[int(x) for x in row[1:]] for row in body], float)
    per = np.array([[sum(1 for r in rows if r["category"] == row[0])] for row in body], float)
    M = M / per
    order = np.argsort(-M.sum(0))
    M, head = M[:, order], [head[i] for i in order]
    fig, ax = plt.subplots(figsize=(12, 3.4))
    im = ax.imshow(np.log10(M + 1), cmap="Blues", aspect="auto")
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            v = M[i, j]
            ax.text(j, i, "–" if v == 0 else (f"{v:.0f}" if v >= 10 else f"{v:.1f}"), ha="center", va="center", fontsize=7.5,
                    color="white" if np.log10(v + 1) > 0.6 * np.log10(M.max() + 1) else INK)
    ax.set_xticks(range(len(head)), [h.replace("_", " ").lower() for h in head], rotation=35, ha="right", fontsize=7.5)
    ax.set_yticks(range(5), [CLASS_DISPLAY[r[0]] for r in body]); ax.grid(False)
    cb = fig.colorbar(im, ax=ax, fraction=0.02, pad=0.01); cb.set_label("log10(mean items + 1)", fontsize=7.5)
    ax.set_title("Equipment inventory: mean items per network (synthetic assignment)")
    fig.tight_layout(); save(fig, out, "11_equipment_distribution")

    # 9. structural diversity
    fig, axs = plt.subplots(1, 3, figsize=(14, 4))
    for c in CLASSES:
        sub = [r for r in rows if r["category"] == c]
        axs[0].scatter([r["extent_km"] for r in sub], [r["mean_degree"] for r in sub], s=26, color=COL[c],
                       edgecolor="white", linewidth=0.6, label=CLASS_DISPLAY[c])
        axs[1].scatter([r["mean_link_km"] for r in sub], [r["frac_deg2"] for r in sub], s=26, color=COL[c],
                       edgecolor="white", linewidth=0.6)
    axs[0].set_xscale("log"); axs[0].set_xlabel("Geographic extent (km, log)"); axs[0].set_ylabel("Mean node degree")
    axs[0].set_title("Scale vs connectivity"); axs[0].legend(fontsize=7, loc="upper left")
    axs[1].set_xscale("log"); axs[1].set_xlabel("Mean link length (km, log)"); axs[1].set_ylabel("Fraction of degree-2 sites")
    axs[1].set_title("Link scale vs ring-likeness")
    uniq = summary["unique_structures_by_category"]
    fams = Counter(r["category"] for r in rows)
    x = np.arange(5)
    axs[2].bar(x - 0.18, [fams[c] for c in CLASSES], 0.34, color="#d6d5cf", label="Networks", edgecolor="white")
    axs[2].bar(x + 0.18, [uniq[c] for c in CLASSES], 0.34, color=[COL[c] for c in CLASSES], label="Distinct unlabelled graph structures", edgecolor="white")
    for i, c in enumerate(CLASSES):
        axs[2].text(i + 0.18, uniq[c] + 0.3, str(uniq[c]), ha="center", fontsize=8, color=INK)
    axs[2].set_xticks(x, [SHORT[c] for c in CLASSES], fontsize=7.5); axs[2].set_ylabel("Count")
    axs[2].set_title("Structural uniqueness (WL hash)"); axs[2].legend(fontsize=7, loc="lower left"); axs[2].grid(axis="x", visible=False)
    fig.tight_layout(); save(fig, out, "12_structural_diversity")

    # 10. validation results
    fig, axs = plt.subplots(1, 2, figsize=(12, 3.9), gridspec_kw={"width_ratios": [1, 1.6]})
    st_order = [("PASS", "#1baf7a"), ("PASS_WITH_WARNINGS", "#eda100"), ("FAIL", "#e34948")]
    bottom = np.zeros(5)
    for st, col in st_order:
        v = np.array([sum(1 for r in rows if r["category"] == c and r["status"] == st) for c in CLASSES])
        axs[0].bar(range(5), v, bottom=bottom, color=col, width=0.6, edgecolor="white", linewidth=1.5,
                   label=st.replace("_", " ").lower())
        for i, (vv, bb) in enumerate(zip(v, bottom)):
            if vv:
                axs[0].text(i, bb + vv / 2, str(vv), ha="center", va="center", fontsize=8, color=INK)
        bottom += v
    axs[0].set_xticks(range(5), [SHORT[c] for c in CLASSES], fontsize=7.5); axs[0].set_ylabel("Networks")
    axs[0].set_title("Validation status per category"); axs[0].legend(fontsize=7, loc="lower right"); axs[0].grid(axis="x", visible=False)
    chk = Counter((i["check"], i["severity"]) for i in issues)
    checks = list(summary["issues_by_check"])
    y = np.arange(len(checks))
    left = np.zeros(len(checks))
    for sev, col in (("ERROR", "#e34948"), ("WARNING", "#eda100"), ("INFO", "#b7d3f6")):
        v = np.array([chk.get((k, sev), 0) for k in checks])
        axs[1].barh(y, v, left=left, color=col, label=sev.lower(), edgecolor="white", linewidth=1)
        left += v
    for i, t in enumerate(left):
        axs[1].text(t + 0.5, i, "0 issues" if t == 0 else str(int(t)), va="center", fontsize=6.5, color=INK2)
    axs[1].set_yticks(y, checks, fontsize=6.5); axs[1].invert_yaxis(); axs[1].set_xlabel("Issues raised (all scenarios)")
    axs[1].set_title(f"Automated checks ({len(checks)}): issues by check"); axs[1].legend(fontsize=7, loc="lower right")
    axs[1].grid(axis="y", visible=False)
    fig.tight_layout(); save(fig, out, "13_validation_results")
    print(f"figures -> {out}")


if __name__ == "__main__":
    main()
