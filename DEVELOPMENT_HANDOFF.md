# DEVELOPMENT HANDOFF — ONDM Agentic Optical Network Digital Twin

_Last updated: 13 Nov 2026 (prototype for the 16 Nov 2026 demonstration). Written so that a reviewer (human or
the ChatGPT research/writing agent) can audit the implementation and draft the ONDM manuscript without running it._

---

## 1. Environment audit (13 Nov 2026)

| Item | Finding |
|---|---|
| Host | Windows 11 Pro, Python 3.12.10 venv (`.venv`) |
| GPU | NVIDIA RTX 3500 Ada Laptop, 12 GB VRAM, driver 596.58 / CUDA 13.2 |
| VLM runtime | Ollama 0.40.16 (already installed). Vision models present before this work: `gemma3:4b`, `gemma3:12b-it-qat` (no tool calling) |
| VLM chosen | **`qwen3-vl:8b-instruct`** (Qwen3-VL 8.2B, Q4_K_M, ~6.6 GB loaded at 16k ctx, 100 % GPU, ≈40 tok/s). Capabilities reported by Ollama: completion, vision, tools |
| GNPy | 3.0.1 already installed in `.venv`, CLI and Python API functional |
| NetBox | **Not installed.** Port 8080 is the EDB PostgreSQL Apache landing page, port 5432 a native PostgreSQL 18 — unrelated. NetBox 4.7.5 was deployed via `netbox-docker` (see §4) |
| Docker | Docker Desktop 4.84 / Engine 29.6.2. It initially failed to start because of stale AF_UNIX socket files from Aug 2026 in `%LOCALAPPDATA%\Docker\run`; the directory was renamed to `run.stale-20261113` (not deleted) and Docker started normally |
| Dataset | `data/semantic_pilot/`: 30 graphs + 30 PNGs + YOLO labels + manifest; all vertices `equipment_type: ROADM`; 6–12 sites, max degree 11, all connected. **Not modified.** |
| Original scripts | `integrations/gnpy/full_topology_to_gnpy.py` and `topology_to_gnpy_poc.py` — **not modified**; the app imports the converter as-is |

## 2. What was built (verified)

```
ondm/config.py        settings from env/.env (no secrets in code)
ondm/topology.py      read-only dataset access, path validation, sanitized sandbox payload
ondm/vlm.py           VLMBackend protocol + OllamaVLM; image downscaling; JSON/code extraction; hard token caps
ondm/gnpy_engine.py   converter reuse + GNPy design/propagation per explicit ROADM path, explicit acceptance rule
ondm/inventory.py     NetBoxInventory (pynetbox, read-only) | LocalInventory (labelled fallback); correlation checks
ondm/sandbox.py       AST policy + Docker execution (no network, RO fs, non-root, limits, no env)
ondm/agent.py         ONDMAgent workflows (BC1–BC3), validator, bounded self-correction, trusted fallbacks, chat tools
ondm/viz.py           Plotly topology figure with path / failure / unusable-link highlighting
app/streamlit_app.py  NOC console (9 tabs)
sandbox/              Dockerfile + runner.py for image ondm-sandbox:latest
scripts/netbox_synthetic_inventory.py   plan | import [--scenarios] | rollback
scripts/smoke_agent.py                  end-to-end run of BC1–BC3 + chat with the real VLM
tests/test_core.py                      9 tests (dataset, routing, failure, GNPy, inventory fallback, policy, sandbox)
docs/presentation/    build_deck.js, screenshots, ONDM_Agentic_Digital_Twin_2026-11-16.pptx (9 slides)
```

### 2.1 Agent workflow and provenance model
Each run produces a trace of `Step(actor, title, status, detail, payload, code)` where actor ∈
`VLM | SANDBOX | VALIDATOR | NETBOX | GNPY | TRUSTED | AGENT`.

1. **Plan (VLM)** — image (downscaled to 896 px) + request + topology facts → JSON plan under an Ollama JSON schema.
2. **Validate plan (VALIDATOR)** — ids checked against the graph; UI selections are authoritative in demo (“strict”)
   mode; every override is logged (the model frequently returns `null` for endpoints — logged as a warning).
