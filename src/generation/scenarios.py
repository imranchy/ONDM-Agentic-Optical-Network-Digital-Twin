"""Scenario builders for the five optical transport architecture classes.

A *scenario* is a plain dict:
    nodes: [{id, role, lat, lon, tier}]   graph vertices are SITES
    edges: [{id, u, v, medium, length_km, great_circle_km, route_factor, length_source}]
    family, provenance, geography, params
Inline amplifiers / undersea repeaters are attached to edges by ``add_equipment`` (never vertices).

All ranges come from the generation config (configs/*.json) and are declared assumptions
(see src/generation/taxonomy.py::ASSUMPTIONS).
"""
from __future__ import annotations

import math
from typing import Any

import networkx as nx
import numpy as np

from .taxonomy import (
    MEDIUM_SUBMARINE, MEDIUM_TERRESTRIAL, ROLE_BU, ROLE_CLS, ROLE_CO, ROLE_DC, ROLE_HUB_ROADM,
    ROLE_OADM, ROLE_POP, ROLE_ROADM,
)
from .topology_bench import EARTH_R_KM, haversine_km


# ------------------------------------------------------------------------------------------
# geometry helpers
# ------------------------------------------------------------------------------------------
def destination(lat: float, lon: float, dist_km: float, bearing_deg: float) -> tuple[float, float]:
    """Great-circle destination point."""
    d = dist_km / EARTH_R_KM
    b = math.radians(bearing_deg)
    p1, l1 = math.radians(lat), math.radians(lon)
    p2 = math.asin(math.sin(p1) * math.cos(d) + math.cos(p1) * math.sin(d) * math.cos(b))
    l2 = l1 + math.atan2(math.sin(b) * math.sin(d) * math.cos(p1), math.cos(d) - math.sin(p1) * math.sin(p2))
    lon2 = (math.degrees(l2) + 540) % 360 - 180
    return round(math.degrees(p2), 5), round(lon2, 5)


def interpolate_gc(a: tuple[float, float], b: tuple[float, float], f: float) -> tuple[float, float]:
    """Point at fraction f along the great circle a->b."""
    p1, l1 = map(math.radians, a)
    p2, l2 = map(math.radians, b)
    d = haversine_km(*a, *b) / EARTH_R_KM
    if d < 1e-9:
        return a
    A, B = math.sin((1 - f) * d) / math.sin(d), math.sin(f * d) / math.sin(d)
    x = A * math.cos(p1) * math.cos(l1) + B * math.cos(p2) * math.cos(l2)
    y = A * math.cos(p1) * math.sin(l1) + B * math.cos(p2) * math.sin(l2)
    z = A * math.sin(p1) + B * math.sin(p2)
    return round(math.degrees(math.atan2(z, math.hypot(x, y))), 5), round(math.degrees(math.atan2(y, x)), 5)


def initial_bearing(a: tuple[float, float], b: tuple[float, float]) -> float:
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dl = math.radians(b[1] - a[1])
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def u(rng: np.random.Generator, lo_hi) -> float:
    return float(rng.uniform(lo_hi[0], lo_hi[1]))


def ri(rng: np.random.Generator, lo_hi) -> int:
    return int(rng.integers(lo_hi[0], lo_hi[1] + 1))


class _Builder:
    """Accumulates nodes/edges with synthetic lengths derived from coordinates."""

    def __init__(self, rng: np.random.Generator, rf_terrestrial, rf_submarine):
        self.rng = rng
        self.nodes: list[dict] = []
        self.edges: list[dict] = []
        self.rf_t, self.rf_s = rf_terrestrial, rf_submarine
        self._pos: dict[str, tuple[float, float]] = {}

    def node(self, role: str, lat: float, lon: float, tier: str | None = None) -> str:
        nid = f"n{len(self.nodes)}"
        self.nodes.append({"id": nid, "role": role, "lat": round(lat, 5), "lon": round(lon, 5), "tier": tier})
        self._pos[nid] = (lat, lon)
        return nid

    def edge(self, a: str, b: str, medium: str = MEDIUM_TERRESTRIAL) -> None:
        if a == b or any({e["u"], e["v"]} == {a, b} for e in self.edges):
            return
        gc = haversine_km(*self._pos[a], *self._pos[b])
        rf = u(self.rng, self.rf_s if medium == MEDIUM_SUBMARINE else self.rf_t)
        self.edges.append({"u": a, "v": b, "medium": medium, "great_circle_km": round(gc, 3),
                           "route_factor": round(rf, 4), "length_km": round(max(gc * rf, 0.5), 2),
                           "length_source": "synthetic: great-circle x route factor (A2)"})


