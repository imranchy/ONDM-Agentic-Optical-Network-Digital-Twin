"""Independent rule-based check of the class label from drawn evidence (graph + equipment only).

Implemented separately from the generator: it never reads the generation family or the label
when evaluating the rules. See docs/TAXONOMY.md "Classification rules used by the validator".
"""
from __future__ import annotations

import networkx as nx

from src.generation.topology_bench import haversine_km

R = {"ROADM": "ROADM", "HUB": "HUB_ROADM", "OADM": "OADM", "CO": "CO", "DC": "DC", "CLS": "CLS",
     "BU": "BU", "POP": "POP_ROADM"}


def features(graph: dict, equipment: dict) -> dict:
    g = nx.Graph()
    for n in graph["nodes"]:
        g.add_node(n["id"], role=n["role"])
    for e in graph["edges"]:
        g.add_edge(e["u"], e["v"], length=e["length_km"], medium=e["medium"])
    roles = [n["role"] for n in graph["nodes"]]
    cnt = {r: roles.count(r) for r in set(roles)}
    lengths = [e["length_km"] for e in graph["edges"]]
    deg = dict(g.degree())
    n = g.number_of_nodes()
    nodes = graph["nodes"]
    extent = max((haversine_km(a["lat"], a["lon"], b["lat"], b["lon"]) for i, a in enumerate(nodes) for b in nodes[i + 1:]), default=0)
    bridges = list(nx.bridges(g)) if n > 1 else []
    ilas = sum(e["n_inline_amplifiers"] for e in graph["edges"] if e["medium"] == "terrestrial")
    return {
        "n": n, "roles": cnt,
        "n_sub_edges": sum(1 for e in graph["edges"] if e["medium"] == "submarine"),
        "mean_link_km": sum(lengths) / len(lengths), "max_link_km": max(lengths),
        "extent_km": extent,
        "frac_deg2": sum(1 for v in deg.values() if v == 2) / n,
        "two_edge_connected": len(bridges) == 0,
        "n_bridges": len(bridges),
        "n_cycles_basis": len(nx.cycle_basis(g)),
        "is_tree": nx.is_tree(g),
        "terrestrial_ilas": ilas,
        "terminal_bearing": sum(v for r, v in cnt.items() if r != R["BU"]),
    }


def evaluate(graph: dict, equipment: dict) -> dict:
    f = features(graph, equipment)
    c = f["roles"]
    has = lambda r: c.get(r, 0) > 0  # noqa: E731
    no_special = not (has("DC") or has("CLS") or has("BU"))
    rules = {
        "submarine": c.get("CLS", 0) >= 2 and f["n_sub_edges"] >= 1,
        "dci": c.get("DC", 0) >= 2 and c.get("DC", 0) >= 0.5 * f["terminal_bearing"] and f["n_sub_edges"] == 0,
        "metro_ring": no_special and not has("CO") and f["two_edge_connected"] and f["frac_deg2"] >= 0.6
                      and f["max_link_km"] <= 100,
        "metro_aggregation": no_special and has("HUB_ROADM") and has("ROADM") and c.get("CO", 0) >= 4
                             and f["max_link_km"] <= 100,
        "long_haul_core": set(c) <= {"ROADM"} and (f["mean_link_km"] >= 150 or f["extent_km"] >= 800)
                          and f["terrestrial_ilas"] > 0,
    }
    # structure-only cues: what graph shape alone would suggest (informative warnings)
    struct = []
    if f["frac_deg2"] >= 0.6 and f["n_cycles_basis"] <= 2 and not rules["metro_ring"]:
        struct.append("structure_ring_like")
    if f["is_tree"]:
        struct.append("structure_tree")
    if f["mean_link_km"] >= 250 and not rules["long_haul_core"]:
        struct.append("long_links_like_long_haul")
    if rules["metro_aggregation"]:
        # aggregation tier forming a single ring
        role_of = {n["id"]: n["role"] for n in graph["nodes"]}
        sub = nx.Graph([(e["u"], e["v"]) for e in graph["edges"] if role_of[e["u"]] == role_of[e["v"]] == "ROADM"])
        if sub.number_of_nodes() >= 3 and all(d == 2 for _, d in sub.degree()) and nx.is_connected(sub):
            struct.append("distribution_tier_is_ring")
    if rules["long_haul_core"] and f["extent_km"] < 800:
        struct.append("small_extent_for_long_haul")
    return {"rules": rules, "satisfied": [k for k, v in rules.items() if v], "structural_cues": struct, "features": f}
