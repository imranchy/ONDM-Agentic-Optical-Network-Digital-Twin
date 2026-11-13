"""ONDM agent: VLM planning -> code generation -> sandbox execution -> inspection/correction ->
GNPy / NetBox tool calls -> grounded explanation.

Every step is appended to a transparent trace that records WHO produced the information:
  VLM        model inference (planning, code, explanation, diagram reading)
  SANDBOX    isolated execution of VLM-generated code
  VALIDATOR  trusted checks against the ground-truth topology (never replaces generated results)
  GNPY       physical-layer simulation (trusted tool)
  NETBOX     read-only inventory query (trusted tool; or LOCAL FALLBACK, labelled)
  TRUSTED    deterministic fallback graph tool, used ONLY if generated code fails; always labelled
"""
from __future__ import annotations

import json
import time
import traceback
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

import networkx as nx

from . import gnpy_engine, inventory, sandbox
from . import topology as topo
from .config import SETTINGS
from .vlm import VLMBackend, encode_image, extract_code, extract_json

TASKS = ("provisioning", "failure_restoration", "troubleshooting", "general_analysis")

SYSTEM_PROMPT = """You are ONDM-Agent, an optical-network engineering assistant inside a research digital twin.
All topologies, equipment and inventory are SYNTHETIC (not operator telemetry).
Graph vertices are ROADM switching sites; edges are fiber links with lengths in km. In-line amplifiers
sit inside fiber spans; transceivers attach to ROADMs. Be precise and concise. Never invent numbers:
use only values from the provided tool results. A graph path is NOT proof of optical feasibility; only
an executed GNPy simulation compared against stated acceptance criteria can support a feasibility claim."""


@dataclass
class Step:
    actor: str
    title: str
    status: str = "ok"            # ok | error | warning | skipped
    detail: str = ""
    payload: Any = None
    code: str | None = None
    duration_s: float = 0.0


@dataclass
class AgentRun:
    sample_id: str
    request: str
    task: str | None = None
    plan: dict = field(default_factory=dict)
    steps: list[Step] = field(default_factory=list)
    code_attempts: list[dict] = field(default_factory=list)
    code_result: Any = None
    code_status: str = "not_run"   # verified | executed_with_discrepancies | failed | not_executed | not_run
    result_origin: str = ""        # "VLM-generated code (sandbox)" or "TRUSTED fallback tool"
    inventory: dict | None = None
    correlation: dict | None = None
    gnpy: list[dict] = field(default_factory=list)
    highlight: dict = field(default_factory=dict)
    answer: str = ""
    error: str | None = None
    total_s: float = 0.0

    def add(self, step: Step) -> Step:
        self.steps.append(step)
        return step


# ============================================================================ prompts / schemas
PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "task": {"type": "string", "enum": list(TASKS)},
        "source": {"type": ["string", "null"]},
        "target": {"type": ["string", "null"]},
        "failed_link": {"type": ["array", "null"], "items": {"type": "string"}},
        "roadm": {"type": ["string", "null"]},
        "line_rate_gbps": {"type": ["integer", "null"]},
        "k_paths": {"type": ["integer", "null"]},
        "needs_inventory": {"type": "boolean"},
        "needs_gnpy": {"type": "boolean"},
        "diagram_observations": {"type": "string"},
        "plan_steps": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["task", "needs_inventory", "needs_gnpy", "diagram_observations", "plan_steps"],
}

RESULT_SPECS = {
    "provisioning": """Find up to params["k_paths"] loop-free candidate routes from params["source"] to params["target"],
ordered by total distance (edge attribute 'distance_km'). Do NOT use any link listed in params["excluded_links"]
(list of [u, v] pairs, either direction) - those links are unusable according to inventory.
result = {"candidate_paths": [{"path": [site, ...], "distance_km": float, "hops": int}, ...],
          "excluded_links_respected": true, "notes": str}""",
    "failure_restoration": """Simulate failure of link params["failed_link"] = [u, v] on a COPY of G (never modify G itself).
For every unordered pair of sites whose shortest-distance path in the intact network traverses the failed link,
compute the restoration (shortest-distance) path in the failed network, or null if disconnected.
result = {"failed_link": [u, v], "network_still_connected": bool,
          "components_after_failure": [[site, ...], ...],
          "affected_pairs": [{"pair": [s, t], "original_path": [...], "original_km": float,
                              "restoration_path": [...] or null, "restoration_km": float or null}, ...],
          "num_affected_pairs": int, "num_unrestorable_pairs": int}""",
    "troubleshooting": """Analyse ROADM params["roadm"]. params["excluded_links"] lists links unusable according to inventory.
result = {"roadm": str, "degree": int, "neighbors": [{"site": str, "distance_km": float}, ...],
          "is_articulation_point": bool, "bridge_links_at_roadm": [[u, v], ...],
          "usable_degree": int,   # neighbours reachable over links NOT in excluded_links
          "unreachable_sites_with_exclusions": [site, ...],  # sites not reachable from roadm once excluded links are removed
          "farthest_site": {"site": str, "path": [...], "distance_km": float}}  # farthest by shortest distance, using usable links only""",
    "general_analysis": """Answer the engineering request with a graph computation.
result = a JSON-serialisable dict containing the computed values needed to answer the request.""",
}

CODE_CONTRACT = """Write Python code that runs in an isolated sandbox. Contract:
- Pre-defined variables: `G` (networkx.Graph; nodes = ROADM site ids as strings; edge attribute
  'distance_km' (float) and 'weight' (same value)), `nx` (networkx), `topology` (dict), `params` (dict).
- G and params are ALREADY DEFINED: do not rebuild G, do not redefine params, do not hard-code topology data,
  and do not test whether they exist (no locals()/globals()).
- Prefer NetworkX library algorithms (e.g. nx.shortest_simple_paths, nx.dijkstra_path, nx.bridges) over
  hand-written graph search.
- You may import only: networkx, math, itertools, collections, heapq, json, statistics, functools, operator, copy.
- No file, network, OS access, no eval/exec/open/getattr, no dunder attributes.
- Assign the final answer to a variable named `result`. It must be JSON-serialisable
  (use lists, dicts, str, int, float, bool, None; convert tuples/sets to lists).
- Prefer clear, robust code (handle nx.NetworkXNoPath). Return ONLY one ```python code block."""