# ------------------------------------------------------------------------------------------
# 1. Long-haul / core from Topology Bench
# ------------------------------------------------------------------------------------------
def long_haul_exclusion_reasons(t: dict, cfg: dict) -> list[str]:
    """Why a Topology Bench topology is NOT used as a long-haul source (empty list = eligible)."""
    s, r = t["summary"], []
    if not cfg["min_nodes"] <= s["n_nodes"] <= cfg["max_nodes"]:
        r.append(f"n_nodes {s['n_nodes']} outside [{cfg['min_nodes']}, {cfg['max_nodes']}] (diagram legibility)")
    if not s["connected"]:
        r.append("disconnected")
    if not cfg["min_extent_km"] <= s["geo_extent_km"] <= cfg["max_extent_km"]:
        r.append(f"extent {s['geo_extent_km']:.0f} km outside [{cfg['min_extent_km']}, {cfg['max_extent_km']}]")
    if (s["link_km_mean"] or 0) < cfg["min_mean_link_km"]:
        r.append(f"mean link {s['link_km_mean']:.0f} km < {cfg['min_mean_link_km']}")
    if (s["link_km_max"] or 0) > cfg["max_link_km"]:
        r.append(f"max link {s['link_km_max']:.0f} km > {cfg['max_link_km']} (likely logical/IP adjacency)")
    lo, hi = s.get("length_to_greatcircle_ratio_min"), s.get("length_to_greatcircle_ratio_max")
    if lo is not None and (lo < cfg["min_length_ratio"] or hi > cfg["max_length_ratio"]):
        r.append(f"length/great-circle ratio range [{lo:.2f}, {hi:.2f}] outside "
                 f"[{cfg['min_length_ratio']}, {cfg['max_length_ratio']}] (inconsistent source data)")
    return r


def eligible_long_haul_sources(catalog: dict, cfg: dict) -> list[dict]:
    return [t for t in catalog["topologies"] if not long_haul_exclusion_reasons(t, cfg)]


def build_long_haul(src: dict, rng: np.random.Generator, cfg: dict) -> dict[str, Any]:
    nodes, idmap = [], {}
    for n in src["nodes"]:
        nid = f"n{len(nodes)}"
        idmap[n["id"]] = nid
        nodes.append({"id": nid, "role": ROLE_ROADM, "lat": n["lat"], "lon": n["lon"], "tier": None,
                      "source_node_id": n["id"], "source_location_name": n["name"],
                      "source_country": n["country"]})
    pos = {n["id"]: (n["lat"], n["lon"]) for n in src["nodes"]}
    edges, seen = [], set()
    for e in src["edges"]:
        key = frozenset((e["u"], e["v"]))
        if e["u"] == e["v"] or key in seen:
            continue
        seen.add(key)
        gc = haversine_km(*pos[e["u"]], *pos[e["v"]])
        edges.append({"u": idmap[e["u"]], "v": idmap[e["v"]], "medium": MEDIUM_TERRESTRIAL,
                      "great_circle_km": round(gc, 3),
                      "route_factor": round(e["length_km"] / gc, 4) if gc > 1e-6 else None,
                      "length_km": round(e["length_km"], 2), "source_edge_id": e["id"],
                      "length_source": "Topology Bench 'Computed Length (km)' (A1)"})
    countries = sorted({n["country"] for n in src["nodes"] if n["country"]})
    return {
        "family": "tb_real_derived_mesh",
        "nodes": nodes, "edges": edges,
        "provenance": {
            "topology_origin": "derived_from_published_real_world_topology",
            "source_dataset": "Topology Bench real_topologies (doi:10.5281/zenodo.13921775, CC-BY-4.0)",
            "source_topology_id": f"TB_{src['tb_index']:03d}_{src['name']}",
            "source_file": src["file"],
            "modification": "none to graph/coordinates/lengths; duplicate edges/self-loops removed if present",
            "coordinates": "real_derived (Topology Bench node lat/lon)",
            "fiber_connections": "real_derived (Topology Bench edges)",
            "fiber_lengths": "real_derived_with_route_factor (Topology Bench computed length, A1)",
            "equipment": "synthetic_assignment",
            "optical_parameters": "assumed",
        },
        "geography": {"scope": "national_or_continental", "countries": countries,
                      "coordinate_source": "Topology Bench"},
        "group_key": f"TB_{src['tb_index']:03d}",
    }


