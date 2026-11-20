"""Generate a balanced optical-network scenario dataset (pilot: 125 = 5 x 25).

Usage:
    python -m src.generation.generate_dataset --config configs/pilot_125.json

Per network writes (matching ids):
    networks/network_NNNN.png            engineering schematic (model input)
    networks/network_NNNN.graph.json     sites, links, link attributes (no class label)
    networks/network_NNNN.equipment.json equipment inventory + assumptions
    networks/network_NNNN.metadata.json  ground truth, provenance, seed, geography, validation
    render_manifests/network_NNNN.render.json   drawn-element bounding boxes (validation aid only)
plus manifest.csv, generation_config.json and generation_log.json.

Scenario ids are assigned after a seeded global shuffle so that ids carry no class information.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
import networkx as nx
import numpy as np

from . import scenarios as S
from .render import STYLE_HASH, render
from .taxonomy import ASSUMPTIONS, CLASS_DISPLAY, CLASSES
from .topology_bench import haversine_km


def scenario_seed(master: int, cls_idx: int, k: int, attempt: int = 0) -> int:
    ss = np.random.SeedSequence([master, cls_idx, k, attempt])
    return int(ss.generate_state(1, dtype=np.uint32)[0])


def structural_signature(sc: dict) -> str:
    g = nx.Graph()
    for n in sc["nodes"]:
        g.add_node(n["id"], role=n["role"])
    for e in sc["edges"]:
        g.add_edge(e["u"], e["v"], medium=e["medium"])
    return nx.weisfeiler_lehman_graph_hash(g, node_attr="role", edge_attr="medium", iterations=4)


def anchor_cities(catalog: dict) -> list[dict]:
    seen, out = set(), []
    for t in catalog["topologies"]:
        for n in t["nodes"]:
            if not n["name"]:
                continue
            key = (n["name"].strip().lower(), round(n["lat"], 1), round(n["lon"], 1))
            if key in seen:
                continue
            seen.add(key)
            out.append({"name": n["name"].strip(), "country": n["country"], "lat": n["lat"], "lon": n["lon"],
                        "source_topology": f"TB_{t['tb_index']:03d}_{t['name']}"})
    return out


def git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None


def geo_extent(nodes: list[dict]) -> float:
    return max((haversine_km(a["lat"], a["lon"], b["lat"], b["lon"]) for i, a in enumerate(nodes) for b in nodes[i + 1:]), default=0.0)


def build_one(cls: str, k: int, cfg: dict, catalog: dict, lh_sources: list[dict], anchors: list[dict],
              anchor_order: dict, seen: set) -> tuple[dict, int]:
    ci = CLASSES.index(cls)
    common = cfg["common"]
    for attempt in range(60):
        seed = scenario_seed(cfg["master_seed"], ci, k, attempt)
        rng = np.random.default_rng(seed)
        if cls == "long_haul_core":
            sc = S.build_long_haul(lh_sources[k], rng, cfg[cls])
        elif cls == "submarine":
            sc = S.build_submarine(rng, cfg[cls], common)
        else:
            anchor = anchors[anchor_order[cls][(k + attempt) % len(anchors)]]
            if cls == "metro_ring":
                sc = S.build_metro_ring(anchor, rng, cfg[cls], common)
            elif cls == "metro_aggregation":
                sc = S.build_metro_aggregation(anchor, rng, cfg[cls], common)
            else:
                sc = S.build_dci(anchor, rng, cfg[cls], common, anchors)
        sc = S.finalise(sc, rng, common)
        g = nx.Graph([(e["u"], e["v"]) for e in sc["edges"]])
        g.add_nodes_from(n["id"] for n in sc["nodes"])
        if not nx.is_connected(g):
            continue
        sig = structural_signature(sc)
        # long-haul sources are distinct published graphs; synthetic graphs must be structurally new
        if cls != "long_haul_core" and sig in seen:
            continue
        seen.add(sig)
        sc["structural_signature_wl"] = sig
        sc["generation_attempt"] = attempt
        return sc, seed
    raise RuntimeError(f"could not generate a unique {cls} scenario #{k}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/pilot_125.json")
    ap.add_argument("--clean", action="store_true", help="delete the output dir first")
    a = ap.parse_args()
    cfg_text = Path(a.config).read_text(encoding="utf-8")
    cfg = json.loads(cfg_text)
    cfg_sha = hashlib.sha256(cfg_text.encode()).hexdigest()
    out = Path(cfg["output_dir"])
    if a.clean and out.exists():
        for child in out.iterdir():  # clear contents (keeps the directory itself)
            shutil.rmtree(child) if child.is_dir() else child.unlink()
    (out / "networks").mkdir(parents=True, exist_ok=True)
    (out / "render_manifests").mkdir(parents=True, exist_ok=True)

    catalog = json.loads(Path(cfg["topology_bench_catalog"]).read_text(encoding="utf-8"))
    master = np.random.default_rng(cfg["master_seed"])
    eligible = S.eligible_long_haul_sources(catalog, cfg["long_haul_core"])
    per = cfg["per_class"]
    if len(eligible) < per:
        raise SystemExit(f"only {len(eligible)} eligible long-haul sources for {per} scenarios")
    lh_sources = [eligible[int(i)] for i in master.permutation(len(eligible))[:per]]
    anchors = anchor_cities(catalog)
    anchor_order = {c: master.permutation(len(anchors)).tolist() for c in ("metro_ring", "metro_aggregation", "dci")}

    built = []
    seen: set = set()
    for cls in CLASSES:
        for k in range(per):
            sc, seed = build_one(cls, k, cfg, catalog, lh_sources, anchors, anchor_order, seen)
            sc["category"], sc["seed"], sc["class_index_k"] = cls, seed, k
            if sc["group_key"] is None:
                sc["group_key"] = f"SYN_{cls}_{k:04d}"
            built.append(sc)

    order = master.permutation(len(built))
    commit = git_commit()
    rows = []
    for new_i, bi in enumerate(order, start=1):
        sc = built[int(bi)]
        sid = f"network_{new_i:04d}"
        base = out / "networks" / sid
        manifest = render(sc, str(base) + ".png")
        manifest["scenario_id"] = sid
        (out / "render_manifests" / f"{sid}.render.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")

        node_out = []
        for n in sc["nodes"]:
            d = {k: n[k] for k in ("id", "role", "lat", "lon", "degree")}
            d["tier"] = n.get("tier")
            d["diagram_label"] = [t for t in manifest["nodes"] if t["node_id"] == n["id"]][0]["text"]
            node_out.append(d)
        edge_keys = ("id", "u", "v", "medium", "length_km", "great_circle_km", "route_factor", "n_spans",
                     "span_length_km", "n_inline_amplifiers", "inline_amplifier_type")
        edge_out = [{k: e.get(k) for k in edge_keys} | {"diagram_label": [t for t in manifest["edges"] if t["edge_id"] == e["id"]][0]["text"]}
                    for e in sc["edges"]]
        g = nx.Graph([(e["u"], e["v"]) for e in sc["edges"]])
        graph = {"scenario_id": sid, "directed": False, "node_count": len(node_out), "edge_count": len(edge_out),
                 "nodes": node_out, "edges": edge_out,
                 "connectivity": {"connected": nx.is_connected(g), "components": nx.number_connected_components(g),
                                  "min_degree": min(dict(g.degree()).values()),
                                  "max_degree": max(dict(g.degree()).values())}}
        (Path(str(base) + ".graph.json")).write_text(json.dumps(graph, indent=1), encoding="utf-8")

        used = sorted({eq.get("assumption") for eq in sc["equipment"] if eq.get("assumption")})
        equipment = {"scenario_id": sid, "items": sc["equipment"],
                     "parameters": sc["equipment_assumptions"],
                     "assumptions": {k: ASSUMPTIONS[k] for k in used},
                     "note": "Synthetic equipment assignment. Counts and types are modelling assumptions, "
                             "not vendor designs; no GNPy simulation has been run for this scenario."}
        (Path(str(base) + ".equipment.json")).write_text(json.dumps(equipment, indent=1), encoding="utf-8")

        lengths = [e["length_km"] for e in sc["edges"]]
        geo = dict(sc["geography"])
        geo["geo_extent_km"] = round(geo_extent(sc["nodes"]), 1)
        geo["coordinate_provenance"] = sc["provenance"]["coordinates"]
        geo["length_note"] = ("Fibre length is NOT straight-line distance; see route factor per edge and "
                              "assumptions A1/A2. Routes do not follow surveyed rights-of-way or real cables.")
        meta = {
            "scenario_id": sid,
            "ground_truth": {"category": sc["category"], "category_display": CLASS_DISPLAY[sc["category"]]},
            "generation_family": sc["family"],
            "group_key": sc["group_key"],
            "seed": sc["seed"], "master_seed": cfg["master_seed"], "generation_attempt": sc["generation_attempt"],
            "provenance": sc["provenance"],
            "geography": geo,
            "equipment_assumptions": sc["equipment_assumptions"],
            "assumption_ids": sorted(set(used) | ({"A1_tb_lengths"} if sc["category"] == "long_haul_core" else {"A2_synthetic_route_factor"})),
            "network_size": {"n_nodes": len(sc["nodes"]), "n_edges": len(sc["edges"]),
                             "total_fiber_km": round(sum(lengths), 1),
                             "link_km_min": round(min(lengths), 2), "link_km_max": round(max(lengths), 2),
                             "n_inline_amplifiers": sum(e["n_inline_amplifiers"] for e in sc["edges"]),
                             "roles": {r: sum(1 for n in sc["nodes"] if n["role"] == r) for r in sorted({n["role"] for n in sc["nodes"]})}},
            "params": sc.get("params"),
            "structural_signature_wl": sc["structural_signature_wl"],
            "generation": {"config_file": a.config, "config_sha256": cfg_sha,
                           "generator_version": cfg["generator_version"], "git_commit": commit,
                           "render_style_hash": STYLE_HASH},
            "validation": {"status": "pending"},
        }
        (Path(str(base) + ".metadata.json")).write_text(json.dumps(meta, indent=1), encoding="utf-8")
        rows.append({"scenario_id": sid, "category": sc["category"], "family": sc["family"],
                     "group_key": sc["group_key"], "seed": sc["seed"], "n_nodes": len(sc["nodes"]),
                     "n_edges": len(sc["edges"])})
        print(f"{sid} {sc['category']:18s} {sc['family']:34s} N={len(sc['nodes']):2d} E={len(sc['edges']):2d}")

    with open(out / "manifest.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    shutil.copyfile(a.config, out / "generation_config.json")
    log = {"generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "config_sha256": cfg_sha, "git_commit": commit, "python": sys.version.split()[0],
           "platform": platform.platform(), "numpy": np.__version__, "networkx": nx.__version__,
           "matplotlib": matplotlib.__version__, "n_scenarios": len(rows),
           "long_haul_sources_eligible": len(eligible),
           "long_haul_sources_eligible_ids": [f"TB_{t['tb_index']:03d}_{t['name']}" for t in eligible],
           "long_haul_sources_excluded": {f"TB_{t['tb_index']:03d}_{t['name']}": S.long_haul_exclusion_reasons(t, cfg["long_haul_core"])
                                          for t in catalog["topologies"] if S.long_haul_exclusion_reasons(t, cfg["long_haul_core"])},
           "long_haul_sources_used": [f"TB_{t['tb_index']:03d}_{t['name']}" for t in lh_sources],
           "anchor_city_pool": len(anchors)}
    (out / "generation_log.json").write_text(json.dumps(log, indent=1), encoding="utf-8")
    print(f"done: {len(rows)} scenarios -> {out}")


if __name__ == "__main__":
    main()
