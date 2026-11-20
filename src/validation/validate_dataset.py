"""Automated validation of a generated optical-network dataset.

Usage:
    python -m src.validation.validate_dataset --data data/pilot/ONDM_pilot_125 --out reports/pilot_125

Severity: ERROR = scenario fails; WARNING = legitimate-but-notable or needs human review;
INFO = recorded fact. Every check id is listed in CHECKS with whether it is automated.
Writes JSON/CSV/Markdown reports and updates each metadata file's "validation" block.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

import networkx as nx
import numpy as np
from PIL import Image

from src.generation.render import LEGEND_ENTRIES
from src.generation.taxonomy import CLASSES, LEAKAGE_TOKENS
from src.generation.topology_bench import haversine_km
from src.validation.label_rules import evaluate

CHECKS = {
    # id: (category, description)
    "S1_node_ids": ("structural", "node ids unique and well-formed (S\\d\\d)"),
    "S2_edge_endpoints": ("structural", "every edge endpoint is a defined node"),
    "S3_dup_edges": ("structural", "no duplicate edges or self-loops"),
    "S4_connected": ("structural", "graph connected, no isolated nodes"),
    "S5_counts": ("structural", "declared node/edge counts match lists"),
    "S6_class_structure": ("structural", "class-specific structural requirements"),
    "S7_duplicates": ("structural", "no isomorphic (role+medium labelled) duplicate graphs in dataset"),
    "S8_near_duplicate_images": ("structural", "no near-identical images (dHash Hamming <= 4)"),
    "E1_locations": ("equipment", "every equipment item references a valid node or edge"),
    "E2_switching": ("equipment", "ROADM/OADM equipment degree equals graph degree; one per site"),
    "E3_amplifiers": ("equipment", "ILA only on terrestrial links, repeaters only undersea; counts/positions consistent"),
    "E4_spans": ("equipment", "spans x span length = link length; span length <= declared maximum"),
    "E5_class_compat": ("equipment", "equipment types compatible with the network class"),
    "E6_terminals": ("equipment", "terminal-bearing sites have terminal equipment; BUs have none"),
    "E7_dci_reach": ("equipment", "400ZR pluggables only where DC-to-DC path <= declared reach"),
    "E8_attributes": ("equipment", "every equipment item carries type, location and assumption id"),
    "G1_latlon": ("geographic", "latitude/longitude within valid ranges"),
    "G2_length_ge_gc": ("geographic", "fibre length >= great-circle distance recomputed from coordinates"),
    "G3_route_factor": ("geographic", "fibre/great-circle ratio within [1.0, 2.0]"),
    "G4_scope": ("geographic", "geographic extent and link lengths plausible for the class"),
    "G5_provenance": ("geographic", "coordinate/length provenance recorded and consistent with class"),
    "D1_image": ("diagram", "image readable, expected size, not blank"),
    "D2_complete": ("diagram", "every node and edge drawn; drawn labels match graph JSON"),
    "D3_in_bounds": ("diagram", "all labels inside the drawing area"),
    "D4_font": ("diagram", "label font size >= 14 px (node) / 12 px (link) at native resolution"),
    "D5_overlap": ("diagram", "label overlaps (area > 15% of smaller label)"),
    "D6_leakage": ("diagram", "no category names / hints in drawn text or PNG metadata"),
    "D7_style": ("diagram", "identical style hash and legend in every image"),
    "D8_symbols": ("diagram", "drawn equipment line matches inventory"),
    "D9_amp_markers": ("diagram", "amplifier markers drawn = min(count, 5)"),
    "L1_rule": ("label", "assigned class satisfies its own evidence rule"),
    "L2_ambiguity": ("label", "no other class rule satisfied (else ambiguity warning)"),
    "L3_structural_cue": ("label", "structure-only cues pointing elsewhere (informative)"),
}

HUMAN_REVIEW = [
    "Engineering realism of each architecture template and of the equipment assignment (expert judgement).",
    "Visual legibility at the resolution a VLM actually receives (automated check uses native 1600x1200 px).",
    "Whether a human expert can identify the class from each diagram without metadata (blind review of contact sheets).",
    "Submarine synthetic coordinates may fall on land; not checked against coastlines (assumption A8).",
    "Whether Topology Bench networks selected as long-haul are optical core networks rather than IP-layer PoP maps.",
    "Overlap of link labels with amplifier markers or lines below the overlap threshold.",
]

ALLOWED_ROLES = {
    "long_haul_core": {"ROADM"},
    "metro_ring": {"HUB_ROADM", "OADM", "ROADM"},
    "metro_aggregation": {"HUB_ROADM", "ROADM", "CO"},
    "dci": {"DC", "ROADM"},
    "submarine": {"CLS", "BU", "POP_ROADM"},
}
FORBIDDEN_EQUIPMENT = {
    "long_haul_core": {"SLTE", "POWER_FEED_EQUIPMENT", "SUBMARINE_REPEATER", "BRANCHING_UNIT", "COHERENT_PLUGGABLE_400ZR"},
    "metro_ring": {"SLTE", "POWER_FEED_EQUIPMENT", "SUBMARINE_REPEATER", "BRANCHING_UNIT"},
    "metro_aggregation": {"SLTE", "POWER_FEED_EQUIPMENT", "SUBMARINE_REPEATER", "BRANCHING_UNIT"},
    "dci": {"SLTE", "POWER_FEED_EQUIPMENT", "SUBMARINE_REPEATER", "BRANCHING_UNIT"},
    "submarine": {"COHERENT_PLUGGABLE_400ZR", "COHERENT_TRANSPONDER_ZRPLUS"},
}
SCOPE = {  # (extent_km_min, extent_km_max, max_link_km) -- plausibility envelopes (assumptions)
    "long_haul_core": (800, 8000, 3000),
    "metro_ring": (0, 100, 60),
    "metro_aggregation": (0, 200, 80),
    "dci": (0, 1200, 900),
    "submarine": (50, 15000, 15000),
}


def dhash(path: Path, size: int = 16) -> int:
    im = Image.open(path).convert("L").resize((size + 1, size), Image.LANCZOS)
    a = np.asarray(im, dtype=np.int16)
    bits = (a[:, 1:] > a[:, :-1]).flatten()
    return int("".join("1" if b else "0" for b in bits), 2)


def overlap_frac(a, b) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    if w <= 0 or h <= 0:
        return 0.0
    small = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return w * h / small if small > 0 else 0.0


def tokens_hit(text: str) -> list[str]:
    t = text.lower()
    hits = []
    for tok in LEAKAGE_TOKENS:
        if re.search(r"(?<![a-z])" + re.escape(tok) + r"(?![a-z])", t):
            hits.append(tok)
    return hits


def validate_one(sid: str, d: Path, issues: list, record: dict) -> None:
    def add(check, sev, msg):
        issues.append({"scenario_id": sid, "check": check, "severity": sev, "message": msg})

    net = d / "networks"
    graph = json.loads((net / f"{sid}.graph.json").read_text(encoding="utf-8"))
    eq = json.loads((net / f"{sid}.equipment.json").read_text(encoding="utf-8"))
    meta = json.loads((net / f"{sid}.metadata.json").read_text(encoding="utf-8"))
    man = json.loads((d / "render_manifests" / f"{sid}.render.json").read_text(encoding="utf-8"))
    cls = meta["ground_truth"]["category"]
    record.update({"scenario_id": sid, "category": cls, "family": meta["generation_family"],
                   "group_key": meta["group_key"]})
    for name, obj in (("graph", graph), ("equipment", eq), ("metadata", meta), ("render", man)):
        if obj.get("scenario_id") != sid:
            add("S5_counts", "ERROR", f"{name} file scenario_id mismatch")

    # ---------------- structural
    ids = [n["id"] for n in graph["nodes"]]
    if len(set(ids)) != len(ids) or not all(re.fullmatch(r"S\d{2}", i) for i in ids):
        add("S1_node_ids", "ERROR", "duplicate or malformed node ids")
    idset = set(ids)
    pairs = []
    for e in graph["edges"]:
        if e["u"] not in idset or e["v"] not in idset:
            add("S2_edge_endpoints", "ERROR", f"edge {e['id']} has undefined endpoint")
        if e["u"] == e["v"]:
            add("S3_dup_edges", "ERROR", f"self-loop {e['id']}")
        pairs.append(frozenset((e["u"], e["v"])))
    if len(set(pairs)) != len(pairs):
        add("S3_dup_edges", "ERROR", "duplicate edges")
    g = nx.Graph()
    g.add_nodes_from(ids)
    g.add_edges_from((e["u"], e["v"]) for e in graph["edges"])
    if not nx.is_connected(g):
        add("S4_connected", "ERROR", f"{nx.number_connected_components(g)} components")
    if any(dd == 0 for _, dd in g.degree()):
        add("S4_connected", "ERROR", "isolated node(s)")
    if graph["node_count"] != len(ids) or graph["edge_count"] != len(graph["edges"]):
        add("S5_counts", "ERROR", "declared counts mismatch")
    roles = {n["id"]: n["role"] for n in graph["nodes"]}
    deg = dict(g.degree())
    bad_roles = set(roles.values()) - ALLOWED_ROLES[cls]
    if bad_roles:
        add("S6_class_structure", "ERROR", f"roles {sorted(bad_roles)} not allowed for {cls}")
    if cls == "metro_ring" and list(nx.bridges(g)):
        add("S6_class_structure", "ERROR", "ring network has bridge links (not every node protected)")
    if cls == "dci":
        weak = [v for v, r in roles.items() if r == "DC" and deg[v] < 2]
        if weak:
            add("S6_class_structure", "WARNING", f"DC sites without diverse links: {weak}")
    if cls == "submarine":
        for v, r in roles.items():
            if r == "BU" and deg[v] != 3:
                add("S6_class_structure", "ERROR", f"BU {v} degree {deg[v]} != 3")
    if cls == "long_haul_core":
        spurs = [v for v in ids if deg[v] == 1]
        if spurs:
            add("S6_class_structure", "INFO", f"{len(spurs)} degree-1 spur site(s) (present in published source topology)")
    if cls == "metro_aggregation":
        for v, r in roles.items():
            if r == "CO" and any(roles[w] == "CO" for w in g[v]):
                add("S6_class_structure", "ERROR", f"CO {v} connected to another CO")

    # ---------------- equipment
    edges = {e["id"]: e for e in graph["edges"]}
    items = eq["items"]
    by_node = defaultdict(list)
    by_edge = defaultdict(list)
    for it in items:
        if not it.get("type") or not it.get("location") or not it.get("assumption"):
            add("E8_attributes", "ERROR", f"{it.get('equipment_id')} missing type/location/assumption")
        loc = it.get("location", {})
        if "node" in loc:
            if loc["node"] not in idset:
                add("E1_locations", "ERROR", f"{it['equipment_id']} at unknown node")
            by_node[loc["node"]].append(it)
        elif "edge" in loc:
            if loc["edge"] not in edges:
                add("E1_locations", "ERROR", f"{it['equipment_id']} on unknown edge")
            else:
                by_edge[loc["edge"]].append(it)
        else:
            add("E1_locations", "ERROR", f"{it['equipment_id']} has no location")
    for v, r in roles.items():
        sw = [i for i in by_node[v] if i["type"] in ("ROADM", "OADM")]
        if r in ("ROADM", "HUB_ROADM", "POP_ROADM", "OADM"):
            if len(sw) != 1 or sw[0]["degree"] != deg[v]:
                add("E2_switching", "ERROR", f"{v}: switching equipment/degree mismatch")
            if r == "OADM" and deg[v] != 2:
                add("E2_switching", "ERROR", f"OADM {v} degree {deg[v]} != 2")
        elif sw:
            add("E2_switching", "ERROR", f"{v} ({r}) has switching equipment")
        terms = [i for i in by_node[v] if i["type"] in ("COHERENT_TRANSPONDER", "COHERENT_PLUGGABLE_400ZR", "COHERENT_TRANSPONDER_ZRPLUS", "SLTE")]
        if r == "BU" and by_node[v] and any(i["type"] != "BRANCHING_UNIT" for i in by_node[v]):
            add("E6_terminals", "ERROR", f"BU {v} carries non-BU equipment")
        if r != "BU" and not terms:
            add("E6_terminals", "ERROR", f"{v} ({r}) has no terminal equipment")
        if r == "DC":
            for i in terms:
                if i["type"] == "COHERENT_PLUGGABLE_400ZR" and i["max_dc_path_km"] > eq["parameters"]["dci_pluggable_reach_km"] + 1e-6:
                    add("E7_dci_reach", "ERROR", f"{v}: 400ZR beyond declared reach")
    smax_t = eq["parameters"]["terrestrial_max_span_km"]
    smax_s = eq["parameters"]["submarine_repeater_spacing_km"]
    for eid, e in edges.items():
        amps = by_edge[eid]
        types = {i["type"] for i in amps}
        if e["medium"] == "terrestrial" and types - {"ILA_EDFA"}:
            add("E3_amplifiers", "ERROR", f"{eid}: non-ILA equipment on terrestrial link")
        if e["medium"] == "submarine" and types - {"SUBMARINE_REPEATER"}:
            add("E3_amplifiers", "ERROR", f"{eid}: non-repeater equipment on undersea link")
        if len(amps) != e["n_inline_amplifiers"]:
            add("E3_amplifiers", "ERROR", f"{eid}: amplifier count mismatch")
        if any(not (0 < i["location"]["position_km_from_u"] < e["length_km"]) for i in amps):
            add("E3_amplifiers", "ERROR", f"{eid}: amplifier position outside link")
        if abs(e["n_spans"] * e["span_length_km"] - e["length_km"]) > 0.05 * e["n_spans"] + 0.01:
            add("E4_spans", "ERROR", f"{eid}: spans x span length != length")
        lim = smax_s if (e["medium"] == "submarine" and e["n_inline_amplifiers"]) else smax_t
        if e["medium"] == "submarine" and not e["n_inline_amplifiers"]:
            lim = eq["parameters"]["unrepeatered_max_km"]
        if e["span_length_km"] > lim + 0.01:
            add("E4_spans", "ERROR", f"{eid}: span {e['span_length_km']} km > declared max {lim}")
    present = {i["type"] for i in items}
    bad = present & FORBIDDEN_EQUIPMENT[cls]
    if bad:
        add("E5_class_compat", "ERROR", f"equipment {sorted(bad)} incompatible with {cls}")

    # ---------------- geographic
    pos = {n["id"]: (n["lat"], n["lon"]) for n in graph["nodes"]}
    for v, (la, lo) in pos.items():
        if not (-90 <= la <= 90 and -180 <= lo <= 180):
            add("G1_latlon", "ERROR", f"{v} invalid coordinates")
    ratios = []
    for e in graph["edges"]:
        gc = haversine_km(*pos[e["u"]], *pos[e["v"]])
        if e["length_km"] < gc * 0.999 - 0.01:
            add("G2_length_ge_gc", "ERROR", f"{e['id']}: fibre {e['length_km']} km < great-circle {gc:.1f} km")
        if gc > 0.5:
            r = e["length_km"] / gc
            ratios.append(r)
            if not (0.999 <= r <= 2.0):
                add("G3_route_factor", "WARNING", f"{e['id']}: fibre/great-circle ratio {r:.2f}")
    ext = meta["geography"]["geo_extent_km"]
    lo_, hi_, maxl = SCOPE[cls]
    if not (lo_ <= ext <= hi_):
        add("G4_scope", "WARNING", f"extent {ext:.0f} km outside plausibility envelope [{lo_}, {hi_}] for {cls}")
    if meta["network_size"]["link_km_max"] > maxl:
        add("G4_scope", "WARNING", f"max link {meta['network_size']['link_km_max']:.0f} km > {maxl} for {cls}")
    prov = meta["provenance"]
    if cls == "long_haul_core":
        if not prov["coordinates"].startswith("real_derived") or not prov.get("source_topology_id"):
            add("G5_provenance", "ERROR", "long-haul scenario lacks real-derived provenance")
    elif "synthetic" not in prov["coordinates"]:
        add("G5_provenance", "ERROR", "synthetic scenario not marked synthetic")

    # ---------------- diagram
    png = net / f"{sid}.png"
    try:
        im = Image.open(png)
        im.load()
        arr = np.asarray(im.convert("L"), dtype=np.float32)
        if list(im.size) != man["image_px"]:
            add("D1_image", "ERROR", f"image size {im.size} != manifest {man['image_px']}")
        ink = float((arr < 200).mean())
        if arr.std() < 5 or not (0.005 <= ink <= 0.5):
            add("D1_image", "ERROR", f"image blank or saturated (ink fraction {ink:.3f})")
        record["ink_fraction"] = round(ink, 4)
        meta_text = " ".join(f"{k}={v}" for k, v in (im.info or {}).items() if isinstance(v, str))
        if tokens_hit(meta_text):
            add("D6_leakage", "ERROR", f"PNG metadata contains {tokens_hit(meta_text)}")
    except Exception as ex:  # noqa: BLE001
        add("D1_image", "ERROR", f"image unreadable: {ex}")
    mn = {it["node_id"]: it for it in man["nodes"]}
    me = {it["edge_id"]: it for it in man["edges"]}
    for n in graph["nodes"]:
        if n["id"] not in mn:
            add("D2_complete", "ERROR", f"node {n['id']} not drawn")
        elif mn[n["id"]]["text"] != n["diagram_label"]:
            add("D2_complete", "ERROR", f"node {n['id']} drawn label != graph label")
    for e in graph["edges"]:
        if e["id"] not in me:
            add("D2_complete", "ERROR", f"edge {e['id']} not drawn")
        elif me[e["id"]]["text"] != e["diagram_label"]:
            add("D2_complete", "ERROR", f"edge {e['id']} drawn label != graph label")
        elif me[e["id"]]["amp_markers_drawn"] != min(e["n_inline_amplifiers"], 5):
            add("D9_amp_markers", "ERROR", f"edge {e['id']} amplifier markers mismatch")
        if e["id"] in me and me[e["id"]]["dashed"] != (e["medium"] == "submarine"):
            add("D2_complete", "ERROR", f"edge {e['id']} line style does not match medium")
    W, H = man["image_px"]
    pa = man["plot_area_px"]
    boxes = [(f"node {i['node_id']}", i["bbox_px"]) for i in man["nodes"]] + [(f"edge {i['edge_id']}", i["bbox_px"]) for i in man["edges"]]
    for name, b in boxes:
        if b[0] < pa[0] - 1 or b[1] < pa[1] - 1 or b[2] > pa[2] + 1 or b[3] > pa[3] + 1:
            add("D3_in_bounds", "ERROR", f"{name} label outside drawing area")
    if man["font_px"]["node"] < 14 or man["font_px"]["edge"] < 12:
        add("D4_font", "ERROR", f"font too small {man['font_px']}")
    n_ov = 0
    worst = 0.0
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            f = overlap_frac(boxes[i][1], boxes[j][1])
            if f > 0.15:
                n_ov += 1
                worst = max(worst, f)
    record["label_overlaps"] = n_ov
    if n_ov:
        add("D5_overlap", "WARNING", f"{n_ov} label pair(s) overlap > 15% (worst {worst:.0%})")
    drawn = [i["text"] for i in man["nodes"]] + [i["text"] for i in man["edges"]]
    leak = sorted({h for t in drawn for h in tokens_hit(t)})
    if leak:
        add("D6_leakage", "ERROR", f"drawn text contains category hint(s): {leak}")
    canonical = ["Legend"] + [lbl for *_, lbl in LEGEND_ENTRIES]
    if [x["text"] for x in man["legend"]] != canonical:
        add("D7_style", "ERROR", "legend differs from canonical legend")
    la_ = man["legend_area_px"]
    for x in man["legend"]:
        b = x["bbox_px"]
        if b[0] < la_[0] or b[2] > la_[2] or b[1] < la_[1] or b[3] > la_[3]:
            add("D3_in_bounds", "ERROR", f"legend text '{x['text']}' clipped")
    record["style_hash"] = man["style_hash"]
    for n in graph["nodes"]:
        line = n["diagram_label"].split("\n")[1]
        sw = [i for i in by_node[n["id"]] if i["type"] in ("ROADM", "OADM")]
        if "ROADM-" in line and (not sw or not line.endswith(f"-{sw[0]['degree']}D")):
            add("D8_symbols", "ERROR", f"{n['id']} drawn degree != inventory")
        m = re.search(r"×(\d+)$", line)
        if m:
            cnt = sum(i.get("count", 0) for i in by_node[n["id"]] if i["type"].startswith("COHERENT"))
            if int(m.group(1)) != cnt:
                add("D8_symbols", "ERROR", f"{n['id']} drawn terminal count != inventory")

    # ---------------- label
    lab = evaluate(graph, eq)
    record["rules_satisfied"] = ";".join(lab["satisfied"])
    record["structural_cues"] = ";".join(lab["structural_cues"])
    if not lab["rules"][cls]:
        add("L1_rule", "ERROR", f"assigned class {cls} does not satisfy its evidence rule")
    others = [c for c in lab["satisfied"] if c != cls]
    if others:
        add("L2_ambiguity", "WARNING", f"also satisfies rule(s) for {others} — AMBIGUOUS, needs review")
    for cue in lab["structural_cues"]:
        add("L3_structural_cue", "INFO", cue)
    f = lab["features"]
    record.update({"n_nodes": f["n"], "n_edges": graph["edge_count"], "mean_link_km": round(f["mean_link_km"], 1),
                   "max_link_km": round(f["max_link_km"], 1), "extent_km": round(f["extent_km"], 1),
                   "frac_deg2": round(f["frac_deg2"], 3), "n_bridges": f["n_bridges"],
                   "cycle_rank": f["n_cycles_basis"], "mean_degree": round(2 * graph["edge_count"] / f["n"], 3),
                   "density": round(nx.density(g), 4), "diameter_hops": nx.diameter(g) if nx.is_connected(g) else None,
                   "inline_amplifiers": sum(e["n_inline_amplifiers"] for e in graph["edges"]),
                   "total_fiber_km": meta["network_size"]["total_fiber_km"],
                   "median_route_factor": round(float(np.median(ratios)), 3) if ratios else None,
                   "equipment_items": len(items)})
    record["_equipment_types"] = Counter(i["type"] for i in items)
    record["_graph"] = g
    record["_roles"] = roles
    record["_media"] = {(e["u"], e["v"]): e["medium"] for e in graph["edges"]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/pilot/ONDM_pilot_125")
    ap.add_argument("--out", default="reports/pilot_125")
    ap.add_argument("--no-write-metadata", action="store_true")
    a = ap.parse_args()
    d, out = Path(a.data), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    sids = sorted(p.name[:-len(".graph.json")] for p in (d / "networks").glob("*.graph.json"))
    for ext in (".png", ".equipment.json", ".metadata.json"):
        missing = [s for s in sids if not (d / "networks" / f"{s}{ext}").exists()]
        if missing:
            raise SystemExit(f"missing {ext} for {missing[:5]}")
    issues, records = [], []
    for sid in sids:
        rec: dict = {}
        validate_one(sid, d, issues, rec)
        records.append(rec)

    # dataset-level: duplicates (isomorphism with role + medium labels)
    by_hash = defaultdict(list)
    for r in records:
        g = r["_graph"].copy()
        nx.set_node_attributes(g, r["_roles"], "role")
        nx.set_edge_attributes(g, {k: v for k, v in r["_media"].items()}, "medium")
        r["_lg"] = g
        by_hash[nx.weisfeiler_lehman_graph_hash(g, node_attr="role", edge_attr="medium", iterations=4)].append(r)
    dup_rows = []
    for h, group in by_hash.items():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                A, B = group[i], group[j]
                if nx.is_isomorphic(A["_lg"], B["_lg"], node_match=lambda x, y: x["role"] == y["role"],
                                    edge_match=lambda x, y: x["medium"] == y["medium"]):
                    dup_rows.append({"a": A["scenario_id"], "b": B["scenario_id"], "type": "isomorphic_labelled_graph",
                                     "category_a": A["category"], "category_b": B["category"]})
                    issues.append({"scenario_id": B["scenario_id"], "check": "S7_duplicates", "severity": "ERROR",
                                   "message": f"isomorphic to {A['scenario_id']}"})
    # unlabelled isomorphism (structure only) is reported as INFO
    plain = defaultdict(list)
    for r in records:
        plain[nx.weisfeiler_lehman_graph_hash(r["_graph"], iterations=4)].append(r)
    plain_dups = 0
    for group in plain.values():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                if nx.is_isomorphic(group[i]["_graph"], group[j]["_graph"]):
                    plain_dups += 1
                    dup_rows.append({"a": group[i]["scenario_id"], "b": group[j]["scenario_id"],
                                     "type": "isomorphic_unlabelled_structure_only",
                                     "category_a": group[i]["category"], "category_b": group[j]["category"]})
    # near-duplicate images
    hashes = {r["scenario_id"]: dhash(d / "networks" / f"{r['scenario_id']}.png") for r in records}
    sid_list = list(hashes)
    min_ham = {}
    for i, s in enumerate(sid_list):
        for t in sid_list[i + 1:]:
            hd = bin(hashes[s] ^ hashes[t]).count("1")
            min_ham[s] = min(min_ham.get(s, 999), hd)
            min_ham[t] = min(min_ham.get(t, 999), hd)
            if hd <= 4:
                dup_rows.append({"a": s, "b": t, "type": f"near_identical_image_dhash_{hd}", "category_a": "", "category_b": ""})
                issues.append({"scenario_id": t, "check": "S8_near_duplicate_images", "severity": "WARNING",
                               "message": f"dHash distance {hd} to {s}"})
    groups = Counter(r["group_key"] for r in records)
    for r in records:
        r["min_dhash_distance"] = min_ham.get(r["scenario_id"])
        if groups[r["group_key"]] > 1:
            issues.append({"scenario_id": r["scenario_id"], "check": "S7_duplicates", "severity": "INFO",
                           "message": f"group {r['group_key']} has {groups[r['group_key']]} members"})
    styles = Counter(r["style_hash"] for r in records)
    if len(styles) > 1:
        for r in records:
            issues.append({"scenario_id": r["scenario_id"], "check": "D7_style", "severity": "ERROR",
                           "message": f"style hashes differ across dataset: {dict(styles)}"})

    # ------------------------------------------------------------------ outputs
    sev = defaultdict(lambda: Counter())
    for i in issues:
        sev[i["scenario_id"]][i["severity"]] += 1
    for r in records:
        r["errors"] = sev[r["scenario_id"]]["ERROR"]
        r["warnings"] = sev[r["scenario_id"]]["WARNING"]
        r["status"] = "FAIL" if r["errors"] else ("PASS_WITH_WARNINGS" if r["warnings"] else "PASS")

    with open(out / "validation_issues.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["scenario_id", "check", "severity", "message"])
        w.writeheader(); w.writerows(issues)
    with open(out / "failed_scenarios.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["scenario_id", "check", "severity", "message"])
        w.writeheader(); w.writerows([i for i in issues if i["severity"] == "ERROR"])
    with open(out / "warnings.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["scenario_id", "check", "severity", "message"])
        w.writeheader(); w.writerows([i for i in issues if i["severity"] == "WARNING"])
    with open(out / "duplicate_report.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["a", "b", "type", "category_a", "category_b"])
        w.writeheader(); w.writerows(dup_rows)
    stat_keys = ["scenario_id", "category", "family", "group_key", "status", "errors", "warnings", "n_nodes", "n_edges",
                 "mean_degree", "density", "diameter_hops", "cycle_rank", "n_bridges", "frac_deg2", "mean_link_km",
                 "max_link_km", "total_fiber_km", "extent_km", "median_route_factor", "inline_amplifiers",
                 "equipment_items", "label_overlaps", "ink_fraction", "min_dhash_distance", "rules_satisfied", "structural_cues"]
    with open(out / "structural_statistics.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=stat_keys)
        w.writeheader(); w.writerows([{k: r.get(k) for k in stat_keys} for r in records])
    eq_types = sorted({t for r in records for t in r["_equipment_types"]})
    with open(out / "equipment_summary.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["category"] + eq_types)
        for c in CLASSES:
            tot = Counter()
            for r in records:
                if r["category"] == c:
                    tot.update(r["_equipment_types"])
            w.writerow([c] + [tot.get(t, 0) for t in eq_types])

    dist = Counter(r["category"] for r in records)
    by_check = defaultdict(Counter)
    for i in issues:
        by_check[i["check"]][i["severity"]] += 1

    def cls_stats(key):
        res = {}
        for c in CLASSES:
            v = [r[key] for r in records if r["category"] == c and r.get(key) is not None]
            res[c] = {"min": min(v), "median": float(np.median(v)), "max": max(v)} if v else None
        return res

    summary = {
        "dataset": str(d), "n_scenarios": len(records),
        "category_distribution": {c: dist.get(c, 0) for c in CLASSES},
        "status_counts": dict(Counter(r["status"] for r in records)),
        "status_by_category": {c: dict(Counter(r["status"] for r in records if r["category"] == c)) for c in CLASSES},
        "issues_by_check": {k: {"category": CHECKS[k][0], "description": CHECKS[k][1], **dict(by_check.get(k, {}))} for k in CHECKS},
        "duplicates": {"isomorphic_labelled_pairs": sum(1 for x in dup_rows if x["type"] == "isomorphic_labelled_graph"),
                       "isomorphic_structure_only_pairs": plain_dups,
                       "near_identical_image_pairs": sum(1 for x in dup_rows if x["type"].startswith("near_identical")),
                       "min_dhash_distance_overall": min(min_ham.values()) if min_ham else None},
        "ambiguity_warnings": sum(1 for i in issues if i["check"] == "L2_ambiguity"),
        "structural_cues": dict(Counter(c for r in records for c in r["structural_cues"].split(";") if c)),
        "structure_by_category": {k: cls_stats(k) for k in ("n_nodes", "n_edges", "mean_degree", "mean_link_km", "extent_km", "inline_amplifiers", "label_overlaps")},
        "unique_structures_by_category": {c: len({nx.weisfeiler_lehman_graph_hash(r["_graph"], iterations=4) for r in records if r["category"] == c}) for c in CLASSES},
        "families": dict(Counter(r["family"] for r in records)),
        "style_hashes": dict(styles),
        "automated_checks": {k: v[1] for k, v in CHECKS.items()},
        "requires_human_review": HUMAN_REVIEW,
    }
    (out / "validation_summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    with open(out / "category_distribution.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["category", "count"])
        for c in CLASSES:
            w.writerow([c, dist.get(c, 0)])

    if not a.no_write_metadata:
        per = defaultdict(list)
        for i in issues:
            per[i["scenario_id"]].append(i)
        for r in records:
            p = d / "networks" / f"{r['scenario_id']}.metadata.json"
            meta = json.loads(p.read_text(encoding="utf-8"))
            meta["validation"] = {"status": r["status"], "errors": r["errors"], "warnings": r["warnings"],
                                  "rules_satisfied": r["rules_satisfied"].split(";") if r["rules_satisfied"] else [],
                                  "ambiguous": any(i["check"] == "L2_ambiguity" for i in per[r["scenario_id"]]),
                                  "structural_cues": r["structural_cues"].split(";") if r["structural_cues"] else [],
                                  "issues": [{k: i[k] for k in ("check", "severity", "message")} for i in per[r["scenario_id"]]],
                                  "validator": "src/validation/validate_dataset.py", "human_review": "pending"}
            p.write_text(json.dumps(meta, indent=1), encoding="utf-8")

    print(json.dumps({k: summary[k] for k in ("n_scenarios", "category_distribution", "status_counts", "duplicates", "ambiguity_warnings", "structural_cues")}, indent=1))
    for k, v in summary["issues_by_check"].items():
        cnt = {s: v.get(s, 0) for s in ("ERROR", "WARNING", "INFO") if v.get(s)}
        if cnt:
            print(f"  {k:26s} {cnt}")


if __name__ == "__main__":
    main()
