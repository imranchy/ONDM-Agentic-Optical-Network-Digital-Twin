"""Load the Topology Bench real-topology workbooks into a normalised JSON catalogue.

Source: Matzner et al., "Topology Bench: systematic graph-based benchmarking for core optical
networks", JOCN 17(1):7-27; dataset doi:10.5281/zenodo.13921775 (v4), licence CC-BY-4.0.
Only ``real_topologies.zip`` is read. Each workbook has a Nodes sheet
(Node_ID, Latitude, Longitude, Location Name, Country) and an Edges sheet
(Edge_ID, Source, Destination, Computed Length (km)).

Usage:
    python -m src.generation.topology_bench --raw references/topology_bench/raw/real \
        --out references/topology_bench/real_catalog.json
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import re
from pathlib import Path

import networkx as nx
import openpyxl

EARTH_R_KM = 6371.0088


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_R_KM * math.asin(min(1.0, math.sqrt(a)))


def load_workbook(path: str) -> dict:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    nodes_ws = next(ws for ws in wb.worksheets if ws.title.lower().startswith("nodes"))
    edges_ws = next(ws for ws in wb.worksheets if ws.title.lower().startswith("edges"))
    nodes, edges = [], []
    for i, row in enumerate(nodes_ws.iter_rows(values_only=True)):
        if i == 0 or not row or row[0] is None:
            continue
        nodes.append({"id": int(row[0]), "lat": float(row[1]), "lon": float(row[2]),
                      "name": None if row[3] is None else str(row[3]),
                      "country": None if row[4] is None else str(row[4])})
    for i, row in enumerate(edges_ws.iter_rows(values_only=True)):
        if i == 0 or not row or row[0] is None:
            continue
        edges.append({"id": int(row[0]), "u": int(row[1]), "v": int(row[2]),
                      "length_km": None if row[3] is None else float(row[3])})
    wb.close()
    m = re.match(r"TOP_(\d+)_(.+)\.xlsx$", os.path.basename(path))
    return {"tb_index": int(m.group(1)), "name": m.group(2), "file": os.path.basename(path),
            "nodes": nodes, "edges": edges}


def summarise(topo: dict) -> dict:
    g = nx.Graph()
    pos = {n["id"]: (n["lat"], n["lon"]) for n in topo["nodes"]}
    g.add_nodes_from(pos)
    ratios = []
    for e in topo["edges"]:
        if e["u"] == e["v"]:
            continue
        g.add_edge(e["u"], e["v"], length_km=e["length_km"])
        if e["length_km"] and e["u"] in pos and e["v"] in pos:
            gc = haversine_km(*pos[e["u"]], *pos[e["v"]])
            if gc > 1e-6:
                ratios.append(e["length_km"] / gc)
    lens = [d["length_km"] for *_, d in g.edges(data=True) if d["length_km"] is not None]
    ids = list(pos)
    extent = max((haversine_km(*pos[a], *pos[b]) for i, a in enumerate(ids) for b in ids[i + 1:]),
                 default=0.0)
    countries = sorted({n["country"] for n in topo["nodes"] if n["country"]})
    return {
        "n_nodes": g.number_of_nodes(), "n_edges": g.number_of_edges(),
        "connected": nx.is_connected(g) if g.number_of_nodes() else False,
        "n_components": nx.number_connected_components(g),
        "min_degree": min((d for _, d in g.degree()), default=0),
        "mean_degree": 2 * g.number_of_edges() / max(1, g.number_of_nodes()),
        "link_km_min": min(lens, default=None), "link_km_mean": sum(lens) / len(lens) if lens else None,
        "link_km_max": max(lens, default=None),
        "geo_extent_km": extent,
        "length_to_greatcircle_ratio_median": sorted(ratios)[len(ratios) // 2] if ratios else None,
        "length_to_greatcircle_ratio_min": min(ratios) if ratios else None,
        "length_to_greatcircle_ratio_max": max(ratios) if ratios else None,
        "countries": countries, "n_countries": len(countries),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="references/topology_bench/raw/real")
    ap.add_argument("--out", default="references/topology_bench/real_catalog.json")
    a = ap.parse_args()
    topos = []
    for f in sorted(glob.glob(os.path.join(a.raw, "TOP_*.xlsx"))):
        t = load_workbook(f)
        t["summary"] = summarise(t)
        topos.append(t)
    topos.sort(key=lambda t: t["tb_index"])
    out = {
        "source": {
            "dataset": "Topology Bench real_topologies.zip",
            "doi": "10.5281/zenodo.13921775", "version": "v4", "license": "CC-BY-4.0",
            "citation": "R. Matzner et al., 'Topology Bench: systematic graph-based benchmarking for "
                        "core optical networks', J. Opt. Commun. Netw. 17(1):7-27.",
            "md5_real_topologies_zip": "bcb92010a9116f575851781436528eb0",
            "notes": "Converted verbatim from the workbooks; 'Computed Length (km)' copied unchanged.",
        },
        "topologies": topos,
    }
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"wrote {len(topos)} topologies -> {a.out}")


if __name__ == "__main__":
    main()
