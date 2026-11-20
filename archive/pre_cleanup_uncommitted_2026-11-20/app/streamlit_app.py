"""ONDM Agentic Optical Network Digital Twin — Streamlit NOC console (research prototype).

Run (Windows):  .venv\\Scripts\\streamlit run app\\streamlit_app.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ondm import gnpy_engine, inventory, sandbox  # noqa: E402
from ondm import topology as topo  # noqa: E402
from ondm.agent import ONDMAgent, Step, chat_turn  # noqa: E402
from ondm.config import SETTINGS  # noqa: E402
from ondm.viz import topology_figure  # noqa: E402
from ondm.vlm import OllamaVLM  # noqa: E402

st.set_page_config(page_title="ONDM Optical Digital Twin", page_icon="🛰️", layout="wide")

ACTOR_ICON = {"VLM": "🧠", "SANDBOX": "📦", "VALIDATOR": "✅", "GNPY": "🔬", "NETBOX": "🗄️", "TRUSTED": "🛟",
              "AGENT": "⚙️"}
STATUS_ICON = {"ok": "🟢", "warning": "🟠", "error": "🔴", "skipped": "⚪"}
VERDICT_COLOR = {"FEASIBLE (simulated)": "#00c853", "MARGINAL": "#ffab00", "NOT FEASIBLE": "#ff1744",
                 "UNDETERMINED": "#90a4ae"}

st.markdown("""
<style>
.block-container {padding-top: 3.6rem;}
.stTabs [data-baseweb="tab-list"] {gap: 6px; flex-wrap: wrap;}
.stTabs [data-baseweb="tab"] {padding: 6px 12px; font-weight: 600;}
.kpi {background:#111a2e; border:1px solid #23314f; border-radius:8px; padding:8px 12px; text-align:center}
.kpi .v {font-size:1.35rem; font-weight:700; color:#e3f2fd} .kpi .l {font-size:0.75rem; color:#90a4ae}
.verdict {display:inline-block; padding:2px 10px; border-radius:10px; font-weight:700; color:#0b1220}
.origin {font-size:0.8rem; color:#b0bec5}
</style>""", unsafe_allow_html=True)


# ------------------------------------------------------------------------------------------ status
@st.cache_data(ttl=30, show_spinner=False)
def service_status(model: str) -> dict:
    out = {"vlm": OllamaVLM(model=model).health()}
    try:
        out["netbox"] = inventory.NetBoxInventory().status()
        out["netbox"]["ok"] = True
    except Exception as exc:
        out["netbox"] = {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:120]}"}
    out["sandbox"] = {"ok": sandbox.docker_available(), **sandbox.isolation_profile()}
    out["gnpy"] = {"ok": True, "version": gnpy_engine.GNPY_VERSION, "equipment": gnpy_engine.EQPT_CONFIG.name}
    return out


@st.cache_data(ttl=60, show_spinner=False)
def vision_models() -> list[str]:
    h = OllamaVLM().health()
    models = h.get("installed_models", [])
    pref = [m for m in models if any(k in m for k in ("vl", "gemma3", "llava", "vision", "minicpm"))]
    return pref or [SETTINGS.vlm_model]


# ------------------------------------------------------------------------------------------ sidebar
with st.sidebar:
    st.markdown("## Digital Twin")
    st.caption("Agentic VLM · GNPy · NetBox · NetworkX")
    samples = topo.list_samples()
    sample = st.selectbox("Topology", samples, index=samples.index("topo_0013") if "topo_0013" in samples else 0,
                          format_func=lambda s: f"{s} · {topo.manifest().get(s, {}).get('topology', '')} · "
                                                f"{topo.manifest().get(s, {}).get('nodes', '?')} sites")
    models = vision_models()
    default_model = SETTINGS.vlm_model if SETTINGS.vlm_model in models else models[0]
    model = st.selectbox("VLM (Ollama)", models, index=models.index(default_model))
    think = st.toggle("Model 'thinking' (slower; thinking-capable models only)", value=False)
    use_image = st.toggle("Send diagram image to VLM", value=True)
    live_inv = st.toggle("Use live NetBox", value=True)
    st.divider()
    st.markdown("**Transmission requirement (GNPy)**")
    cat = gnpy_engine.transceiver_catalog()
    rates = sorted({int(c["bit_rate_gbps"]) for c in cat}, reverse=True)
    rate = st.selectbox("Line rate (Gb/s)", rates, index=rates.index(400) if 400 in rates else 0)
    trx_type, trx_mode = gnpy_engine.mode_for_rate(rate, "Voyager" if any(
        c["trx_type"] == "Voyager" and int(c["bit_rate_gbps"]) == rate for c in cat) else None)
    margin = st.slider("Extra margin over GNPy system margin (dB)", 0.0, 5.0, 1.0, 0.5)
    power = st.slider("Channel launch power (dBm)", -3.0, 3.0, 0.0, 0.5)
    span = st.slider("Max span length (km)", 50, 100, int(SETTINGS.gnpy_max_span_km), 10)
    requirement = gnpy_engine.TransmissionRequirement(line_rate_gbps=rate, trx_type=trx_type, trx_mode=trx_mode,
                                                      extra_margin_db=margin, channel_power_dbm=power,
                                                      max_span_km=float(span))
    st.caption(f"Mode: {trx_type} / {trx_mode} (GNPy library)")
    st.divider()
    stt = service_status(model)
    v = stt["vlm"]
    st.markdown(f"{'🟢' if v.get('ok') else '🔴'} **VLM** {model}"
                + (f" · {v.get('parameter_size')} {v.get('quantization')}" if v.get("ok") else " · offline"))
    n = stt["netbox"]
    st.markdown(f"{'🟢' if n.get('ok') else '🟠'} **NetBox** "
                + (f"v{n.get('netbox_version')} · {n.get('ondm_devices')} synthetic devices" if n.get("ok")
                   else "unavailable → local fallback"))
    st.markdown(f"{'🟢' if stt['gnpy']['ok'] else '🔴'} **GNPy** {stt['gnpy']['version']}")
    st.markdown(f"{'🟢' if stt['sandbox']['ok'] else '🟠'} **Sandbox** "
                + ("Docker · no network · read-only" if stt["sandbox"]["ok"] else "unavailable → code not executed"))
    if st.button("↻ Refresh status", width="stretch"):
        service_status.clear(); vision_models.clear(); st.rerun()


def make_agent(on_step=None) -> ONDMAgent:
    return ONDMAgent(OllamaVLM(model=model), think=think, prefer_live_inventory=live_inv, on_step=on_step)


# ------------------------------------------------------------------------------------------ renderers
def verdict_badge(v: str) -> str:
    return f'<span class="verdict" style="background:{VERDICT_COLOR.get(v, "#90a4ae")}">{v}</span>'


def render_gnpy_table(results: list[dict]):
    if not results:
        st.info("No GNPy simulation was run for this request.")
        return
    rows = []
    for r in results:
        rows.append({"Role": r.get("label", ""), "Route": " → ".join(r["sites"]), "km": r.get("route_km"),
                     "Rate": f"{r['requirement']['line_rate_gbps']}G",
                     "GSNR worst (0.1nm) dB": r.get("gsnr_0p1nm_db_worst"),
                     "OSNR-ASE worst (0.1nm) dB": r.get("osnr_ase_0p1nm_db_worst"),
                     "Req. OSNR dB": r.get("required_osnr_db_0p1nm"), "Sys margin dB": r.get("system_margin_db"),
                     "Remaining margin dB": r.get("remaining_margin_db_worst"),
                     "Spans": r.get("num_fiber_spans"), "Amps": r.get("num_amplifiers"),
                     "Latency ms": r.get("latency_ms"), "Verdict": r.get("verdict"), "Status": r.get("status")})
    df = pd.DataFrame(rows)

    def color(v):
        return f"color: {VERDICT_COLOR.get(v, '#cfd8dc')}; font-weight: 700"

    st.dataframe(df.style.map(color, subset=["Verdict"]), width="stretch", hide_index=True)
    with st.expander("GNPy details: assumptions, verdict reasoning, element trace"):
        for r in results:
            st.markdown(f"**{' → '.join(r['sites'])}** @ {r['requirement']['line_rate_gbps']}G — "
                        f"{verdict_badge(r.get('verdict', ''))}", unsafe_allow_html=True)
            st.caption(r.get("requirement_text", ""))
            if r.get("verdict_reasons"):
                st.write("Reason: " + "; ".join(r["verdict_reasons"]))
            if r.get("error"):
                st.error(r["error"])
            if r.get("element_trace"):
                st.dataframe(pd.DataFrame(r["element_trace"]), width="stretch", hide_index=True, height=200)
        if results and results[0].get("assumptions"):
            st.json(results[0]["assumptions"], expanded=False)


def render_trace(steps: list[Step]):
    for i, s in enumerate(steps, 1):
        head = f"{STATUS_ICON.get(s.status, '⚪')} {ACTOR_ICON.get(s.actor, '•')} **{s.actor}** · {s.title}"
        with st.expander(f"{i}. {s.actor} · {s.title} · {s.status} · {s.duration_s}s", expanded=False):
            st.markdown(head)
            if s.detail:
                st.write(s.detail)
            if s.code:
                st.code(s.code, language="python")
            if s.payload is not None:
                st.json(s.payload, expanded=False)


def render_code_attempts(attempts: list[dict], status: str, origin: str):
    badge = {"verified": "🟢 generated code executed and verified",
             "executed_with_discrepancies": "🟠 generated code executed — discrepancies flagged",
             "failed": "🔴 generated code failed after bounded corrections — trusted fallback used",
             "not_executed": "🟠 sandbox unavailable — code NOT executed", "not_run": "⚪ no code generated"}
    st.markdown(f"**{badge.get(status, status)}**  ·  result origin: `{origin or 'n/a'}`")
    if not attempts:
        return
    tabs = st.tabs([f"Attempt {a['attempt']} · {a['status']}" for a in attempts])
    for t, a in zip(tabs, attempts):
        with t:
            if a.get("code"):
                st.code(a["code"], language="python")
            if a.get("error"):
                st.error(a["error"])
            for p in a.get("problems") or []:
                st.warning(p)


def render_run(run, key: str):
    if run.error:
        st.error(run.error)
    c1, c2 = st.columns([1.15, 1])
    with c1:
        st.plotly_chart(topology_figure(run.sample_id, run.highlight, gnpy=run.gnpy, height=520),
                        width="stretch", key=f"fig_{key}")
    with c2:
        st.markdown("#### Engineering assessment")
        st.markdown(run.answer or "_no answer_")
        st.markdown(f'<div class="origin">VLM: {model} · total {run.total_s}s · '
                    f'task: {run.task} · inventory: {(run.inventory or {}).get("source", "not queried")}</div>',
                    unsafe_allow_html=True)
    t1, t2, t3, t4, t5 = st.tabs(["🔬 GNPy results", "📦 Generated code", "🧾 Agent trace", "🗄️ Inventory evidence",
                                  "🗺️ Plan"])
    with t1:
        render_gnpy_table(run.gnpy)
    with t2:
        render_code_attempts(run.code_attempts, run.code_status, run.result_origin)
        if run.code_result is not None:
            st.markdown("**Execution result (from sandbox)**")
            st.json(run.code_result, expanded=False)
    with t3:
        render_trace(run.steps)
    with t4:
        if run.correlation:
            st.caption(f"Source: {run.correlation['source']}")
            f = pd.DataFrame(run.correlation["findings"])
            if not f.empty:
                st.dataframe(f, width="stretch", hide_index=True)
            st.write("Links excluded from routing (inventory):", run.correlation["unusable_links"] or "none")
        else:
            st.info("Inventory not queried for this run.")
    with t5:
        st.json(run.plan, expanded=True)


def run_with_live_trace(request: str, hints: dict, label: str):
    box = st.status(f"Agent working on {label} …", expanded=True)

    def on_step(s: Step):
        box.write(f"{STATUS_ICON.get(s.status, '⚪')} {ACTOR_ICON.get(s.actor, '•')} **{s.actor}** — {s.title}"
                  + (f" · _{s.detail[:160]}_" if s.detail else "") + f" ({s.duration_s}s)")

    agent = make_agent(on_step)
    run = agent.run_workflow(sample, request, hints=hints, requirement=requirement, use_image=use_image)
    box.update(label=f"{label}: finished in {run.total_s}s", state="error" if run.error else "complete",
               expanded=False)
    return run


# ------------------------------------------------------------------------------------------ layout
g = topo.build_graph(sample)
summ = topo.summary(sample)
tabs = st.tabs(["Overview", "1 · Service provisioning", "2 · Fiber failure & restoration",
                "3 · Inventory troubleshooting", "Engineering chat", "NetBox explorer", "GNPy lab",
                "Diagram reading", "Assumptions"])

# ---------------- Overview
with tabs[0]:
    k = st.columns(6)
    for col, (lab, val) in zip(k, [("ROADM sites", summ["num_sites"]), ("Fiber links", summ["num_links"]),
                                   ("Total fiber km", f"{summ['total_fiber_km']:g}"),
                                   ("Longest link km", f"{summ['max_link_km']:g}"),
                                   ("Bridges (SPOF links)", len(summ["bridges"])),
                                   ("Articulation sites", len(summ["articulation_points"]))]):
        col.markdown(f'<div class="kpi"><div class="v">{val}</div><div class="l">{lab}</div></div>',
                     unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("##### Interactive topology (ground-truth graph JSON)")
        st.plotly_chart(topology_figure(sample, height=560), width="stretch", key="ov_fig")
    with c2:
        st.markdown("##### Original diagram image (VLM input)")
        st.image(str(topo.image_path(sample)), width="stretch")
    st.caption(summ["data_provenance"])

# ---------------- BC1
with tabs[1]:
    st.markdown("### ① Intelligent optical service provisioning")
    st.caption("Plan (VLM+image) → NetBox inventory → VLM writes NetworkX routing code → sandbox → validator → "
               "GNPy per candidate → VLM explanation")
    nodes = sorted(g.nodes())
    c = st.columns([1, 1, 1, 3])
    src = c[0].selectbox("Source ROADM", nodes, index=0, key="p_src")
    dst = c[1].selectbox("Destination ROADM", nodes, index=min(6, len(nodes) - 1), key="p_dst")
    kp = c[2].number_input("Candidate routes (k)", 1, 5, 3, key="p_k")
    req = c[3].text_area("Operator request", height=80, key="p_req",
                         placeholder="Type the operator request, e.g. Provision a 400G service between ROADM A and ROADM G…")
    if st.button("▶ Run provisioning agent", type="primary", key="p_run", disabled=src == dst or not req.strip()):
        st.session_state["bc1"] = run_with_live_trace(req, {"task": "provisioning", "source": src, "target": dst,
                                                            "k_paths": int(kp), "line_rate_gbps": rate,
                                                            "strict": True}, "service provisioning")
    if st.session_state.get("bc1") and st.session_state["bc1"].sample_id == sample:
        render_run(st.session_state["bc1"], "bc1")

# ---------------- BC2
with tabs[2]:
    st.markdown("### ② Fiber failure and restoration")
    st.caption("Plan → VLM writes failure-analysis code (on a graph copy) → sandbox → validator → GNPy on the "
               "longest restoration routes → explanation")
    edges = sorted(tuple(sorted(e)) for e in g.edges())
    c = st.columns([1.2, 3])
    link = c[0].selectbox("Failed fiber link", edges, format_func=lambda e: f"{e[0]}–{e[1]} ({g[e[0]][e[1]]['distance_km']:g} km)",
                          key="f_link")
    req2 = c[1].text_area("Operator request", height=80, key="f_req",
                          placeholder="Type the operator request, e.g. Analyze the failure of fiber link H-J…")
    if st.button("▶ Run failure-analysis agent", type="primary", key="f_run", disabled=not req2.strip()):
        st.session_state["bc2"] = run_with_live_trace(req2, {"task": "failure_restoration",
                                                             "failed_link": list(link), "strict": True},
                                                      "failure analysis")
    if st.session_state.get("bc2") and st.session_state["bc2"].sample_id == sample:
        r2 = st.session_state["bc2"]
        render_run(r2, "bc2")
        res = r2.code_result if r2.code_result else None
        if res is None:
            trusted = [s for s in r2.steps if s.actor == "TRUSTED"]
            res = trusted[-1].payload if trusted else None
        if res and res.get("affected_pairs"):
            st.markdown("##### Affected site pairs")
            st.dataframe(pd.DataFrame([{"pair": "–".join(a["pair"]), "original": " → ".join(a["original_path"]),
                                        "orig km": a.get("original_km"),
                                        "restoration": " → ".join(a["restoration_path"]) if a.get("restoration_path") else "NONE (isolated)",
                                        "restoration km": a.get("restoration_km")} for a in res["affected_pairs"]]),
                         width="stretch", hide_index=True)

# ---------------- BC3
with tabs[3]:
    st.markdown("### ③ Inventory-aware ROADM troubleshooting")
    st.caption("Plan → NetBox inventory + topology correlation → VLM graph-analysis code → sandbox → validator → "
               "GNPy to farthest reachable site → explanation")
    c = st.columns([1, 3])
    roadm = c[0].selectbox("ROADM", sorted(g.nodes()), index=sorted(g.nodes()).index("D") if "D" in g else 0, key="t_roadm")
    req3 = c[1].text_area("Operator request", height=80, key="t_req",
                          placeholder="Type the operator request, e.g. Inspect the equipment and fiber connections of ROADM D…")
    if st.button("▶ Run troubleshooting agent", type="primary", key="t_run", disabled=not req3.strip()):
        st.session_state["bc3"] = run_with_live_trace(req3, {"task": "troubleshooting", "roadm": roadm, "strict": True},
                                                      "troubleshooting")
    if st.session_state.get("bc3") and st.session_state["bc3"].sample_id == sample:
        render_run(st.session_state["bc3"], "bc3")

# ---------------- Chat
with tabs[4]:
    st.markdown("### 💬 Engineering chat (autonomous tool calling)")
    st.caption("The VLM decides which tools to call: execute_networkx_code (writes its own code), gnpy_assess_path, "
               "netbox_inventory. Every tool call is shown below the answer.")
    hist_key = f"chat_{sample}"
    st.session_state.setdefault(hist_key, {"history": [], "turns": []})
    chat = st.session_state[hist_key]
    for turn in chat["turns"]:
        with st.chat_message("user"):
            st.write(turn["q"])
        with st.chat_message("assistant"):
            st.markdown(turn["a"])
            with st.expander(f"Tool trace ({len(turn['steps'])} steps)"):
                render_trace(turn["steps"])
    ex = st.columns(3)
    prompts = [f"Which links in this network are single points of failure? Write code to check.",
               f"Is a 400G service from A to the most distant site physically feasible?",
               f"Which ROADM has the most fiber connections and what does inventory say about it?"]
    clicked = None
    for col, p in zip(ex, prompts):
        if col.button(p, key=f"ex_{p[:20]}", width="stretch"):
            clicked = p
    q = st.chat_input("Ask an engineering question about this topology…") or clicked
    if q:
        with st.chat_message("user"):
            st.write(q)
        with st.chat_message("assistant"):
            box = st.status("Thinking with tools…", expanded=True)

            def on_step(s: Step):
                box.write(f"{STATUS_ICON.get(s.status, '⚪')} {ACTOR_ICON.get(s.actor, '•')} **{s.actor}** — {s.title}")
            try:
                ans, steps, hist = chat_turn(OllamaVLM(model=model), sample, chat["history"][-8:], q,
                                             attach_image=use_image and not chat["turns"], think=think,
                                             prefer_live_inventory=live_inv, on_step=on_step)
                box.update(label="Done", state="complete", expanded=False)
                chat["history"] = hist
                chat["turns"].append({"q": q, "a": ans, "steps": steps})
                st.rerun()
            except Exception as exc:
                box.update(label="Error", state="error")
                st.error(f"VLM/tool error: {type(exc).__name__}: {exc}")
    if chat["turns"] and st.button("Clear chat"):
        st.session_state[hist_key] = {"history": [], "turns": []}
        st.rerun()

# ---------------- NetBox explorer
with tabs[5]:
    st.markdown("### 🗄️ Inventory explorer (read-only)")
    inv = inventory.inventory_for(sample, live_inv)
    src_label = inv["source"]
    (st.success if src_label == "LIVE NETBOX" else st.warning)(
        f"Source: **{src_label}** · {inv.get('backend_note', '')}" + (f" · {inv['url']}" if inv.get("url") else ""))
    corr = inventory.correlate(sample, inv)
    c1, c2 = st.columns([1, 1])
    with c1:
        st.markdown("##### Devices")
        st.dataframe(pd.DataFrame(inv["devices"]).drop(columns=["netbox_id"], errors="ignore"),
                     width="stretch", hide_index=True, height=300)
    with c2:
        st.markdown("##### Topology ↔ inventory correlation")
        fd = pd.DataFrame(corr["findings"])
        if fd.empty:
            st.success("No discrepancies")
        else:
            st.dataframe(fd, width="stretch", hide_index=True, height=300)
    st.markdown("##### Fiber & patch cables")
    st.dataframe(pd.DataFrame(inv["cables"]), width="stretch", hide_index=True)
    st.plotly_chart(topology_figure(sample, {"excluded_links": corr["unusable_links"]}, height=420),
                    width="stretch", key="nb_fig")
    with st.expander("Interfaces"):
        st.dataframe(pd.DataFrame(inv["interfaces"]), width="stretch", hide_index=True)

# ---------------- GNPy lab
with tabs[6]:
    st.markdown("### 🔬 GNPy lab — direct physical-layer simulation")
    st.caption("Deterministic GNPy runs on an explicit ROADM path (no VLM). Use to check what the agent reports.")
    c = st.columns([1, 1, 2])
    a_ = c[0].selectbox("From", sorted(g.nodes()), key="g_a")
    b_ = c[1].selectbox("To", sorted(g.nodes()), index=min(3, len(g) - 1), key="g_b")
    import networkx as nx
    from itertools import islice

    try:
        cands = [list(p) for p in islice(nx.shortest_simple_paths(g, a_, b_, weight="distance_km"), 5)] if a_ != b_ else []
    except nx.NetworkXNoPath:
        cands = []
    pick = c[2].multiselect("Paths to simulate", [" → ".join(p) for p in cands],
                            default=[" → ".join(p) for p in cands[:2]])
    if st.button("▶ Run GNPy", type="primary"):
        res = []
        with st.spinner("Running GNPy design + propagation…"):
            for p in pick:
                r = gnpy_engine.assess_path(sample, p.split(" → "), requirement)
                r["label"] = "manual"
                res.append(r)
        st.session_state["gnpy_lab"] = (sample, res)
    if st.session_state.get("gnpy_lab") and st.session_state["gnpy_lab"][0] == sample:
        res = st.session_state["gnpy_lab"][1]
        render_gnpy_table(res)
        st.plotly_chart(topology_figure(sample, {"paths": [r["sites"] for r in res]}, gnpy=res, height=460),
                        width="stretch", key="gl_fig")
    with st.expander("Transceiver modes in the GNPy example equipment library"):
        st.dataframe(pd.DataFrame(gnpy_engine.transceiver_catalog()), width="stretch", hide_index=True)

# ---------------- Diagram reading
with tabs[7]:
    st.markdown("### 👁️ Diagram reading — VLM vs ground truth")
    st.caption("The VLM sees ONLY the image; the validator compares its extraction with the graph JSON. "
               "Single-sample check, not a benchmark.")
    c1, c2 = st.columns([1, 1])
    with c1:
        st.image(str(topo.image_path(sample)), width="stretch")
    with c2:
        if st.button("▶ Read diagram with VLM", type="primary"):
            with st.spinner("VLM reading the diagram…"):
                try:
                    st.session_state["diag"] = (sample, make_agent().read_diagram(sample))
                except Exception as exc:
                    st.error(f"{type(exc).__name__}: {exc}")
        if st.session_state.get("diag") and st.session_state["diag"][0] == sample:
            d = st.session_state["diag"][1]
            k = st.columns(3)
            k[0].metric("Nodes correct", f"{d['nodes_correct']}/{d['nodes_true']}", f"{d['nodes_predicted']} predicted",
                        delta_color="off")
            k[1].metric("Links correct", f"{d['links_correct']}/{d['links_true']}", f"{d['links_predicted']} predicted",
                        delta_color="off")
            k[2].metric("Link km correct", f"{d['link_km_correct']}/{d['links_correct']}", f"{d['latency_s']} s",
                        delta_color="off")
            st.write("Missed links:", d["missed_links"] or "none", " · Spurious links:", d["spurious_links"] or "none")
            st.write(f"Topology type — VLM: `{d['prediction'].get('topology_type')}` · truth: `{d['topology_type_true']}`")
            st.json(d["prediction"], expanded=False)

# ---------------- Assumptions
with tabs[8]:
    st.markdown("""
### ℹ️ Assumptions, provenance and limitations
**Data.** 30 synthetic topologies (`data/semantic_pilot`). Vertices are ROADM switching sites; edges are fiber links with
synthetic lengths (40–400 km). Not operator data.

**GNPy.** Topology converted by the preserved research converter `integrations/gnpy/full_topology_to_gnpy.py`
(unchanged): every vertex → GNPy `Roadm` (default variety), a test `Transceiver` attached at every ROADM (simulation
assumption), each link → two directed fiber chains split into spans ≤ max-span km with in-line EDFAs; boosters/pre-amps
added by GNPy autodesign. Fiber/EDFA/ROADM/transceiver parameters come from GNPy's **example** equipment library
(`eqpt_config.json`), not vendor or measured data. Full C-band load at the transceiver mode's minimum spacing.
**Verdict rule:** `FEASIBLE (simulated)` only if the worst-channel GNPy remaining margin (GSNR − required OSNR −
transceiver penalties − library system margin) ≥ the configured extra margin; `MARGINAL` if 0 ≤ margin < extra margin;
`NOT FEASIBLE` if < 0. No spectrum occupancy, ageing, PDL/filtering penalties beyond GNPy defaults, or real power
settings are modelled.

**NetBox.** Local NetBox 4.7 (Docker) populated by `scripts/netbox_synthetic_inventory.py` with records tagged
`ondm-synthetic` (reversible). Three troubleshooting constraints tagged `ondm-scenario` were injected deliberately
(topo_0003/0013/0023). The app uses a read-only token.

**Generated code.** Runs in a Docker container with no network, read-only FS, non-root, resource limits, no secrets.
Results are checked by a validator against the ground-truth graph; on repeated failure a clearly labelled trusted
tool is used instead — never presented as generated output.

**VLM.** One local model (default Qwen3-VL-8B-Instruct, Q4_K_M via Ollama). Outputs vary between runs; errors are
expected and visible in the trace. No benchmark claims are made.
""")