def _graph_brief(sample_id: str) -> str:
    s = topo.summary(sample_id)
    links = ", ".join(f"{l['a']}-{l['b']}({l['km']:g}km)" for l in s["links"])
    return (f"Topology {sample_id} ({s['topology_type']}): {s['num_sites']} ROADM sites "
            f"{', '.join(s['roadm_sites'])}; {s['num_links']} links: {links}.")


# ============================================================================ agent
class ONDMAgent:
    def __init__(self, vlm: VLMBackend, think: bool = False, max_attempts: int | None = None,
                 prefer_live_inventory: bool = True, on_step: Callable[[Step], None] | None = None):
        self.vlm = vlm
        self.think = think
        self.max_attempts = max_attempts or SETTINGS.max_code_attempts
        self.prefer_live_inventory = prefer_live_inventory
        self.on_step = on_step

    # ---------------------------------------------------------------- helpers
    def _emit(self, run: AgentRun, step: Step) -> Step:
        run.add(step)
        if self.on_step:
            try:
                self.on_step(step)
            except Exception:
                pass
        return step

    def _vlm(self, messages, **kw):
        return self.vlm.chat(messages, think=self.think, **kw)

    # ---------------------------------------------------------------- step 1: plan
    def plan(self, run: AgentRun, hints: dict, use_image: bool = True) -> dict:
        g = topo.build_graph(run.sample_id)
        user = (f"{_graph_brief(run.sample_id)}\n"
                f"Operator request: \"{run.request}\"\n"
                f"UI selections (hints, may be empty): {json.dumps(hints)}\n\n"
                "Look at the attached network diagram and the topology facts. Decide the task type, the "
                "relevant site ids (must be existing ids), whether inventory (NetBox) and physical-layer "
                "simulation (GNPy) are needed, and list 3-6 concrete plan steps. In diagram_observations, "
                "briefly state what you see in the image (topology shape, notable long links) in at most 50 "
                "words. Answer in JSON.")
        msg = {"role": "user", "content": user}
        if use_image:
            msg["images"] = [encode_image(topo.image_path(run.sample_id))]
        t0 = time.perf_counter()
        step = Step("VLM", "Interpret request and diagram -> plan")
        try:
            resp = self._vlm([{"role": "system", "content": SYSTEM_PROMPT}, msg], json_schema=PLAN_SCHEMA,
                             temperature=0.1, max_tokens=1200)
            plan = extract_json(resp.content)
            step.payload = {"plan": plan, "latency_s": resp.latency_s, "image_used": use_image,
                            "tokens": [resp.prompt_tokens, resp.completion_tokens]}
        except Exception as exc:
            plan = {}
            step.status, step.detail = "error", f"{type(exc).__name__}: {exc}"
        step.duration_s = round(time.perf_counter() - t0, 2)
        self._emit(run, step)

        # ---- validate the plan against the graph; UI hints override invalid ids (logged)
        fixes = []
        if plan.get("task") not in TASKS:
            plan["task"] = hints.get("task", "general_analysis")
            fixes.append(f"task -> {plan['task']}")
        for key in ("source", "target", "roadm"):
            val = plan.get(key)
            if hints.get(key) and val != hints[key]:
                if val not in g:
                    fixes.append(f"{key}: model gave {val!r}, using UI selection {hints[key]!r}")
                    plan[key] = hints[key]
                elif hints.get("strict"):
                    fixes.append(f"{key}: model gave {val!r}, UI selection {hints[key]!r} is authoritative")
                    plan[key] = hints[key]
            if plan.get(key) is not None and plan[key] not in g:
                fixes.append(f"{key}: {plan[key]!r} is not a site in {run.sample_id}")
                plan[key] = None
        fl = plan.get("failed_link")
        if hints.get("failed_link") and not g.has_edge(*hints["failed_link"]):
            fixes.append(f"UI failed_link {hints['failed_link']!r} is not a link in {run.sample_id}")
            hints.pop("failed_link")
        if hints.get("failed_link"):
            if not (isinstance(fl, list) and len(fl) == 2 and g.has_edge(*fl)) or \
                    (hints.get("strict") and sorted(fl) != sorted(hints["failed_link"])):
                fixes.append(f"failed_link: model gave {fl!r}, using UI selection {hints['failed_link']!r}")
                plan["failed_link"] = list(hints["failed_link"])
        elif fl and not (isinstance(fl, list) and len(fl) == 2 and g.has_edge(*fl)):
            fixes.append(f"failed_link {fl!r} is not a link")
            plan["failed_link"] = None
        plan["line_rate_gbps"] = plan.get("line_rate_gbps") or hints.get("line_rate_gbps") or 400
        plan["k_paths"] = max(1, min(int(plan.get("k_paths") or hints.get("k_paths") or 3), 5))
        if fixes:
            self._emit(run, Step("VALIDATOR", "Plan validated against topology", "warning", "; ".join(fixes)))
        else:
            self._emit(run, Step("VALIDATOR", "Plan validated against topology", "ok",
                                 "all site ids exist in the topology"))
        run.plan, run.task = plan, plan["task"]
        return plan

    # ---------------------------------------------------------------- step 2: inventory
    def query_inventory(self, run: AgentRun, roadm: str | None = None) -> None:
        t0 = time.perf_counter()
        try:
            inv = inventory.inventory_for(run.sample_id, self.prefer_live_inventory)
            corr = inventory.correlate(run.sample_id, inv)
            run.inventory, run.correlation = inv, corr
            payload = {"source": inv["source"], "note": inv.get("backend_note"),
                       "devices": len(inv["devices"]), "cables": len(inv["cables"]),
                       "findings": corr["findings"], "unusable_links": corr["unusable_links"]}
            if roadm:
                payload["roadm_view"] = inventory.roadm_view(run.sample_id, roadm, inv)
            status = "ok" if inv["source"] == "LIVE NETBOX" else "warning"
            self._emit(run, Step("NETBOX", f"Read-only inventory query ({inv['source']})", status,
                                 f"{len(inv['devices'])} devices, {len(inv['cables'])} cables; "
                                 f"{len(corr['findings'])} correlation findings; unusable links: "
                                 f"{corr['unusable_links'] or 'none'}", payload,
                                 duration_s=round(time.perf_counter() - t0, 2)))
        except Exception as exc:
            self._emit(run, Step("NETBOX", "Inventory query", "error", f"{type(exc).__name__}: {exc}"))

    # ---------------------------------------------------------------- step 3: code gen + exec
    def generate_and_run(self, run: AgentRun, task: str, params: dict,
                         verifier: Callable[[Any], list[str]] | None = None) -> Any:
        spec = RESULT_SPECS[task]
        gb = topo.build_graph(run.sample_id)
        base = (f"{CODE_CONTRACT}\n\nTask: {spec}\n\nparams (already defined) = {json.dumps(params)}\n"
                f"G (already defined) has {gb.number_of_nodes()} sites {sorted(gb.nodes())} and "
                f"{gb.number_of_edges()} links. Operator request: \"{run.request}\"")
        messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": base}]
        controlled = topo.controlled_input(run.sample_id)
        for attempt in range(1, self.max_attempts + 1):
            t0 = time.perf_counter()
            try:
                resp = self._vlm(messages, temperature=0.2 if attempt == 1 else 0.6, max_tokens=1800,
                                 seed=1000 * attempt + len(run.code_attempts))
            except Exception as exc:
                self._emit(run, Step("VLM", f"Generate NetworkX code (attempt {attempt})", "error",
                                     f"{type(exc).__name__}: {exc}"))
                run.code_status = "failed"
                return None
            code = extract_code(resp.content)
            gen_step = Step("VLM", f"Generate NetworkX code (attempt {attempt})",
                            "ok" if code else "error",
                            f"{resp.completion_tokens} tokens in {resp.latency_s}s" if code else
                            "no python code block in model output", code=code,
                            payload=None if code else resp.content[:1500], duration_s=resp.latency_s)
            self._emit(run, gen_step)
            if not code:
                messages += [{"role": "assistant", "content": resp.content},
                             {"role": "user", "content": "Return the solution as one ```python code block."}]
                run.code_attempts.append({"attempt": attempt, "code": None, "status": "NO_CODE"})
                continue
            ex = sandbox.run_code(code, controlled, params)
            problems: list[str] = []
            if ex.status == "OK" and verifier:
                try:
                    problems = verifier(ex.result)
                except Exception as vexc:
                    problems = [f"result has unexpected structure: {type(vexc).__name__}: {vexc}"]
            status = "ok" if ex.status == "OK" and not problems else ("warning" if ex.status == "OK" else "error")
            self._emit(run, Step("SANDBOX", f"Execute generated code (attempt {attempt})", status,
                                 f"{ex.status} in {ex.runtime_s}s" + (f": {ex.error}" if ex.error else ""),
                                 {"result": ex.result, "stdout": ex.stdout, "traceback": ex.traceback,
                                  "isolation": ex.isolation}, duration_s=ex.runtime_s))
            if problems:
                self._emit(run, Step("VALIDATOR", f"Inspect result (attempt {attempt})", "warning",
                                     "; ".join(problems[:6])))
            elif ex.status == "OK":
                self._emit(run, Step("VALIDATOR", f"Inspect result (attempt {attempt})", "ok",
                                     "result structure and values consistent with ground-truth topology"))
            run.code_attempts.append({"attempt": attempt, "code": code, "status": ex.status, "error": ex.error,
                                      "problems": problems})
            if ex.status == "NOT_EXECUTED":
                run.code_status = "not_executed"
                return None
            if ex.status == "OK" and not problems:
                run.code_status, run.code_result = "verified", ex.result
                run.result_origin = "VLM-generated code (sandbox)"
                return ex.result
            if ex.status == "VALIDATION_ERROR":
                feedback = (f"Your code was REJECTED by the sandbox security policy before running: {ex.error}. "
                            "Remove those constructs entirely and rewrite the code (G, params and nx are already "
                            "defined; only allowed imports; assign `result`).")
            else:
                feedback = (f"Execution status: {ex.status}. Error: {ex.error}\n{(ex.traceback or '')[-1200:]}\n"
                            f"{_error_lines(code, ex.traceback)}\n{_api_hint(ex.error)}"
                            if ex.status != "OK" else
                        "The code ran but the result failed inspection:\n- " + "\n- ".join(problems[:8]))
            if ex.status == "OK" and attempt == self.max_attempts:
                run.code_status, run.code_result = "executed_with_discrepancies", ex.result
                run.result_origin = "VLM-generated code (sandbox) - discrepancies flagged"
                return ex.result
            messages += [{"role": "assistant", "content": f"```python\n{code}\n```"},
                         {"role": "user", "content": feedback + "\nFix the code. Return one ```python block."}]
        run.code_status = "failed"
        return None

    # ---------------------------------------------------------------- step 4: GNPy
    def run_gnpy(self, run: AgentRun, paths: list[list[str]], requirement: gnpy_engine.TransmissionRequirement,
                 label: str = "candidate") -> None:
        for p in paths:
            t0 = time.perf_counter()
            res = gnpy_engine.assess_path(run.sample_id, p, requirement)
            res["label"] = label
            run.gnpy.append(res)
            status = {"SIMULATED": "ok", "ERROR": "error"}.get(res["status"], "warning")
            detail = (f"{'-'.join(p)} ({res.get('route_km', 0):g} km): {res['verdict']}; worst GSNR(0.1nm) "
                      f"{res.get('gsnr_0p1nm_db_worst')} dB, margin {res.get('remaining_margin_db_worst')} dB"
                      if res["status"] == "SIMULATED" else res.get("error", res["status"]))
            self._emit(run, Step("GNPY", f"GNPy simulation @ {requirement.line_rate_gbps}G ({label})", status, detail,
                                 gnpy_engine.compact(res), duration_s=round(time.perf_counter() - t0, 2)))

    # ---------------------------------------------------------------- step 5: explanation
    def explain(self, run: AgentRun, evidence: dict) -> str:
        prompt = (f"Operator request: \"{run.request}\"\nTopology: {_graph_brief(run.sample_id)}\n\n"
                  f"Evidence (JSON from executed tools; the only facts you may use):\n"
                  f"{json.dumps(evidence, default=str)[:9000]}\n\n"
                  "Write the engineering answer in Markdown with these sections:\n"
                  "**Findings** (direct answer), **Evidence** (cite the numbers above, say which tool produced "
                  "them), **Assumptions & limitations** (synthetic data, GNPy example equipment, etc.), "
                  "**Recommendation**. Keep it under 250 words. Feasibility statements must match the GNPy "
                  "verdicts exactly; if GNPy was not run, say feasibility is not established.")
        t0 = time.perf_counter()
        try:
            resp = self._vlm([{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
                             temperature=0.3, max_tokens=900)
            answer = resp.content.strip()
            self._emit(run, Step("VLM", "Explain results", "ok", f"{resp.completion_tokens} tokens",
                                 duration_s=resp.latency_s))
        except Exception as exc:
            answer = f"_VLM explanation unavailable ({type(exc).__name__}: {exc}). See evidence panels._"
            self._emit(run, Step("VLM", "Explain results", "error", str(exc),
                                 duration_s=round(time.perf_counter() - t0, 2)))
        run.answer = answer
        return answer

    # ============================================================ workflows
    def run_workflow(self, sample_id: str, request: str, hints: dict | None = None,
                     requirement: gnpy_engine.TransmissionRequirement | None = None,
                     use_image: bool = True) -> AgentRun:
        hints = dict(hints or {})
        run = AgentRun(sample_id=sample_id, request=request)
        t0 = time.perf_counter()
        try:
            plan = self.plan(run, hints, use_image=use_image)
            task = plan["task"]
            if hints.get("task") and hints.get("strict") and task != hints["task"]:
                self._emit(run, Step("VALIDATOR", "Task type", "warning",
                                     f"model chose {task!r}; demo scenario requires {hints['task']!r}"))
                task = run.task = plan["task"] = hints["task"]
            requirement = requirement or gnpy_engine.TransmissionRequirement()
            if plan.get("line_rate_gbps") and plan["line_rate_gbps"] != requirement.line_rate_gbps:
                try:
                    tt, tm = gnpy_engine.mode_for_rate(plan["line_rate_gbps"])
                    requirement.line_rate_gbps, requirement.trx_type, requirement.trx_mode = \
                        plan["line_rate_gbps"], tt, tm
                except ValueError as exc:
                    self._emit(run, Step("VALIDATOR", "Line rate", "warning", str(exc)))
            handler = {"provisioning": self._provisioning, "failure_restoration": self._failure,
                       "troubleshooting": self._troubleshooting}.get(task, self._general)
            handler(run, plan, requirement)
        except Exception as exc:
            run.error = f"{type(exc).__name__}: {exc}"
            self._emit(run, Step("AGENT", "Unhandled error", "error", traceback.format_exc()[-2000:]))
        run.total_s = round(time.perf_counter() - t0, 2)
        return run

    # ---------------------------------------------------------------- BC1
    def _provisioning(self, run: AgentRun, plan: dict, req) -> None:
        g = topo.build_graph(run.sample_id)
        src, dst = plan.get("source"), plan.get("target")
        if not src or not dst or src == dst:
            run.error = "Provisioning needs two distinct existing ROADM sites."
            self._emit(run, Step("VALIDATOR", "Endpoints", "error", run.error))
            return
        self.query_inventory(run)
        excluded = (run.correlation or {}).get("unusable_links", [])
        params = {"source": src, "target": dst, "k_paths": plan["k_paths"], "excluded_links": excluded,
                  "line_rate_gbps": req.line_rate_gbps}
        ex_set = {tuple(sorted(l)) for l in excluded}

        gu = _without(g, ex_set)
        truth = _trusted_k_paths(gu, src, dst, plan["k_paths"])

        def verify(res):
            probs = []
            paths = res["candidate_paths"]
            if not isinstance(paths, list) or not paths:
                if truth:
                    probs.append("no candidate paths returned although a usable path exists")
                return probs
            seqs = [tuple(map(str, c["path"])) for c in paths]
            if len(set(seqs)) != len(seqs):
                probs.append("duplicate paths returned; candidate routes must be distinct")
            if len(paths) < len(truth):
                probs.append(f"only {len(paths)} distinct route(s) returned but {len(truth)} usable loop-free "
                             f"routes exist (k={plan['k_paths']})")
            if truth and paths:
                best = topo.path_length_km(g, truth[0])
                try:
                    got = min(topo.path_length_km(g, list(s)) for s in seqs if topo.validate_path(g, list(s))[0])
                    if got - best > 0.5:
                        probs.append(f"shortest returned route is {got:g} km but a shorter usable route exists")
                except ValueError:
                    pass
            for c in paths:
                p = [str(x) for x in c["path"]]
                ok, why = topo.validate_path(g, p)
                if not ok:
                    probs.append(f"path {p}: {why}")
                    continue
                if p[0] != src or p[-1] != dst:
                    probs.append(f"path {p} does not go from {src} to {dst}")
                true_km = topo.path_length_km(g, p)
                if abs(float(c.get("distance_km", -1)) - true_km) > 0.5:
                    probs.append(f"path {p}: reported {c.get('distance_km')} km, actual {true_km:g} km")
                used = {tuple(sorted(e)) for e in zip(p, p[1:])}
                if used & ex_set:
                    probs.append(f"path {p} uses excluded link(s) {sorted(used & ex_set)}")
            return probs

        result = self.generate_and_run(run, "provisioning", params, verify)
        paths = []
        if result:
            for c in result.get("candidate_paths", [])[: plan["k_paths"]]:
                p = [str(x) for x in c["path"]]
                if topo.validate_path(g, p)[0]:
                    paths.append(p)
        if not paths and run.code_status in ("failed", "not_executed"):
            paths = _trusted_k_paths(_without(g, ex_set), src, dst, plan["k_paths"])
            run.result_origin = "TRUSTED fallback tool (generated code failed)"
            self._emit(run, Step("TRUSTED", "Fallback k-shortest paths (NOT generated code)", "warning",
                                 f"{len(paths)} paths", paths))
        uniq = []
        for p in paths:
            if p not in uniq:
                uniq.append(p)
        paths = uniq
        run.highlight = {"paths": paths, "excluded_links": excluded, "endpoints": [src, dst]}
        if paths:
            self.run_gnpy(run, paths, req)
            self._rate_fallback(run, req)
        self.explain(run, {
            "request_type": "service provisioning", "source": src, "target": dst,
            "transmission_requirement": req.describe(),
            "inventory_source": (run.inventory or {}).get("source"),
            "inventory_unusable_links_excluded": excluded,
            "inventory_findings_at_endpoints": [f for f in (run.correlation or {}).get("findings", [])
                                                if f.get("object") in (src, dst) or src in str(f.get("object"))
                                                or dst in str(f.get("object"))],
            "routing_result_origin": run.result_origin, "routing_code_status": run.code_status,
            "candidate_routes": [{"sites": p, "km": topo.path_length_km(g, p)} for p in paths],
            "gnpy_results": [gnpy_engine.compact(r) for r in run.gnpy if r.get("label") == "candidate"],
            "gnpy_lower_rate_alternatives": [{"line_rate_gbps": r["requirement"]["line_rate_gbps"],
                                              **gnpy_engine.compact(r)} for r in run.gnpy
                                             if r.get("label") == "lower-rate alternative"],
        })

    def _rate_fallback(self, run: AgentRun, req) -> None:
        """If no candidate passes at the requested rate, simulate lower-rate modes on the shortest route."""
        cands = [r for r in run.gnpy if r.get("label") == "candidate" and r["status"] == "SIMULATED"]
        if not cands or any(r["verdict"].startswith("FEASIBLE") for r in cands):
            return
        best = min(cands, key=lambda r: r.get("route_km", 1e9))
        for rate in (300, 200, 100):
            if rate >= req.line_rate_gbps:
                continue
            try:
                tt, tm = gnpy_engine.mode_for_rate(rate, req.trx_type)
            except ValueError:
                try:
                    tt, tm = gnpy_engine.mode_for_rate(rate)
                except ValueError:
                    continue
            alt = gnpy_engine.TransmissionRequirement(line_rate_gbps=rate, trx_type=tt, trx_mode=tm,
                                                      extra_margin_db=req.extra_margin_db,
                                                      channel_power_dbm=req.channel_power_dbm,
                                                      max_span_km=req.max_span_km)
            self.run_gnpy(run, [best["sites"]], alt, label="lower-rate alternative")
            if run.gnpy[-1]["verdict"].startswith("FEASIBLE"):
                break

    # ---------------------------------------------------------------- BC2
    def _failure(self, run: AgentRun, plan: dict, req) -> None:
        g = topo.build_graph(run.sample_id)
        fl = plan.get("failed_link")
        if not fl:
            run.error = "Failure analysis needs an existing link."
            self._emit(run, Step("VALIDATOR", "Failed link", "error", run.error))
            return
        u, v = fl
        if plan.get("needs_inventory", True):
            self.query_inventory(run)
        params = {"failed_link": [u, v]}
        gf = g.copy()
        gf.remove_edge(u, v)

        def verify(res):
            probs = []
            if bool(res["network_still_connected"]) != nx.is_connected(gf):
                probs.append(f"network_still_connected should be {nx.is_connected(gf)}")
            n_true = _affected_pairs_count(g, u, v)
            if int(res["num_affected_pairs"]) != n_true and len(res["affected_pairs"]) != n_true:
                probs.append(f"expected {n_true} affected site pairs (shortest path uses {u}-{v}), "
                             f"got {res['num_affected_pairs']}")
            for ap in res["affected_pairs"][:50]:
                rp = ap.get("restoration_path")
                s, t = [str(x) for x in ap["pair"]]
                if rp:
                    rp = [str(x) for x in rp]
                    ok, why = topo.validate_path(gf, rp)
                    if not ok:
                        probs.append(f"restoration path {rp}: {why} (in failed network)")
                    elif abs(float(ap.get("restoration_km") or -1) - topo.path_length_km(gf, rp)) > 0.5:
                        probs.append(f"restoration km for {s}-{t} incorrect")
                    elif {rp[0], rp[-1]} != {s, t}:
                        probs.append(f"restoration path {rp} endpoints do not match pair {s}-{t}")
                elif nx.has_path(gf, s, t):
                    probs.append(f"pair {s}-{t} marked unrestorable but a path exists")
            return probs

        result = self.generate_and_run(run, "failure_restoration", params, verify)
        if result is None and run.code_status in ("failed", "not_executed"):
            result = _trusted_failure(g, u, v)
            run.result_origin = "TRUSTED fallback tool (generated code failed)"
            self._emit(run, Step("TRUSTED", "Fallback failure analysis (NOT generated code)", "warning",
                                 f"{result['num_affected_pairs']} affected pairs", result))
        affected = (result or {}).get("affected_pairs", [])
        restor = [ap for ap in affected if ap.get("restoration_path")]
        restor.sort(key=lambda ap: -(ap.get("restoration_km") or 0))
        gnpy_paths = []
        for ap in restor:
            p = [str(x) for x in ap["restoration_path"]]
            if topo.validate_path(gf, p)[0] and p not in gnpy_paths:
                gnpy_paths.append(p)
            if len(gnpy_paths) >= 3:
                break
        run.highlight = {"failed_link": [u, v], "paths": gnpy_paths,
                         "unrestorable": [ap["pair"] for ap in affected if not ap.get("restoration_path")]}
        failed_cable = None
        if run.inventory:
            for c in run.inventory["cables"]:
                if c.get("label") in (f"{run.sample_id} {u}-{v}", f"{run.sample_id} {v}-{u}"):
                    failed_cable = {k: c.get(k) for k in ("label", "status", "length", "length_unit",
                                                          "a_device", "a_interface", "b_device", "b_interface",
                                                          "description")}
        if gnpy_paths:  # physical check of restoration routes always runs (cheap); plan flag is advisory
            self.run_gnpy(run, gnpy_paths, req, label="restoration")
        self.explain(run, {
            "request_type": "fiber failure and restoration", "failed_link": [u, v],
            "failed_link_km": g[u][v]["distance_km"], "failed_cable_inventory_record": failed_cable,
            "analysis_origin": run.result_origin, "code_status": run.code_status,
            "network_still_connected": (result or {}).get("network_still_connected"),
            "num_affected_pairs": (result or {}).get("num_affected_pairs"),
            "num_unrestorable_pairs": (result or {}).get("num_unrestorable_pairs"),
            "affected_pairs_sample": affected[:8],
            "longest_restoration_paths_simulated": [gnpy_engine.compact(r) for r in run.gnpy],
            "transmission_requirement": req.describe(),
        })

    # ---------------------------------------------------------------- BC3
    def _troubleshooting(self, run: AgentRun, plan: dict, req) -> None:
        g = topo.build_graph(run.sample_id)
        node = plan.get("roadm")
        if not node:
            run.error = "Troubleshooting needs an existing ROADM site."
            self._emit(run, Step("VALIDATOR", "ROADM", "error", run.error))
            return
        self.query_inventory(run, roadm=node)
        excluded = (run.correlation or {}).get("unusable_links", [])
        ex_set = {tuple(sorted(l)) for l in excluded}
        params = {"roadm": node, "excluded_links": excluded}
        gu = _without(g, ex_set)

        def verify(res):
            probs = []
            if int(res["degree"]) != g.degree(node):
                probs.append(f"degree should be {g.degree(node)}")
            if bool(res["is_articulation_point"]) != (node in set(nx.articulation_points(g))):
                probs.append("is_articulation_point incorrect")
            if int(res["usable_degree"]) != gu.degree(node):
                probs.append(f"usable_degree should be {gu.degree(node)} after removing excluded links")
            reach = nx.node_connected_component(gu, node)
            unreachable = sorted(set(g) - reach)
            if sorted(map(str, res.get("unreachable_sites_with_exclusions") or [])) != unreachable:
                probs.append(f"unreachable_sites_with_exclusions should be {unreachable}")
            fs = res.get("farthest_site") or {}
            if fs.get("path"):
                p = [str(x) for x in fs["path"]]
                ok, why = topo.validate_path(gu, p)
                if not ok:
                    probs.append(f"farthest_site path {p}: {why} (usable links only)")
                else:
                    d = nx.single_source_dijkstra_path_length(gu, node, weight="distance_km")
                    if abs(topo.path_length_km(g, p) - max(d.values())) > 0.5:
                        probs.append(f"farthest site distance should be {max(d.values()):g} km")
            return probs

        result = self.generate_and_run(run, "troubleshooting", params, verify)
        if result is None and run.code_status in ("failed", "not_executed"):
            result = _trusted_troubleshoot(g, gu, node)
            run.result_origin = "TRUSTED fallback tool (generated code failed)"
            self._emit(run, Step("TRUSTED", "Fallback ROADM analysis (NOT generated code)", "warning", "", result))
        paths = []
        fs = (result or {}).get("farthest_site") or {}
        if fs.get("path") and topo.validate_path(gu, [str(x) for x in fs["path"]])[0]:
            paths.append([str(x) for x in fs["path"]])
        run.highlight = {"roadm": node, "excluded_links": excluded, "paths": paths}
        if paths:  # always simulate the farthest-site path
            self.run_gnpy(run, paths, req, label="farthest reachable site")
        rv = inventory.roadm_view(run.sample_id, node, run.inventory) if run.inventory else None
        self.explain(run, {
            "request_type": "inventory-aware ROADM troubleshooting", "roadm": node,
            "inventory_source": (run.inventory or {}).get("source"),
            "roadm_inventory": {"degree_ports_installed_on_device": rv["degree_ports_total"],
                                "degree_ports_with_fiber_cable": rv["degree_ports_used"],
                                "disabled_interfaces": rv["disabled_interfaces"],
                                "devices_at_site": rv["devices_at_site"]} if rv else None,
            "inventory_findings_for_roadm_or_its_links": [
                f for f in (run.correlation or {}).get("findings", [])
                if node == f.get("object") or node in (f.get("link") or []) or f"-{node}" in str(f.get("object"))],
            "network_wide_unusable_links": excluded,
            "graph_analysis_origin": run.result_origin, "graph_analysis": result,
            "gnpy_farthest_site": [gnpy_engine.compact(r) for r in run.gnpy],
            "transmission_requirement": req.describe(),
        })

    # ---------------------------------------------------------------- general
    def _general(self, run: AgentRun, plan: dict, req) -> None:
        result = self.generate_and_run(run, "general_analysis", {k: plan.get(k) for k in
                                                                 ("source", "target", "roadm", "failed_link")})
        self.explain(run, {"request_type": "general analysis", "code_status": run.code_status,
                           "computed_result": result})

    # ============================================================ diagram reading
    def read_diagram(self, sample_id: str) -> dict:
        """VLM reads the diagram image only; result compared with ground truth by the validator."""
        schema = {"type": "object", "properties": {
            "nodes": {"type": "array", "items": {"type": "string"}},
            "links": {"type": "array", "items": {"type": "object", "properties": {
                "a": {"type": "string"}, "b": {"type": "string"}, "km": {"type": "number"}},
                "required": ["a", "b", "km"]}},
            "topology_type": {"type": "string"}}, "required": ["nodes", "links", "topology_type"]}
        msg = {"role": "user", "images": [encode_image(topo.image_path(sample_id), 1280)],
               "content": "This is an optical network diagram. Nodes are ROADM sites labelled with letters. "
                          "List every node label, every fiber link with its distance label in km, and the "
                          "topology type (ring, star, mesh, tree, hybrid or random). Answer in JSON."}
        resp = self.vlm.chat([msg], json_schema=schema, temperature=0.0, think=False)
        pred = extract_json(resp.content)
        g = topo.build_graph(sample_id)
        true_e = {tuple(sorted((u, v))): d["distance_km"] for u, v, d in g.edges(data=True)}
        pred_e = {}
        for l in pred.get("links", []):
            try:
                pred_e[tuple(sorted((str(l["a"]), str(l["b"]))))] = float(l["km"])
            except Exception:
                continue
        tp = set(true_e) & set(pred_e)
        km_ok = sum(1 for e in tp if abs(true_e[e] - pred_e[e]) < 0.5)
        pn, tn = set(map(str, pred.get("nodes", []))), set(g.nodes())
        return {
            "prediction": pred, "latency_s": resp.latency_s,
            "nodes_correct": len(pn & tn), "nodes_true": len(tn), "nodes_predicted": len(pn),
            "links_correct": len(tp), "links_true": len(true_e), "links_predicted": len(pred_e),
            "link_km_correct": km_ok,
            "missed_links": sorted(set(true_e) - set(pred_e)), "spurious_links": sorted(set(pred_e) - set(true_e)),
            "topology_type_true": g.graph.get("topology_type"),
            "note": "Single-sample check against ground truth; not a benchmark result.",
        }


def _error_lines(code: str, tb: str | None) -> str:
    """Map '<generated>' traceback line numbers back to source so the model sees the faulty statement."""
    import re

    if not tb:
        return ""
    lines = code.splitlines()
    out = []
    for n in re.findall(r'File "<generated>", line (\d+)', tb):
        i = int(n)
        if 1 <= i <= len(lines):
            out.append(f"  line {i}: {lines[i - 1].strip()}")
    if not out:
        return ""
    return ("The error was raised at these lines of YOUR code (innermost last):\n" + "\n".join(out[-4:]) +
            "\nCheck the data types of the variables used on these lines.")


def _api_hint(error: str | None) -> str:
    """For hallucinated networkx attributes, suggest real names from the networkx namespace."""
    import difflib
    import re

    if not error:
        return ""
    m = re.search(r"module 'networkx' has no attribute '(\w+)'", error) or \
        re.search(r"'Graph' object has no attribute '(\w+)'", error)
    if not m:
        if re.search(r"KeyError: -?\d+$", error.strip()):
            return ("KeyError with an integer usually means a dict was indexed by position (e.g. entry[0] on a "
                    "dict like {'path': [...]}). Use the dict key (entry['path']) or iterate over the list itself.")
        if "unhashable type: 'list'" in error:
            return "Lists cannot be set members or dict keys; convert them with tuple(...) or sorted(...) first."
        return ""
    pool = dir(nx) if "module" in m.group(0) else dir(nx.Graph)
    close = difflib.get_close_matches(m.group(1), [n for n in pool if not n.startswith("_")], n=5, cutoff=0.5)
    return f"'{m.group(1)}' does not exist. Real NetworkX names that may be what you need: {close}." if close else ""


# ============================================================================ trusted fallbacks
def _without(g: nx.Graph, ex_set: set) -> nx.Graph:
    h = g.copy()
    h.remove_edges_from([e for e in list(h.edges()) if tuple(sorted(e)) in ex_set])
    return h


def _trusted_k_paths(g, s, t, k):
    from itertools import islice

    try:
        return [list(p) for p in islice(nx.shortest_simple_paths(g, s, t, weight="distance_km"), k)]
    except nx.NetworkXNoPath:
        return []


def _affected_pairs_count(g, u, v) -> int:
    n = 0
    paths = dict(nx.all_pairs_dijkstra_path(g, weight="distance_km"))
    nodes = sorted(g.nodes())
    for i, s in enumerate(nodes):
        for t in nodes[i + 1:]:
            p = paths[s][t]
            if any({a, b} == {u, v} for a, b in zip(p, p[1:])):
                n += 1
    return n


def _trusted_failure(g, u, v) -> dict:
    gf = g.copy()
    gf.remove_edge(u, v)
    paths = dict(nx.all_pairs_dijkstra_path(g, weight="distance_km"))
    nodes = sorted(g.nodes())
    affected = []
    for i, s in enumerate(nodes):
        for t in nodes[i + 1:]:
            p = paths[s][t]
            if any({a, b} == {u, v} for a, b in zip(p, p[1:])):
                try:
                    rp = nx.dijkstra_path(gf, s, t, weight="distance_km")
                    rk = topo.path_length_km(gf, rp)
                except nx.NetworkXNoPath:
                    rp, rk = None, None
                affected.append({"pair": [s, t], "original_path": p, "original_km": topo.path_length_km(g, p),
                                 "restoration_path": rp, "restoration_km": rk})
    return {"failed_link": [u, v], "network_still_connected": nx.is_connected(gf),
            "components_after_failure": [sorted(c) for c in nx.connected_components(gf)],
            "affected_pairs": affected, "num_affected_pairs": len(affected),
            "num_unrestorable_pairs": sum(1 for a in affected if not a["restoration_path"])}


def _trusted_troubleshoot(g, gu, node) -> dict:
    d, p = nx.single_source_dijkstra(gu, node, weight="distance_km")
    far = max(d, key=d.get)
    return {"roadm": node, "degree": g.degree(node),
            "neighbors": [{"site": n, "distance_km": g[node][n]["distance_km"]} for n in g[node]],
            "is_articulation_point": node in set(nx.articulation_points(g)),
            "bridge_links_at_roadm": [list(b) for b in nx.bridges(g) if node in b],
            "usable_degree": gu.degree(node),
            "unreachable_sites_with_exclusions": sorted(set(g) - nx.node_connected_component(gu, node)),
            "farthest_site": {"site": far, "path": p[far], "distance_km": d[far]}}


# ============================================================================ free-form tool-calling chat
CHAT_TOOLS = [
    {"type": "function", "function": {
        "name": "execute_networkx_code",
        "description": "Execute Python/NetworkX code you write in an isolated sandbox on the selected topology. "
                       "Variables G (networkx.Graph, edge attr distance_km), nx, topology, params are pre-defined. "
                       "Assign the answer to `result` (JSON-serialisable). Returns the result or the error.",
        "parameters": {"type": "object", "properties": {
            "code": {"type": "string", "description": "Python source code"},
            "purpose": {"type": "string"}}, "required": ["code"]}}},
    {"type": "function", "function": {
        "name": "gnpy_assess_path",
        "description": "Run a GNPy physical-layer simulation for an explicit ROADM site path and line rate. "
                       "Returns GSNR/OSNR, remaining margin and a verdict against configured criteria.",
        "parameters": {"type": "object", "properties": {
            "sites": {"type": "array", "items": {"type": "string"}},
            "line_rate_gbps": {"type": "integer", "enum": [100, 200, 300, 400]}}, "required": ["sites"]}}},
    {"type": "function", "function": {
        "name": "netbox_inventory",
        "description": "Read-only inventory query (NetBox, or labelled local fallback). kind='roadm' needs site; "
                       "kind='findings' returns inventory/topology correlation issues; kind='cables' lists cables.",
        "parameters": {"type": "object", "properties": {
            "kind": {"type": "string", "enum": ["roadm", "findings", "cables"]},
            "site": {"type": "string"}}, "required": ["kind"]}}},
]


def chat_turn(vlm: VLMBackend, sample_id: str, history: list[dict], user_text: str, *, attach_image: bool,
              think: bool = False, prefer_live_inventory: bool = True, max_tool_calls: int = 6,
              on_step: Callable[[Step], None] | None = None) -> tuple[str, list[Step], list[dict]]:
    """One user turn with native tool calling. Returns (answer, steps, updated_history)."""
    steps: list[Step] = []

    def emit(s: Step):
        steps.append(s)
        if on_step:
            try:
                on_step(s)
            except Exception:
                pass

    sys_msg = {"role": "system", "content": SYSTEM_PROMPT + "\n" + _graph_brief(sample_id) +
               "\nUse tools for any computation, inventory or physical-layer question; write NetworkX code "
               "yourself with execute_networkx_code. Explain results with the numbers returned by tools."}
    msgs = [sys_msg] + history
    um = {"role": "user", "content": user_text}
    if attach_image:
        um["images"] = [encode_image(topo.image_path(sample_id))]
    msgs.append(um)
    new_hist = history + [{"role": "user", "content": user_text}]
    controlled = topo.controlled_input(sample_id)
    inv_cache = {}
    for _ in range(max_tool_calls + 1):
        resp = vlm.chat(msgs, tools=CHAT_TOOLS, think=think, temperature=0.2)
        emit(Step("VLM", "Reason / choose tool" if resp.tool_calls else "Answer", "ok",
                  f"{resp.completion_tokens} tokens", duration_s=resp.latency_s))
        if not resp.tool_calls:
            new_hist.append({"role": "assistant", "content": resp.content})
            return resp.content, steps, new_hist
        msgs.append({"role": "assistant", "content": resp.content, "tool_calls": resp.tool_calls})
        for tc in resp.tool_calls:
            fn = tc.get("function", {})
            name, args = fn.get("name"), fn.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}
            t0 = time.perf_counter()
            try:
                if name == "execute_networkx_code":
                    ex = sandbox.run_code(args.get("code", ""), controlled, {})
                    out = {"status": ex.status, "result": ex.result, "error": ex.error,
                           "traceback": (ex.traceback or "")[-800:]}
                    emit(Step("SANDBOX", f"execute_networkx_code: {args.get('purpose', '')}"[:90],
                              "ok" if ex.status == "OK" else "error", ex.status + (f": {ex.error}" if ex.error else ""),
                              {"result": ex.result}, code=args.get("code"), duration_s=ex.runtime_s))
                elif name == "gnpy_assess_path":
                    rate = int(args.get("line_rate_gbps") or 400)
                    tt, tm = gnpy_engine.mode_for_rate(rate)
                    r = gnpy_engine.assess_path(sample_id, args.get("sites", []),
                                                gnpy_engine.TransmissionRequirement(line_rate_gbps=rate,
                                                                                    trx_type=tt, trx_mode=tm))
                    out = gnpy_engine.compact(r)
                    emit(Step("GNPY", f"gnpy_assess_path {'-'.join(map(str, args.get('sites', [])))} @ {rate}G",
                              "ok" if r["status"] == "SIMULATED" else "error", r.get("verdict", ""), out,
                              duration_s=round(time.perf_counter() - t0, 2)))
                elif name == "netbox_inventory":
                    if "inv" not in inv_cache:
                        inv_cache["inv"] = inventory.inventory_for(sample_id, prefer_live_inventory)
                    inv = inv_cache["inv"]
                    kind = args.get("kind")
                    if kind == "roadm":
                        out = inventory.roadm_view(sample_id, str(args.get("site")), inv)
                    elif kind == "findings":
                        out = inventory.correlate(sample_id, inv)
                    else:
                        out = {"source": inv["source"], "cables": inv["cables"]}
                    emit(Step("NETBOX", f"netbox_inventory kind={kind} site={args.get('site')}", "ok",
                              inv["source"], out, duration_s=round(time.perf_counter() - t0, 2)))
                else:
                    out = {"error": f"unknown tool {name}"}
            except Exception as exc:
                out = {"error": f"{type(exc).__name__}: {exc}"}
                emit(Step("AGENT", f"tool {name} failed", "error", out["error"]))
            msgs.append({"role": "tool", "tool_name": name, "content": json.dumps(out, default=str)[:6000]})
    msgs.append({"role": "user", "content": "Tool budget exhausted. Answer now with what you have."})
    resp = vlm.chat(msgs, think=think, temperature=0.2)
    new_hist.append({"role": "assistant", "content": resp.content})
    return resp.content, steps, new_hist
