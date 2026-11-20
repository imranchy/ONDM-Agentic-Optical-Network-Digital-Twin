"""Fast checks of generator determinism, invariants and validator behaviour (no full dataset needed)."""
import json
from pathlib import Path

import numpy as np
import pytest

from src.generation import scenarios as S
from src.generation.generate_dataset import scenario_seed, structural_signature
from src.generation.taxonomy import LEAKAGE_TOKENS
from src.generation.render import node_text, edge_text
from src.validation.label_rules import evaluate
from src.validation.validate_dataset import tokens_hit

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT / "configs" / "pilot_125.json").read_text(encoding="utf-8"))
ANCHOR = {"name": "Testville", "country": "X", "lat": 48.0, "lon": 11.0, "source_topology": "TEST"}


def _graph(sc):
    return {"nodes": [{"id": n["id"], "role": n["role"], "lat": n["lat"], "lon": n["lon"]} for n in sc["nodes"]],
            "edges": sc["edges"], "edge_count": len(sc["edges"])}


def build(cls, seed):
    rng = np.random.default_rng(seed)
    c = CFG["common"]
    if cls == "metro_ring":
        sc = S.build_metro_ring(ANCHOR, rng, CFG[cls], c)
    elif cls == "metro_aggregation":
        sc = S.build_metro_aggregation(ANCHOR, rng, CFG[cls], c)
    elif cls == "dci":
        sc = S.build_dci(ANCHOR, rng, CFG[cls], c, [ANCHOR, {**ANCHOR, "name": "B", "lat": 49.5, "lon": 12.5}])
    else:
        sc = S.build_submarine(rng, CFG[cls], c)
    return S.finalise(sc, rng, c)


@pytest.mark.parametrize("cls", ["metro_ring", "metro_aggregation", "dci", "submarine"])
@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_synthetic_scenarios_satisfy_own_rule_only(cls, seed):
    sc = build(cls, seed)
    res = evaluate(_graph(sc), {"items": sc["equipment"]})
    assert res["rules"][cls], (cls, seed, res)
    assert res["satisfied"] == [cls], (cls, seed, res["satisfied"])


@pytest.mark.parametrize("cls", ["metro_ring", "submarine"])
def test_determinism(cls):
    a, b = build(cls, 42), build(cls, 42)
    assert json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)
    assert structural_signature(a) == structural_signature(b)


def test_amplifiers_live_on_edges_and_spans_are_consistent():
    sc = build("submarine", 7)
    for e in sc["edges"]:
        assert abs(e["n_spans"] * e["span_length_km"] - e["length_km"]) < 0.05 * e["n_spans"] + 0.01
        if e["medium"] == "submarine" and e["n_inline_amplifiers"]:
            assert e["inline_amplifier_type"] == "SUBMARINE_REPEATER"
    assert not any(n["role"] in ("ILA", "RPT") for n in sc["nodes"])


def test_drawn_text_has_no_leakage():
    for cls in ("metro_ring", "metro_aggregation", "dci", "submarine"):
        sc = build(cls, 11)
        for n in sc["nodes"]:
            assert not tokens_hit(node_text(n)), node_text(n)
        for e in sc["edges"]:
            assert not tokens_hit(edge_text(e))


def test_leakage_detector_catches_class_names():
    assert tokens_hit("Metro ring S01") and tokens_hit("DCI site") and tokens_hit("core ROADM")
    assert not tokens_hit("S01\nROADM-3D") and not tokens_hit("DC ZR×4") and not tokens_hit("CLS SLTE")
    assert "submarine" in LEAKAGE_TOKENS


def test_seed_scheme_is_stable():
    assert scenario_seed(20261120, 0, 0) == scenario_seed(20261120, 0, 0)
    assert scenario_seed(20261120, 0, 0) != scenario_seed(20261120, 0, 1)
