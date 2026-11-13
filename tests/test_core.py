"""Basic integration checks (no VLM needed). Run: .venv\\Scripts\\python -m pytest -q"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ondm import gnpy_engine, inventory, sandbox  # noqa: E402
from ondm import topology as topo  # noqa: E402
from ondm.agent import _trusted_failure, _trusted_k_paths, _api_hint, _error_lines  # noqa: E402


def test_dataset_intact():
    samples = topo.list_samples()
    assert len(samples) == 30
    for s in samples:
        g = topo.build_graph(s)
        assert g.number_of_nodes() >= 6
        assert all(d["equipment_type"] == "ROADM" for _, d in g.nodes(data=True))
        assert topo.image_path(s).exists()


def test_path_validation():
    g = topo.build_graph("topo_0003")
    assert topo.validate_path(g, ["A", "F", "E"])[0]
    assert not topo.validate_path(g, ["A", "C"])[0]            # no direct link
    assert not topo.validate_path(g, ["A", "Z"])[0]            # unknown node
    assert topo.path_length_km(g, ["A", "F", "E", "D", "C"]) == 370


def test_routing_and_failure_trusted_tools():
    g = topo.build_graph("topo_0003")
    paths = _trusted_k_paths(g, "A", "C", 3)
    assert paths[0] == ["A", "F", "E", "D", "C"] and len(paths) == 2   # ring: exactly two routes
    res = _trusted_failure(g, "D", "E")
    assert res["network_still_connected"] is True                       # ring survives one cut
    assert res["num_affected_pairs"] > 0 and res["num_unrestorable_pairs"] == 0
    tree = topo.build_graph("topo_0002")
    u, v = next(iter(tree.edges()))
    assert _trusted_failure(tree, u, v)["network_still_connected"] is False  # tree: every link is a bridge


def test_gnpy_feasibility_ordering():
    short = gnpy_engine.assess_path("topo_0003", ["A", "F"])
    long = gnpy_engine.assess_path("topo_0003", ["A", "B", "C"])
    assert short["status"] == long["status"] == "SIMULATED"
    assert short["gsnr_0p1nm_db_worst"] > long["gsnr_0p1nm_db_worst"]
    assert short["verdict"].startswith("FEASIBLE")
    assert long["remaining_margin_db_worst"] < short["remaining_margin_db_worst"]


def test_gnpy_rejects_invalid_path():
    r = gnpy_engine.assess_path("topo_0003", ["A", "C"])
    assert r["verdict"] == "UNDETERMINED" and "Invalid path" in r["error"]


def test_local_inventory_fallback_is_labelled():
    inv = inventory.LocalInventory().topology_inventory("topo_0003")
    assert "LOCAL FALLBACK" in inv["source"]
    corr = inventory.correlate("topo_0003", inv)
    assert not [f for f in corr["findings"] if f["severity"] == "high"]


def test_static_code_policy():
    assert sandbox.validate_code("import os\nresult=1")
    assert sandbox.validate_code("result=open('x').read()")
    assert sandbox.validate_code("x=().__class__\nresult=1")
    assert sandbox.validate_code("x=1")  # no result
    assert not sandbox.validate_code("import networkx as nx\nresult=nx.number_of_nodes(G)")


@pytest.mark.skipif(not sandbox.docker_available(), reason="Docker sandbox image not available")
def test_sandbox_executes_and_isolates():
    t = topo.controlled_input("topo_0003")
    ok = sandbox.run_code("import networkx as nx\nresult=nx.dijkstra_path_length(G,'A','C',weight='distance_km')", t)
    assert ok.status == "OK" and ok.result == 370
    err = sandbox.run_code("result=G['A']['Z']", t)
    assert err.status == "RUNTIME_ERROR"


def test_feedback_helpers():
    assert "articulation_points" in _api_hint("AttributeError: module 'networkx' has no attribute 'is_articulation_point'")
    assert "line 2" in _error_lines("a=1\nb=a[0]\nresult=b", 'File "<generated>", line 2, in <module>')