3. **Inventory (NETBOX)** — devices/interfaces/cables for the topology; correlation produces findings and a list of
   *unusable links* (cable not `connected`, disabled port, missing record).
4. **Code (VLM)** — task contract + result schema; the model writes Python/NetworkX.
5. **Execute (SANDBOX)** — see §5.
6. **Inspect (VALIDATOR)** — task-specific checks against ground truth (path validity, km, duplicates, k-coverage,
   shortest route found, excluded links respected, affected-pair count, restoration validity, degree,
   articulation, reachability, farthest site). Failures are fed back to the VLM.
7. **Correct** — up to 3 attempts. Feedback contains the error, the offending source lines mapped from the traceback,
   and hints (real NetworkX names for hallucinated attributes via `difflib`, common type errors). Sampling seed and
   temperature change per attempt (identical retries were observed otherwise).
8. **Fallback (TRUSTED)** — only if all attempts fail/are rejected: deterministic NetworkX tool, labelled
   `TRUSTED fallback tool (generated code failed)` in trace, UI and evidence passed to the explanation.
9. **Physics (GNPY)** — candidate / restoration / farthest-site paths; for BC1 a lower-rate search (300→200→100G) on
   the shortest route when no candidate is feasible.
10. **Explain (VLM)** — evidence JSON only; required sections Findings / Evidence / Assumptions / Recommendation.

### 2.2 GNPy integration details
- Converter: preserved script, called with `max_span_km` (default 80) → every vertex a GNPy `Roadm` (default variety),
  a `Transceiver` at every ROADM, each undirected link → two directed chains of `Fiber` spans ≤ 80 km separated by
  `Edfa` ILAs (operational params removed so GNPy autodesign sets gain). Cached in `simulations/cache/`.
- Simulation: `gnpy.tools.worker_utils.designed_network` + `transmission_simulation` with a `PathRequest` built from
  `trx_mode_params(equipment, trx_type, trx_mode)`; strict ROADM include list = exact requested path; spacing = mode
  `min_spacing`; full C-band load between SI `f_min`/`f_max`; `SimParams` default (no Raman).
- Reported: worst/mean GSNR (0.1 nm and signal bandwidth), OSNR-ASE, required OSNR, system margin, **GNPy remaining
  margin** (`gnpy.topology.request.remaining_margin`), CD, PMD, PDL, latency, span/amplifier counts, element trace.
- **Verdict rule** (only from executed results): margin_worst < 0 → `NOT FEASIBLE`; 0 ≤ margin < extra margin (UI,
  default 1 dB) → `MARGINAL`; ≥ extra margin → `FEASIBLE (simulated)`; no margin / error → `UNDETERMINED`/`ERROR`.
  Optional latency limit.
- Example verified numbers (400G = Voyager mode 2, 66 GBd, req. OSNR 21 dB, 2 dB system margin, 0 dBm/ch):

| Topology / path | km | GSNR worst (0.1 nm) | Remaining margin | Verdict |
|---|---|---|---|---|
| topo_0003 A-F | 90 | 28.75 dB | +5.75 dB | FEASIBLE (simulated) |
| topo_0003 A-F-E-D-C | 370 | 23.32 dB | +0.32 dB | MARGINAL |
| topo_0003 A-B-C | 740 | 22.32 dB | −0.68 dB | NOT FEASIBLE |
| topo_0013 A-F-E-D-G | 590 | 22.02 dB | −0.98 dB | NOT FEASIBLE |
| topo_0013 A-L-F-E-D-G | 1010 | 20.26 dB | −2.74 dB | NOT FEASIBLE |
| topo_0013 A-F-E-D-G @300G (mode 3) | 590 | 21.81 dB | +1.81 dB | FEASIBLE (simulated) |
| topo_0013 D-E-F-K | 650 | 22.04 dB | −0.96 dB | NOT FEASIBLE |

  The app's GSNR for topo_0003 A→C (23.32 dB) differs from the archived CLI log (22.83 dB) because the CLI run used
  the SI 50 GHz grid (32 GBd reference channel) while the app uses the 400G mode at 75 GHz spacing.
- A GNPy run takes ≈0.1–0.6 s.

