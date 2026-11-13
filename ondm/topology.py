"""Read-only access to the corrected 30-topology semantic dataset (data/semantic_pilot)."""
from __future__ import annotations

import csv
import json
from functools import lru_cache
from pathlib import Path

import networkx as nx

from .config import SETTINGS


def data_dir() -> Path:
    return SETTINGS.data_dir


def list_samples() -> list[str]:
    return sorted(p.stem for p in (data_dir() / "graphs").glob("topo_*.json"))


@lru_cache(maxsize=64)
def manifest() -> dict[str, dict]:
    path = data_dir() / "manifest.csv"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as fh:
        return {row["sample_id"]: row for row in csv.DictReader(fh)}


def graph_path(sample_id: str) -> Path:
    if sample_id not in list_samples():
        raise ValueError(f"Unknown sample {sample_id!r}")
    return data_dir() / "graphs" / f"{sample_id}.json"


def image_path(sample_id: str) -> Path:
    return data_dir() / "images" / f"{sample_id}.png"


@lru_cache(maxsize=64)
def _load_raw(sample_id: str) -> str:
    return graph_path(sample_id).read_text(encoding="utf-8")


def load_topology(sample_id: str) -> dict:
    """Return a fresh copy of the ground-truth graph JSON (never mutate the source file)."""
    return json.loads(_load_raw(sample_id))


def build_graph(sample_id: str) -> nx.Graph:
    """Undirected NetworkX graph; vertices are ROADM switching sites, edges are fiber links."""
    data = load_topology(sample_id)
    graph = nx.Graph(sample_id=sample_id, topology_type=data.get("topology_type"))
    for node in data["nodes"]:
        graph.add_node(
            str(node["id"]),
            equipment_type=node.get("equipment_type", "ROADM"),
            site_role=node.get("site_role"),
            attached_transceiver=bool(node.get("attached_transceiver", False)),
            x=node.get("position_px", {}).get("x"),
            y=node.get("position_px", {}).get("y"),
        )
    for edge in data["edges"]:
        graph.add_edge(
            str(edge["source"]),
            str(edge["target"]),
            distance_km=float(edge["distance_km"]),
            visual_style=edge.get("visual_style"),
        )
    return graph


def controlled_input(sample_id: str) -> dict:
    """Minimal, sanitized topology payload handed to the code sandbox (no paths, no secrets)."""
    data = load_topology(sample_id)
    return {
        "sample_id": sample_id,
        "topology_type": data.get("topology_type"),
        "nodes": [
            {"id": str(n["id"]), "equipment_type": n.get("equipment_type", "ROADM"),
             "attached_transceiver": bool(n.get("attached_transceiver", False))}
            for n in data["nodes"]
        ],
        "edges": [
            {"source": str(e["source"]), "target": str(e["target"]), "distance_km": float(e["distance_km"])}
            for e in data["edges"]
        ],
    }


def path_length_km(graph: nx.Graph, path: list[str]) -> float:
    return float(sum(graph[u][v]["distance_km"] for u, v in zip(path, path[1:])))


def validate_path(graph: nx.Graph, path: list[str]) -> tuple[bool, str]:
    if not isinstance(path, (list, tuple)) or len(path) < 2:
        return False, "path must contain at least two sites"
    path = [str(p) for p in path]
    for node in path:
        if node not in graph:
            return False, f"unknown site {node!r}"
    if len(set(path)) != len(path):
        return False, "path revisits a site (not a simple path)"
    for u, v in zip(path, path[1:]):
        if not graph.has_edge(u, v):
            return False, f"no fiber link {u}-{v} in topology"
    return True, "ok"


def summary(sample_id: str) -> dict:
    graph = build_graph(sample_id)
    lengths = [d["distance_km"] for _, _, d in graph.edges(data=True)]
    return {
        "sample_id": sample_id,
        "topology_type": graph.graph.get("topology_type"),
        "roadm_sites": sorted(graph.nodes()),
        "num_sites": graph.number_of_nodes(),
        "num_links": graph.number_of_edges(),
        "links": [{"a": u, "b": v, "km": d["distance_km"]} for u, v, d in sorted(graph.edges(data=True))],
        "total_fiber_km": sum(lengths),
        "min_link_km": min(lengths),
        "max_link_km": max(lengths),
        "connected": nx.is_connected(graph),
        "two_edge_connected": nx.is_connected(graph) and not any(nx.bridges(graph)),
        "bridges": [list(b) for b in nx.bridges(graph)],
        "articulation_points": sorted(nx.articulation_points(graph)),
        "data_provenance": "SYNTHETIC dataset (data/semantic_pilot) — not operator telemetry",
    }
