"""GNPy physical-layer engine.

Reuses the existing research converter ``integrations/gnpy/full_topology_to_gnpy.py`` (unchanged)
to turn a synthetic ROADM topology into a GNPy network, then runs GNPy's own design +
propagation code (gnpy.tools.worker_utils.designed_network / transmission_simulation) for an
explicit, strictly routed ROADM path and a configured transceiver mode.

Feasibility is ONLY declared from executed GNPy results compared against explicit acceptance
criteria (GNPy remaining margin, which already includes required OSNR, transceiver penalties
and the equipment-library system margin, plus an operator-configured extra margin).
All equipment parameters come from the GNPy example library and are assumptions.
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import logging
import math
import time
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np

from . import topology as topo
from .config import ROOT, SETTINGS

import gnpy
from gnpy.core import elements, exceptions
from gnpy.core.equipment import trx_mode_params
from gnpy.core.parameters import SimParams
from gnpy.core.utils import automatic_nch, dbm2watt, lin2db, watt2dbm
from gnpy.tools.json_io import load_equipments_and_configs, network_from_json
from gnpy.tools.worker_utils import designed_network, transmission_simulation
from gnpy.topology.request import PathRequest, remaining_margin

GNPY_EXAMPLES = Path(gnpy.__file__).resolve().parent / "example-data"
EQPT_CONFIG = GNPY_EXAMPLES / "eqpt_config.json"
REFERENCE_NETWORK = GNPY_EXAMPLES / "edfa_example_network.json"
CONVERTER_PATH = ROOT / "integrations" / "gnpy" / "full_topology_to_gnpy.py"

GNPY_VERSION = getattr(gnpy, "__version__", None)
if GNPY_VERSION is None:
    try:
        from importlib.metadata import version as _v

        GNPY_VERSION = _v("gnpy")
    except Exception:  # pragma: no cover
        GNPY_VERSION = "unknown"


@lru_cache(maxsize=1)
def _converter():
    spec = importlib.util.spec_from_file_location("ondm_full_topology_to_gnpy", CONVERTER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=1)
def equipment_library_raw() -> dict:
    return json.loads(EQPT_CONFIG.read_text(encoding="utf-8"))


def transceiver_catalog() -> list[dict]:
    """Transceiver types/modes in the GNPy example equipment library (assumptions, not vendor data)."""
    out = []
    lib = equipment_library_raw()
    margins = lib["SI"][0].get("sys_margins")
    for trx in lib.get("Transceiver", []):
        for mode in trx.get("mode", []):
            out.append({
                "trx_type": trx["type_variety"],
                "trx_mode": mode["format"],
                "bit_rate_gbps": mode["bit_rate"] / 1e9,
                "baud_rate_gbd": mode["baud_rate"] / 1e9,
                "required_osnr_db_0p1nm": mode["OSNR"],
                "min_spacing_ghz": mode["min_spacing"] / 1e9,
                "tx_osnr_db": mode.get("tx_osnr"),
                "system_margin_db": margins,
            })
    return out


@dataclass
class TransmissionRequirement:
    """Explicitly configured acceptance criteria for a service request."""

    line_rate_gbps: int = 400
    trx_type: str = "Voyager"
    trx_mode: str = "mode 2"          # Voyager 'mode 2' = 400 Gb/s, 66 GBd, req. OSNR 21 dB/0.1nm (example lib)
    extra_margin_db: float = 1.0      # operator margin ON TOP of GNPy system margin + penalties
    channel_power_dbm: float = 0.0
    max_span_km: float = SETTINGS.gnpy_max_span_km
    max_latency_ms: float | None = None

    def describe(self) -> str:
        return (f"{self.line_rate_gbps}G service using GNPy example transceiver '{self.trx_type}' / "
                f"'{self.trx_mode}', {self.channel_power_dbm:+.1f} dBm/ch, fiber links split into spans of at most "
                f"{self.max_span_km:g} km with in-line EDFAs (GNPy autodesign), "
                f"accept if worst-channel GNPy remaining margin >= {self.extra_margin_db:g} dB")


def mode_for_rate(line_rate_gbps: int, trx_type: str | None = None) -> tuple[str, str]:
    for entry in transceiver_catalog():
        if int(entry["bit_rate_gbps"]) == int(line_rate_gbps) and (trx_type is None or entry["trx_type"] == trx_type):
            return entry["trx_type"], entry["trx_mode"]
    raise ValueError(f"No transceiver mode for {line_rate_gbps} Gb/s in the GNPy example equipment library")


# --------------------------------------------------------------------------- conversion
def convert_topology(sample_id: str, max_span_km: float | None = None) -> tuple[dict, dict]:
    """Run the preserved research converter; cache GNPy network + assumptions JSON under simulations/cache."""
    max_span_km = float(max_span_km or SETTINGS.gnpy_max_span_km)
    graph = topo.build_graph(sample_id)
    nodes = sorted(graph.nodes())
    SETTINGS.cache_dir.mkdir(parents=True, exist_ok=True)
    out = SETTINGS.cache_dir / f"{sample_id}_span{int(max_span_km)}.json"
    assumptions_file = out.with_suffix(".assumptions.json")
    src_mtime = topo.graph_path(sample_id).stat().st_mtime
    if not out.exists() or out.stat().st_mtime < max(src_mtime, CONVERTER_PATH.stat().st_mtime):
        args = argparse.Namespace(graph=topo.graph_path(sample_id), reference=REFERENCE_NETWORK, output=out,
                                  source=nodes[0], target=nodes[-1], max_span_km=max_span_km, k_paths=1)
        import contextlib, io

        with contextlib.redirect_stdout(io.StringIO()):
            _converter().convert(args)
    return json.loads(out.read_text(encoding="utf-8")), json.loads(assumptions_file.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- simulation
class _ListHandler(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.WARNING)
        self.records: list[str] = []

    def emit(self, record):
        self.records.append(f"{record.levelname}: {record.getMessage()}")


def _f(value, digits=2):
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return None if not math.isfinite(value) else round(value, digits)


def _arr_stats(arr):
    if arr is None:
        return None, None
    a = np.atleast_1d(np.asarray(arr, dtype=float))
    a = a[np.isfinite(a)]
    if a.size == 0:
        return None, None
    return _f(a.mean()), _f(a.min())


def _element_trace(path) -> list[dict]:
    trace = []
    for el in path:
        row = {"uid": el.uid, "type": type(el).__name__}
        if isinstance(el, elements.Fiber):
            row.update(length_km=_f(el.params.length / 1e3, 1), loss_db=_f(getattr(el, "loss", None)))
        elif isinstance(el, elements.Edfa):
            row.update(type_variety=el.params.type_variety, gain_db=_f(getattr(el, "effective_gain", None)),
                       nf_db=_f(np.mean(el.nf) if getattr(el, "nf", None) is not None else None),
                       pout_dbm=_f(getattr(el, "pout_db", None)))
        elif isinstance(el, elements.Roadm):
            row.update(loss_db=_f(getattr(el, "loss", None)))
        trace.append(row)
    return trace


def _build_request(equipment, source, destination, nodes_list, req: TransmissionRequirement) -> PathRequest:
    si = equipment["SI"]["default"]
    params = {
        "request_id": "ondm",
        "trx_type": req.trx_type,
        "trx_mode": req.trx_mode,
        "source": source,
        "destination": destination,
        "bidir": False,
        "nodes_list": nodes_list,
        "loose_list": ["STRICT"] * len(nodes_list),
        "format": req.trx_mode,
        "path_bandwidth": req.line_rate_gbps * 1e9,
        "effective_freq_slot": None,
        "power": dbm2watt(req.channel_power_dbm),
        "tx_power": dbm2watt(req.channel_power_dbm),
    }
    params.update(trx_mode_params(equipment, req.trx_type, req.trx_mode, True))
    # Channel grid: spacing = transceiver min_spacing; full C-band load between SI f_min/f_max (assumption)
    params["spacing"] = params.get("min_spacing") or si.spacing
    params["f_min"], params["f_max"] = si.f_min, si.f_max
    params["nb_channel"] = automatic_nch(si.f_min, si.f_max, params["spacing"])
    params["power"] = dbm2watt(req.channel_power_dbm)
    params["tx_power"] = dbm2watt(req.channel_power_dbm)
    return PathRequest(**params)


def assess_path(sample_id: str, sites: list[str], requirement: TransmissionRequirement | None = None) -> dict:
    """Run a real GNPy design + propagation over an explicit ROADM site path."""
    requirement = requirement or TransmissionRequirement()
    graph = topo.build_graph(sample_id)
    sites = [str(s) for s in sites]
    ok, why = topo.validate_path(graph, sites)
    result = {
        "sample_id": sample_id, "sites": sites, "requirement": asdict(requirement),
        "requirement_text": requirement.describe(), "gnpy_version": GNPY_VERSION,
        "equipment_library": f"GNPy example-data/{EQPT_CONFIG.name}", "status": "UNDETERMINED",
        "verdict": "UNDETERMINED", "warnings": [],
    }
    if not ok:
        result["error"] = f"Invalid path: {why}"
        return result
    result["route_km"] = topo.path_length_km(graph, sites)

    t0 = time.perf_counter()
    handler = _ListHandler()
    gnpy_logger = logging.getLogger("gnpy")
    gnpy_logger.addHandler(handler)
    try:
        net_json, assumptions = convert_topology(sample_id, requirement.max_span_km)
        equipment = load_equipments_and_configs(EQPT_CONFIG, [], [])
        SimParams.set_params({})
        network = network_from_json(copy.deepcopy(net_json), equipment)
        src, dst = f"Trx_{sites[0]}", f"Trx_{sites[-1]}"
        nodes_list = [f"Roadm_{s}" for s in sites[1:]] + [dst]
        rq = _build_request(equipment, src, dst, nodes_list, requirement)
        import contextlib, io

        with contextlib.redirect_stdout(io.StringIO()):
            network, req, ref_req = designed_network(equipment, network, src, dst, nodes_list=nodes_list,
                                                     loose_list=["STRICT"] * len(nodes_list),
                                                     args_power=requirement.channel_power_dbm, service_req=rq)
            path, _props, _powers, infos = transmission_simulation(equipment, network, req, ref_req)
        if not path:
            raise exceptions.NetworkTopologyError("GNPy returned an empty path")
        roadm_seq = [e.uid.replace("Roadm_", "") for e in path if isinstance(e, elements.Roadm)]
        if roadm_seq != sites:
            result["warnings"].append(f"GNPy path ROADM sequence {roadm_seq} differs from requested {sites}")
        rx = path[-1]
        gsnr_bw_mean, gsnr_bw_min = _arr_stats(rx.snr)
        gsnr01_mean, gsnr01_min = _arr_stats(rx.snr_01nm)
        osnr01_mean, osnr01_min = _arr_stats(rx.osnr_ase_01nm)
        osnr_bw_mean, _ = _arr_stats(rx.osnr_ase)
        margin_mean, margin_min = _arr_stats(remaining_margin(rx))
        amps = [e for e in path if isinstance(e, elements.Edfa)]
        fibers = [e for e in path if isinstance(e, elements.Fiber)]
        result.update({
            "status": "SIMULATED",
            "gsnr_0p1nm_db_mean": gsnr01_mean, "gsnr_0p1nm_db_worst": gsnr01_min,
            "gsnr_signal_bw_db_mean": gsnr_bw_mean, "gsnr_signal_bw_db_worst": gsnr_bw_min,
            "osnr_ase_0p1nm_db_mean": osnr01_mean, "osnr_ase_0p1nm_db_worst": osnr01_min,
            "osnr_ase_signal_bw_db_mean": osnr_bw_mean,
            "required_osnr_db_0p1nm": _f(req.required_osnr_db_01nm),
            "system_margin_db": _f(getattr(rx.params, "system_margin", None)),
            "remaining_margin_db_mean": margin_mean, "remaining_margin_db_worst": margin_min,
            "chromatic_dispersion_ps_nm": _f(np.mean(rx.chromatic_dispersion) if rx.chromatic_dispersion is not None else None, 0),
            "pmd_ps": _f(np.mean(rx.pmd) if rx.pmd is not None else None),
            "pdl_db": _f(np.mean(rx.pdl) if rx.pdl is not None else None),
            "latency_ms": _f(np.mean(rx.latency) if rx.latency is not None else None, 3),
            "num_channels": int(infos.number_of_channels),
            "num_fiber_spans": len(fibers), "num_amplifiers": len(amps),
            "num_inline_amplifiers": sum(1 for a in amps if "ILA" in a.uid),
            "element_trace": _element_trace(path),
        })
        # ---------------- acceptance decision (only from executed results)
        reasons = []
        if margin_min is None:
            verdict = "UNDETERMINED"
            reasons.append("GNPy did not report a remaining margin for this mode")
        elif margin_min < 0:
            verdict = "NOT FEASIBLE"
            reasons.append(f"worst-channel remaining margin {margin_min:.2f} dB < 0 (GNPy: mode does not pass)")
        elif margin_min < requirement.extra_margin_db:
            verdict = "MARGINAL"
            reasons.append(f"passes GNPy ({margin_min:.2f} dB) but below configured extra margin "
                           f"{requirement.extra_margin_db:g} dB")
        else:
            verdict = "FEASIBLE (simulated)"
            reasons.append(f"worst-channel remaining margin {margin_min:.2f} dB >= {requirement.extra_margin_db:g} dB")
        if requirement.max_latency_ms is not None and result["latency_ms"] is not None \
                and result["latency_ms"] > requirement.max_latency_ms:
            verdict = "NOT FEASIBLE"
            reasons.append(f"latency {result['latency_ms']} ms > {requirement.max_latency_ms} ms")
        result["verdict"] = verdict
        result["verdict_reasons"] = reasons
        result["assumptions"] = {k: assumptions[k] for k in (
            "status", "site_semantics", "transceivers", "inline_amplifiers", "fiber", "span_limit_km", "roadm",
            "topology_directionality", "limits") if k in assumptions}
    except Exception as exc:  # report exact limitation instead of hiding it
        result["status"] = "ERROR"
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        gnpy_logger.removeHandler(handler)
        result["warnings"].extend(r for r in handler.records[-20:] if "missing type_variety" not in r)
        result["runtime_s"] = round(time.perf_counter() - t0, 2)
    return result


def compact(result: dict) -> dict:
    """Small dict suitable for VLM context (no per-element trace)."""
    keys = ["sites", "route_km", "status", "verdict", "verdict_reasons", "gsnr_0p1nm_db_worst",
            "gsnr_signal_bw_db_worst", "osnr_ase_0p1nm_db_worst", "required_osnr_db_0p1nm", "system_margin_db",
            "remaining_margin_db_worst", "num_fiber_spans", "num_amplifiers", "latency_ms",
            "chromatic_dispersion_ps_nm", "error"]
    return {k: result.get(k) for k in keys if result.get(k) is not None}