### 2.3 NetBox integration details
- NetBox 4.7.5 (image `netboxcommunity/netbox:v4.7-5.1.2`) at http://localhost:8000 (bound to 127.0.0.1),
  compose project in `C:\Users\dipto\netbox-docker` (outside the repo). Default secrets in `env/*.env` were replaced
  by random values. Admin credentials: `C:\Users\dipto\netbox-docker\ONDM_LOCAL_CREDENTIALS.txt` (local only).
- Two v2 API tokens (`nbt_…`): **read-only** (`NETBOX_TOKEN`, used by the app; write attempts return 403 — verified)
  and **write** (`NETBOX_WRITE_TOKEN`, used only by the import script). Both live only in the gitignored `.env`.
- Import (approved by the user on 13 Nov 2026, with scenarios): 30 site groups, 283 sites/ROADMs
  (`SYN-ROADM-CDC-12D`, DEG-1..12 + AD-1..4), 114 transponders (`SYN-TRX-400G`) only where the dataset has
  `attached_transceiver: true`, 310 SMF cables (length = `distance_km`, description = span/ILA counts), 114 patch
  cables. Everything tagged `ondm-synthetic`; manifest at `simulations/netbox/import_manifest.json`; rollback tested
  (44 objects created and removed in a trial).
- **Injected scenarios** (tag `ondm-scenario`, deterministic choice: longest link → `planned`, highest-degree ROADM
  DEG-1 → disabled, first transponder → `offline`):
  topo_0003: B–C planned, A DEG-1 disabled · topo_0013: A–B planned, D DEG-1 (cable C–D) disabled, TRX-I offline ·
  topo_0023: C–F planned, H DEG-1 disabled, TRX-B offline.
- Fallback: if NetBox is unreachable or the topology is absent, `LocalInventory` derives the same structure from the
  graph JSON and every payload/UI element is labelled `LOCAL FALLBACK (synthetic graph JSON, not NetBox)`.

## 3. Verification performed
- `pytest`: 9/9 pass (includes live Docker sandbox test).
- Sandbox: network blocked (OSError), env contains no host variables, memory limit kills (exit 137 → `SANDBOX_ERROR`),
  infinite loop stopped by in-container `SIGALRM` (PID-1 handler) at 20 s, policy rejects `os`, `socket`,
  `importlib`, `open`, dunder access, `locals()`.
- Diagram reading (topo_0003, image only): 6/6 nodes, 6/6 links, 6/6 km labels correct (one sample, not a benchmark).
- Smoke run `scripts/smoke_agent.py`, 13 Nov 2026 17:10, real VLM:

| Workflow | Code outcome | Notes | Wall time |
|---|---|---|---|
| BC1 provisioning topo_0013 A→G | **failed** 3× (`KeyError: 0`, same bug) → TRUSTED fallback | 2 routes; both 400G NOT FEASIBLE; 300G FEASIBLE on 590 km route | 73 s |
| BC2 failure topo_0023 H–J | **verified** on attempt 1 | GNPy skipped by plan flag → fixed afterwards (now always runs) | 28 s |
| BC3 troubleshooting topo_0013 D | **verified** on attempt 3 (two `unhashable list` errors corrected) | disabled DEG-1 / C–D, no transponder, D-E-F-K 650 km NOT FEASIBLE | 79 s |
| Chat “single points of failure?” | sandbox call failed, model rewrote it, second call OK | answer grounded in tool output | — |

  Earlier development runs: BC1 once self-corrected to a verified result on attempt 2; the validator once rejected
  an OK-executing result that returned the same route three times.
- UI: all tabs render; BC3 executed end-to-end in the browser with live trace (84 s).

## 4. Configuration / how to run
See README for full Windows steps. Required at runtime: Ollama with `qwen3-vl:8b-instruct`, Docker Desktop running
(NetBox containers + `ondm-sandbox:latest` image), `.env` with `NETBOX_URL`/`NETBOX_TOKEN`.

```bat
cd /d C:\Users\dipto\netbox-docker && docker compose up -d
cd /d "C:\Users\dipto\Downloads\Projects\Imran ONDM 27"
.venv\Scripts\streamlit run app\streamlit_app.py
```

