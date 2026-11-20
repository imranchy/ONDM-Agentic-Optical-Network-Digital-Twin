"""Render white-background topology figures for the merged presentation (uses real dataset + tools).

Usage: .venv\\Scripts\\python docs\\presentation\\make_figures.py
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ondm import topology as topo  # noqa: E402
from ondm.agent import _trusted_failure, _trusted_k_paths, _without  # noqa: E402

OUT = Path(__file__).resolve().parent / "img"
NAVY, GREY, BLUE, GREEN, RED, ORANGE, GOLD = "#16364A", "#B0BEC5", "#1E88E5", "#2E7D32", "#D32F2F", "#EF6C00", "#F9A825"


def draw(sample, fname, paths=(), path_colors=(), failed=None, unusable=(), focus=(), legend=()):
    g = topo.build_graph(sample)
    pos = {n: (d["x"], -d["y"]) for n, d in g.nodes(data=True)}
    fig, ax = plt.subplots(figsize=(6.4, 5.2), dpi=200)
    unusable = {tuple(sorted(e)) for e in unusable}
    for u, v, d in g.edges(data=True):
        key = tuple(sorted((u, v)))
        (x0, y0), (x1, y1) = pos[u], pos[v]
        if failed and key == tuple(sorted(failed)):
            ax.plot([x0, x1], [y0, y1], color=RED, lw=3.5, ls=(0, (4, 2)), zorder=4.6)
            ax.text((x0 + x1) / 2, (y0 + y1) / 2, "✕", color=RED, fontsize=20, ha="center", va="center", zorder=6,
                    fontweight="bold")
        elif key in unusable:
            ax.plot([x0, x1], [y0, y1], color=ORANGE, lw=3, ls=":", zorder=2)
        else:
            ax.plot([x0, x1], [y0, y1], color=GREY, lw=1.6, zorder=1)
        ax.text((x0 + x1) / 2, (y0 + y1) / 2 + 18, f"{d['distance_km']:g} km", fontsize=6.5, color="#546E7A",
                ha="center", zorder=3, bbox=dict(fc="white", ec="none", pad=0.5, alpha=0.85))
    for i, (p, c) in enumerate(zip(paths, path_colors)):
        off = (i - (len(paths) - 1) / 2) * 14
        ax.plot([pos[n][0] + off for n in p], [pos[n][1] + off for n in p], color=c, lw=4.5, alpha=0.85, zorder=4,
                solid_capstyle="round")
    for n in g.nodes():
        c = GOLD if n in focus else BLUE
        ax.scatter(*pos[n], s=420, marker="s", color=c, edgecolors=NAVY, linewidths=1.2, zorder=5)
        ax.text(*pos[n], n, color="white" if n not in focus else NAVY, fontsize=10, fontweight="bold", ha="center",
                va="center", zorder=7)
    for label, color, style in legend:
        ax.plot([], [], color=color, lw=3.5, ls=style, label=label)
    if legend:
        ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.13), ncol=min(3, len(legend)), frameon=False, fontsize=8)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(OUT / fname, facecolor="white", bbox_inches="tight")
    plt.close(fig)


def main():
    OUT.mkdir(exist_ok=True)
    # BC1: topo_0013 A->G with inventory-unusable links excluded
    g13 = topo.build_graph("topo_0013")
    unusable13 = [["A", "B"], ["C", "D"]]
    p1 = _trusted_k_paths(_without(g13, {tuple(sorted(e)) for e in unusable13}), "A", "G", 3)
    draw("topo_0013", "bc1_provisioning.png", paths=p1, path_colors=[GREEN, "#7B1FA2"], unusable=unusable13,
         focus=("A", "G"), legend=[("Route 1: A-F-E-D-G (590 km)", GREEN, "-"),
                                   ("Route 2: A-L-F-E-D-G (1010 km)", "#7B1FA2", "-"),
                                   ("Unusable in NetBox", ORANGE, ":")])
    # BC2: topo_0023 failure H-J, longest restoration paths
    g23 = topo.build_graph("topo_0023")
    res = _trusted_failure(g23, "H", "J")
    rps = []
    for a in sorted(res["affected_pairs"], key=lambda a: -(a["restoration_km"] or 0)):
        if a["restoration_path"] and a["restoration_path"] not in rps:
            rps.append(a["restoration_path"])
    draw("topo_0023", "bc2_failure.png", paths=rps[:2], path_colors=[GREEN, "#7B1FA2"], failed=("H", "J"),
         legend=[("Failed link H-J", RED, (0, (4, 2))), (f"Restoration {'-'.join(rps[0])}", GREEN, "-"),
                 (f"Restoration {'-'.join(rps[1])}", "#7B1FA2", "-")])
    # BC3: topo_0013 ROADM D, farthest reachable site path
    draw("topo_0013", "bc3_troubleshooting.png", paths=[["D", "E", "F", "K"]], path_colors=[BLUE],
         unusable=unusable13, focus=("D",), legend=[("Farthest reachable: D-E-F-K (650 km)", BLUE, "-"),
                                                     ("Unusable in NetBox", ORANGE, ":")])
    print("figures written to", OUT)


if __name__ == "__main__":
    main()