# ------------------------------------------------------------------------------------------
# 2. Metro optical ring
# ------------------------------------------------------------------------------------------
def build_metro_ring(anchor: dict, rng: np.random.Generator, cfg: dict, common: dict) -> dict:
    b = _Builder(rng, common["route_factor_terrestrial"], common["route_factor_submarine"])
    variant = str(rng.choice(cfg["variants"]))
    lat0, lon0 = anchor["lat"], anchor["lon"]
    R = u(rng, cfg["radius_km"])
    rot = u(rng, (0, 360))
    ecc = u(rng, (0.65, 1.0))

    def ring(center, n, radius, hubs_at):
        ids = []
        # near-even angular spacing with jitter
        even = np.linspace(0, 360, n, endpoint=False)
        ang = even + rng.uniform(-0.25, 0.25, n) * (360 / n)
        for k in range(n):
            r = radius * (ecc if k % 2 else 1.0)
            la, lo = destination(center[0], center[1], r, rot + ang[k])
            ids.append(b.node(ROLE_HUB_ROADM if k in hubs_at else ROLE_OADM, la, lo))
        for k in range(n):
            b.edge(ids[k], ids[(k + 1) % n])
        return ids

    if variant == "single_ring":
        n = ri(rng, cfg["nodes_single"])
        ring((lat0, lon0), n, R, {0})
    elif variant == "dual_hub_ring":
        n = ri(rng, cfg["nodes_single"])
        ring((lat0, lon0), n, R, {0, n // 2})
    else:  # dual_ring: second ring attached at two hubs of the first
        n1 = ri(rng, cfg["nodes_dual_each"])
        ids1 = ring((lat0, lon0), n1, R, {0, 1})
        h1, h2 = ids1[0], ids1[1]
        m = ri(rng, (max(2, cfg["nodes_dual_each"][0] - 2), cfg["nodes_dual_each"][1] - 2))
        # second ring nodes on an arc outside the first ring, between the two hubs
        pa = b._pos[h1]; pb = b._pos[h2]
        mid = ((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2)
        out_bearing = initial_bearing((lat0, lon0), mid)
        c2 = destination(lat0, lon0, R * 1.9, out_bearing)
        R2 = R * u(rng, (0.7, 1.0))
        start = initial_bearing(c2, pb)
        prev = h2
        for k in range(m):
            la, lo = destination(c2[0], c2[1], R2, start + (k + 1) * 300 / (m + 1))
            nid = b.node(ROLE_OADM, la, lo)
            b.edge(prev, nid)
            prev = nid
        b.edge(prev, h1)
    return _synthetic_wrap(b, "metro_ring_" + variant, anchor, "single_metro_area")


# ------------------------------------------------------------------------------------------
# 3. Metro aggregation (hub -> aggregation -> access)
# ------------------------------------------------------------------------------------------
def build_metro_aggregation(anchor: dict, rng: np.random.Generator, cfg: dict, common: dict) -> dict:
    b = _Builder(rng, common["route_factor_terrestrial"], common["route_factor_submarine"])
    lat0, lon0 = anchor["lat"], anchor["lon"]
    rot = u(rng, (0, 360))
    n_hub = ri(rng, cfg["hubs"])
    n_agg = ri(rng, cfg["agg_nodes"])
    n_co = ri(rng, cfg["co_nodes"])
    agg_topo = str(rng.choice(cfg["agg_tier_variants"]))
    p_dual = u(rng, cfg["dual_homing_prob"])

    hubs = []
    for h in range(n_hub):
        la, lo = destination(lat0, lon0, u(rng, (1.0, 4.0)) if n_hub > 1 else 0.3, rot + 180 * h)
        hubs.append(b.node(ROLE_HUB_ROADM, la, lo, tier="hub"))
    if n_hub == 2:
        b.edge(hubs[0], hubs[1])
    R1 = u(rng, cfg["agg_radius_km"])
    agg, agg_ang = [], []
    for k in range(n_agg):
        a = rot + 360 * k / n_agg + u(rng, (-12, 12))
        la, lo = destination(lat0, lon0, R1 * u(rng, (0.85, 1.15)), a)
        agg.append(b.node(ROLE_ROADM, la, lo, tier="distribution"))
        agg_ang.append(a)
    for k in range(n_agg):  # aggregation tier ring backbone
        if agg_topo == "ring" or k < n_agg - 1 or n_agg <= 3:
            b.edge(agg[k], agg[(k + 1) % n_agg])
    if agg_topo == "partial_mesh":
        b.edge(agg[-1], agg[0])
        for _ in range(ri(rng, (1, max(1, n_agg - 3)))):
            i, j = rng.choice(n_agg, 2, replace=False)
            if abs(int(i) - int(j)) not in (1, n_agg - 1):
                b.edge(agg[int(i)], agg[int(j)])
    # hub uplinks: each hub to 2 aggregation nodes (diverse)
    for h_i, h in enumerate(hubs):
        picks = rng.choice(n_agg, size=min(n_agg, 2 if n_hub == 2 else 3), replace=False)
        for p in picks:
            b.edge(h, agg[int(p)])
    # access tier
    for c in range(n_co):
        parent = c % n_agg
        a = agg_ang[parent] + u(rng, (-22, 22))
        la, lo = destination(lat0, lon0, R1 + u(rng, cfg["access_offset_km"]), a)
        co = b.node(ROLE_CO, la, lo, tier="access")
        b.edge(co, agg[parent])
        if rng.random() < p_dual:
            nb = (parent + (1 if rng.random() < 0.5 else -1)) % n_agg
            b.edge(co, agg[nb])
    sc = _synthetic_wrap(b, f"metro_aggregation_{agg_topo}_{n_hub}hub", anchor, "metro_or_regional")
    sc["params"] = {"dual_homing_prob": round(p_dual, 3), "agg_tier": agg_topo}
    return sc


# ------------------------------------------------------------------------------------------
# 4. Data center interconnect
# ------------------------------------------------------------------------------------------
def build_dci(anchor: dict, rng: np.random.Generator, cfg: dict, common: dict, anchors: list[dict]) -> dict:
    b = _Builder(rng, common["route_factor_terrestrial"], common["route_factor_submarine"])
    variant = str(rng.choice(cfg["variants"], p=cfg.get("variant_probs")))
    lat0, lon0 = anchor["lat"], anchor["lon"]
    used_anchors = [anchor]
    if variant == "metro_dci":
        n = ri(rng, cfg["metro_dc_sites"])
        R = u(rng, cfg["metro_radius_km"])
        rot = u(rng, (0, 360))
        dcs = []
        for k in range(n):
            la, lo = destination(lat0, lon0, R * u(rng, (0.4, 1.0)), rot + 360 * k / n + u(rng, (-15, 15)))
            dcs.append(b.node(ROLE_DC, la, lo))
        if n <= 4:
            for i in range(n):
                for j in range(i + 1, n):
                    b.edge(dcs[i], dcs[j])
        else:
            for i in range(n):
                b.edge(dcs[i], dcs[(i + 1) % n])
            for _ in range(ri(rng, (1, n // 2))):
                i, j = rng.choice(n, 2, replace=False)
                b.edge(dcs[int(i)], dcs[int(j)])
    else:  # regional_dci: 2-4 DC campuses in different real cities, linked via ROADMs + ILAs
        n_campus = ri(rng, cfg["regional_campuses"])
        cities = [anchor]
        cand = [a for a in anchors if cfg["regional_city_km"][0] <= haversine_km(lat0, lon0, a["lat"], a["lon"]) <= cfg["regional_city_km"][1]]
        rng.shuffle(cand)
        for c in cand:
            if len(cities) >= n_campus:
                break
            if all(haversine_km(c["lat"], c["lon"], x["lat"], x["lon"]) >= cfg["regional_city_km"][0] for x in cities):
                cities.append(c)
        if len(cities) < 2:  # fall back to a synthetic second campus location
            la, lo = destination(lat0, lon0, u(rng, cfg["regional_city_km"]), u(rng, (0, 360)))
            cities.append({"name": None, "lat": la, "lon": lo, "country": None, "synthetic": True})
        used_anchors = cities
        campus_dcs, gw = [], []
        for c in cities:
            k = ri(rng, cfg["dcs_per_campus"])
            ids = []
            for j in range(k):
                la, lo = destination(c["lat"], c["lon"], u(rng, (2, 15)), u(rng, (0, 360)))
                ids.append(b.node(ROLE_DC, la, lo))
            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    b.edge(ids[i], ids[j])
            campus_dcs.append(ids)
            # a single-DC campus is its own gateway (keeps the DC dual-homed onto the campus ring)
            use_roadm = len(ids) > 1 and rng.random() < cfg["regional_roadm_prob"]
            if use_roadm:
                r = b.node(ROLE_ROADM, *destination(c["lat"], c["lon"], u(rng, (3, 12)), u(rng, (0, 360))))
                for d in ids:
                    b.edge(d, r)
                gw.append([r, r])
            else:
                gw.append([ids[0], ids[-1]])
        nc = len(cities)
        for i in range(nc):  # campuses in a ring (diverse) or a pair with two routes
            j = (i + 1) % nc
            if nc == 2 and i == 1:
                break
            b.edge(gw[i][-1], gw[j][0])
        if nc == 2:
            # second, geographically diverse route through an intermediate ROADM site
            a_end = campus_dcs[0][0] if gw[0][0] == gw[0][-1] and campus_dcs[0][0] != gw[0][-1] else gw[0][0]
            z_end = campus_dcs[1][-1] if gw[1][0] == gw[1][-1] and campus_dcs[1][-1] != gw[1][0] else gw[1][-1]
            pa, pz = b._pos[a_end], b._pos[z_end]
            mid = interpolate_gc(pa, pz, 0.5)
            off = haversine_km(*pa, *pz) * u(rng, (0.15, 0.3))
            via = b.node(ROLE_ROADM, *destination(*mid, off, initial_bearing(pa, pz) + (90 if rng.random() < 0.5 else -90)))
            b.edge(a_end, via)
            b.edge(via, z_end)
    sc = _synthetic_wrap(b, "dci_" + variant, anchor, "metro" if variant == "metro_dci" else "regional")
    sc["geography"]["anchor_cities"] = [{k: a.get(k) for k in ("name", "country", "lat", "lon", "source_topology")} for a in used_anchors]
    return sc


# ------------------------------------------------------------------------------------------
# 5. Submarine
# ------------------------------------------------------------------------------------------
def build_submarine(rng: np.random.Generator, cfg: dict, common: dict) -> dict:
    b = _Builder(rng, common["route_factor_terrestrial"], common["route_factor_submarine"])
    variant = str(rng.choice(cfg["variants"], p=cfg.get("variant_probs")))
    start = (u(rng, cfg["start_lat"]), u(rng, (-180, 180)))
    bearing = u(rng, (0, 360))
    cls_ids = []

    p_dual_bh = cfg.get("dual_backhaul_prob", 0.35)

    def pop_for(cls_id, away_bearing):
        """Terrestrial backhaul: one POP, or two diverse POPs interconnected terrestrially."""
        pops = []
        for _ in range(2 if rng.random() < p_dual_bh else 1):
            la, lo = destination(*b._pos[cls_id], u(rng, cfg["backhaul_km"]), away_bearing + u(rng, (-40, 40)))
            p = b.node(ROLE_POP, la, lo)
            b.edge(cls_id, p, MEDIUM_TERRESTRIAL)
            pops.append(p)
        if len(pops) == 2:
            b.edge(pops[0], pops[1], MEDIUM_TERRESTRIAL)
        return pops

    if variant in ("point_to_point", "branched_trunk"):
        L = u(rng, cfg["trunk_gc_km"])
        end = destination(*start, L, bearing)
        a = b.node(ROLE_CLS, *start)
        z_coords = end
        if variant == "point_to_point":
            z = b.node(ROLE_CLS, *z_coords)
            b.edge(a, z, MEDIUM_SUBMARINE)
            cls_ids = [a, z]
            if rng.random() < cfg.get("dual_landing_prob", 0.4):
                # landing diversity: a second trunk between a second CLS pair 20-80 km from the first
                a2 = b.node(ROLE_CLS, *destination(*start, u(rng, (20, 80)), bearing + 90 + u(rng, (-30, 30))))
                z2 = b.node(ROLE_CLS, *destination(*end, u(rng, (20, 80)), bearing + 90 + u(rng, (-30, 30))))
                b.edge(a2, z2, MEDIUM_SUBMARINE)
                pa = pop_for(a, bearing + 180)
                pz = pop_for(z, bearing)
                b.edge(a2, pa[-1], MEDIUM_TERRESTRIAL)
                b.edge(z2, pz[-1], MEDIUM_TERRESTRIAL)
                cls_ids = []  # backhaul already attached
        else:
            n_bu = ri(rng, cfg["branching_units"])
            fr = np.sort(rng.uniform(0.15, 0.85, n_bu))
            prev = a
            bus = []
            for f in fr:
                bu = b.node(ROLE_BU, *interpolate_gc(start, end, float(f)))
                b.edge(prev, bu, MEDIUM_SUBMARINE)
                bus.append(bu)
                prev = bu
            z = b.node(ROLE_CLS, *z_coords)
            b.edge(prev, z, MEDIUM_SUBMARINE)
            cls_ids = [a, z]
            for bu in bus:
                side = 90 if rng.random() < 0.5 else -90
                la, lo = destination(*b._pos[bu], u(rng, cfg["branch_gc_km"]), bearing + side + u(rng, (-25, 25)))
                c = b.node(ROLE_CLS, la, lo)
                b.edge(bu, c, MEDIUM_SUBMARINE)
                cls_ids.append(c)
        if cls_ids:
            pop_for(a, bearing + 180)
            pop_for(z, bearing)  # beyond the far landing
            for c in cls_ids[2:]:
                pop_for(c, initial_bearing(b._pos[a], b._pos[c]))
    else:  # festoon: chain of CLS along a synthetic coastline, short unrepeatered segments
        n = ri(rng, cfg["festoon_cls"])
        pos = start
        prev = None
        for k in range(n):
            c = b.node(ROLE_CLS, *pos)
            if prev is not None:
                b.edge(prev, c, MEDIUM_SUBMARINE)
            cls_ids.append(c)
            prev = c
            bearing += u(rng, (-25, 25))
            pos = destination(*pos, u(rng, cfg["festoon_gc_km"]), bearing)
        for c in cls_ids:
            pop_for(c, bearing + 90)
    sc = _synthetic_wrap(b, "submarine_" + variant, None, "trans_oceanic" if variant != "festoon" else "coastal_regional")
    sc["provenance"]["coordinates"] = "synthetic (A8: not checked against coastlines; no real cable represented)"
    sc["geography"]["coordinate_source"] = "synthetic"
    return sc


# ------------------------------------------------------------------------------------------
def _synthetic_wrap(b: _Builder, family: str, anchor: dict | None, scope: str) -> dict:
    return {
        "family": family,
        "nodes": b.nodes, "edges": b.edges,
        "provenance": {
            "topology_origin": "generated_from_documented_architectural_template",
            "source_dataset": None, "source_topology_id": None,
            "coordinates": "synthetic sites around real anchor city (A7)" if anchor else "synthetic",
            "fiber_connections": "synthetic",
            "fiber_lengths": "synthetic: great-circle x route factor (A2)",
            "equipment": "synthetic_assignment",
            "optical_parameters": "assumed",
        },
        "geography": {
            "scope": scope,
            "anchor_city": None if anchor is None else {k: anchor.get(k) for k in ("name", "country", "lat", "lon", "source_topology")},
            "coordinate_source": "synthetic offsets from Topology Bench anchor city" if anchor else "synthetic",
            "countries": [anchor["country"]] if anchor and anchor.get("country") else [],
        },
        "group_key": None,
    }


# ------------------------------------------------------------------------------------------
# equipment + finalisation (shared by all classes)
# ------------------------------------------------------------------------------------------
def finalise(sc: dict, rng: np.random.Generator, common: dict) -> dict:
    """Relabel nodes S01.. in random order, compute spans/amplifiers, build equipment inventory."""
    perm = rng.permutation(len(sc["nodes"]))
    rename = {sc["nodes"][int(i)]["id"]: f"S{k + 1:02d}" for k, i in enumerate(perm)}
    for n in sc["nodes"]:
        n["id"] = rename[n["id"]]
    sc["nodes"].sort(key=lambda n: n["id"])
    for e in sc["edges"]:
        e["u"], e["v"] = rename[e["u"]], rename[e["v"]]
        if e["u"] > e["v"]:
            e["u"], e["v"] = e["v"], e["u"]
    sc["edges"].sort(key=lambda e: (e["u"], e["v"]))
    for k, e in enumerate(sc["edges"]):
        e["id"] = f"L{k + 1:02d}"

    g = nx.Graph()
    g.add_nodes_from(n["id"] for n in sc["nodes"])
    for e in sc["edges"]:
        g.add_edge(e["u"], e["v"], length=e["length_km"])

    span_t = round(u(rng, common["terrestrial_max_span_km"]), 1)
    span_s = round(u(rng, common["submarine_repeater_spacing_km"]), 1)
    unrep_max = common["unrepeatered_max_km"]
    equipment: list[dict] = []

    def add(eq_type, location, **attrs):
        equipment.append({"equipment_id": f"EQ{len(equipment) + 1:04d}", "type": eq_type,
                          "location": location, **attrs})

    for e in sc["edges"]:
        L = e["length_km"]
        if e["medium"] == MEDIUM_SUBMARINE:
            n_amp = 0 if L <= unrep_max else math.ceil(L / span_s) - 1
            amp_type = "SUBMARINE_REPEATER" if n_amp else None
            e["repeatered"] = bool(n_amp)
            ref = "A4_submarine_repeater"
        else:
            n_amp = max(0, math.ceil(L / span_t) - 1)
            amp_type = "ILA_EDFA" if n_amp else None
            ref = "A3_terrestrial_span"
        e["n_inline_amplifiers"] = n_amp
        e["inline_amplifier_type"] = amp_type
        e["n_spans"] = n_amp + 1
        e["span_length_km"] = round(L / (n_amp + 1), 2)
        for k in range(n_amp):
            add(amp_type, {"edge": e["id"], "position_km_from_u": round((k + 1) * L / (n_amp + 1), 2)},
                assumption=ref)

    deg = dict(g.degree())
    dc_ids = [n["id"] for n in sc["nodes"] if n["role"] == ROLE_DC]
    dist = dict(nx.all_pairs_dijkstra_path_length(g, weight="length")) if dc_ids else {}
    for n in sc["nodes"]:
        nid, role, d = n["id"], n["role"], deg[n["id"]]
        n["degree"] = d
        loc = {"node": nid}
        if role in (ROLE_ROADM, ROLE_HUB_ROADM, ROLE_POP):
            add("ROADM", loc, degree=d, assumption="A9_roadm_degree")
        elif role == ROLE_OADM:
            add("OADM", loc, degree=d, add_drop="fixed_or_colourless", assumption="A9_roadm_degree")
        elif role == ROLE_BU:
            add("BRANCHING_UNIT", loc, ports=d, assumption="A4_submarine_repeater")
            n["terminal_summary"] = None
            continue
        if role == ROLE_CLS:
            add("SLTE", loc, assumption="A6_terminals")
            add("POWER_FEED_EQUIPMENT", loc, assumption="A6_terminals")
        # line amplifiers at line-terminating sites (booster + pre-amp per degree)
        if role != ROLE_CLS:
            for _ in range(d):
                add("EDFA_BOOSTER", loc, assumption="A3_terrestrial_span")
                add("EDFA_PREAMP", loc, assumption="A3_terrestrial_span")
        # terminal equipment
        if role == ROLE_DC:
            reach = max((dist[nid][o] for o in dc_ids if o != nid), default=0.0)
            k = ri(rng, (4, 16))
            if reach <= common["dci_pluggable_reach_km"]:
                ttype, short = "COHERENT_PLUGGABLE_400ZR", "ZR"
            else:
                ttype, short = "COHERENT_TRANSPONDER_ZRPLUS", "TRP"
            add(ttype, loc, count=k, max_dc_path_km=round(reach, 1), assumption="A5_dci_reach")
            add("DWDM_MUX_DEMUX", loc, assumption="A6_terminals")
            n["terminal_summary"] = {"type": ttype, "count": k, "short": short}
        elif role == ROLE_CLS:
            n["terminal_summary"] = {"type": "SLTE", "count": 1, "short": "SLTE"}
        else:
            lo, hi = (2, 10) if role in (ROLE_ROADM, ROLE_HUB_ROADM) else (1, 4)
            k = ri(rng, (lo, hi))
            add("COHERENT_TRANSPONDER", loc, count=k, assumption="A6_terminals")
            n["terminal_summary"] = {"type": "COHERENT_TRANSPONDER", "count": k, "short": "TRM"}

    sc["equipment"] = equipment
    sc["equipment_assumptions"] = {"terrestrial_max_span_km": span_t,
                                   "submarine_repeater_spacing_km": span_s,
                                   "unrepeatered_max_km": unrep_max,
                                   "dci_pluggable_reach_km": common["dci_pluggable_reach_km"]}
    return sc