Environment variables: see `.env.example` (`ONDM_VLM_MODEL`, `ONDM_VLM_NUM_CTX`, `ONDM_SANDBOX_*`,
`ONDM_MAX_CODE_ATTEMPTS`, `ONDM_GNPY_MAX_SPAN_KM`).

## 5. Security notes
- Generated code never runs on the host. The Docker container has `--network none`, `--read-only`, tmpfs `/tmp`
  (noexec, 16 MB), `--memory 256m --memory-swap 256m`, `--cpus 1`, `--pids-limit 64`, `--cap-drop ALL`,
  `no-new-privileges`, UID 10001, no volumes, no forwarded environment. Input is a sanitized topology dict on stdin.
- If Docker is unavailable the code is displayed but **not executed** (`NOT_EXECUTED`) and the trusted tool is used,
  clearly labelled.
- The AST policy is defence-in-depth only; the container is the boundary.
- The app holds only a read-only NetBox token; the chat tools expose read-only inventory queries only.

## 6. Known issues / remaining work
1. **Code-generation reliability** of the 8B model is moderate: recurrent bugs (dict indexed by position, lists as
   set members, invented NetworkX names, `locals()` checks). Hints were added after the smoke run (`_api_hint`) and
   have not yet been re-measured. Expect occasional trusted fallbacks during the demo — they are labelled.
2. The model often omits endpoint ids in the plan JSON; the validator fills them from UI selections (logged).
3. Explanations occasionally mis-paraphrase evidence (e.g. "ROADM D has 4 ports" for 4 cabled ports of 12). Evidence
   keys were renamed to be explicit; residual paraphrase errors are possible — the evidence panels are authoritative.
4. Workflow latency 30–150 s (dominated by VLM generation, ≈40 tok/s). First call after idle includes model load.
5. `qwen3-vl:8b` (thinking variant) ignores `think=false` and generated thousands of tokens without answering → not
   used by default; selectable in the UI with the thinking toggle.
6. Streamlit does not hot-reload `ondm/*` changes reliably — restart the server after editing the package.
7. Local diffs kept unstaged (not pushed) on purpose: `docs/CODING_AGENT_BRIEF.md` (local starter-package version
   differs from GitHub), and trailing-newline-only diffs in the two original GNPy converters.
8. Not implemented (by instruction): MCP servers, fine-tuning, TopoBench evaluation, multi-agent systems.

## 7. Scientific limitations (for the manuscript)
- **Synthetic data only.** Topologies, lengths, and inventory are generated; 3 inventory constraints were injected
  deliberately for demonstration. No operator telemetry.
- **Physical layer**: GNPy example equipment library (`eqpt_config.json`): fibre (SSMF), EDFA, ROADM default
  variety, Voyager transceiver modes — assumptions, not vendor/field data. Transceivers at every ROADM are a
  simulation assumption (NetBox only lists transponders where the dataset marks them). Full-load C-band, no spectrum
  assignment/occupancy, no ageing, no measured connector losses, GNPy default nonlinear model; the 80 km span split is
  a converter assumption.
- **Feasibility semantics**: "FEASIBLE (simulated)" means only that GNPy's remaining margin under these assumptions
  exceeds the configured extra margin.
- **Model evaluation**: one model, a handful of runs, no held-out evaluation, no statistics. Nothing in this
  prototype should be reported as a benchmark result. The deterministic validator could serve as an automatic
  scorer for future evaluation (path validity, distance error, affected-pair correctness, etc.).
- **Dataset splits** remain preliminary random splits; ILA/transceiver symbols are not rendered in the images.

## 8. Suggested next steps (post-demo, aligned with roadmap)
- Re-run `scripts/smoke_agent.py` N times per workflow and per topology to measure first-attempt and post-correction
  success; log traces as JSON for the paper.
- Add a second/third VLM backend (e.g. Gemma-3, InternVL, MiniCPM-V) behind `VLMBackend`; compare on identical tasks.
- Expand the dataset (rendered amplifier/transceiver symbols, grouped holdouts), then fine-tune.
- Wrap tools as MCP servers; explore richer planning and repair strategies.
