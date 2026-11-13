# ONDM Agentic Optical Network Digital Twin

Research prototype: a **small local vision-language model (VLM)** that reads synthetic optical-network diagrams,
plans engineering tasks, **writes and self-corrects Python/NetworkX code** executed in an isolated sandbox, queries a
**live NetBox** inventory (read-only), runs **GNPy** physical-layer simulations, and explains the results with
evidence — all in a dark NOC-style Streamlit console.

> **Status (13 Nov 2026): working prototype for the 16 Nov 2026 demonstration.** All topologies, inventory and
> equipment parameters are **synthetic**. This is not a validated operator digital twin; GNPy verdicts hold only under
> the stated example-equipment assumptions. See [DEVELOPMENT_HANDOFF.md](DEVELOPMENT_HANDOFF.md) for verified status,
> limitations and open issues.

## What is implemented

| Component | Implementation | Verified |
|---|---|---|
| VLM | `qwen3-vl:8b-instruct` (Qwen3-VL 8B, Q4_K_M) via local Ollama; modular backend (`ondm/vlm.py`) | ✅ image + text + tool calls on RTX 3500 Ada 12 GB |
| GNPy | Preserved converter `integrations/gnpy/full_topology_to_gnpy.py` + GNPy 3.0.1 design/propagation API (`ondm/gnpy_engine.py`) | ✅ GSNR/OSNR/margin per explicit path |
| NetBox | NetBox 4.7.5 (Docker), reversible synthetic import, read-only pynetbox client + labelled local fallback (`ondm/inventory.py`) | ✅ live |
| Code agent | VLM writes NetworkX code → AST policy → Docker sandbox (no network, read-only, non-root, limits) → validator → bounded correction (`ondm/sandbox.py`, `ondm/agent.py`) | ✅ |
| Use cases | ① service provisioning ② fiber failure & restoration ③ inventory-aware ROADM troubleshooting + free tool-calling chat | ✅ |
| UI | `app/streamlit_app.py` (topology viz, image viewer, live agent trace, code viewer, GNPy tables, NetBox explorer, GNPy lab, diagram-reading check) | ✅ |

## Architecture

```
 Operator ──► Streamlit NOC console ──► ONDMAgent (ondm/agent.py)
                                          │ 1 plan        ── VLM (image + request)  ─┐
                                          │ 2 inventory   ── NetBox REST (read-only) │  every step recorded in a
                                          │ 3 code        ── VLM writes NetworkX code │  transparent trace:
                                          │ 4 execute     ── Docker sandbox           │  VLM / SANDBOX / VALIDATOR /
                                          │ 5 inspect     ── validator vs ground truth│  GNPY / NETBOX / TRUSTED
                                          │   (error → VLM correction, ≤3 attempts)   │
                                          │ 6 physics     ── GNPy design+propagation  │
                                          │ 7 explain     ── VLM (evidence-only)     ─┘
 data/semantic_pilot (30 synthetic topologies: graph JSON + PNG)  ── immutable source of truth
```

## Windows installation

Prerequisites: Python 3.12, [Ollama](https://ollama.com) ≥ 0.30, Docker Desktop (for NetBox and the sandbox),
NVIDIA GPU with ≥ 8 GB VRAM recommended.

```bat
cd /d "C:\Users\dipto\Downloads\Projects\Imran ONDM 27"
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
ollama pull qwen3-vl:8b-instruct
docker build -t ondm-sandbox:latest sandbox
copy .env.example .env
```

**NetBox** (local, Docker; installed outside the repo):

```bat
cd /d C:\Users\dipto
git clone -b release https://github.com/netbox-community/netbox-docker.git
cd netbox-docker
rem create docker-compose.override.yml publishing 127.0.0.1:8000:8080, change default secrets in env\*.env
docker compose up -d
```

Create a superuser and two API tokens (read-only for the app, write for the import script), put them in `.env`, then:

```bat
.venv\Scripts\python scripts\netbox_synthetic_inventory.py plan --scenarios
.venv\Scripts\python scripts\netbox_synthetic_inventory.py import --scenarios
rem undo everything later with:
.venv\Scripts\python scripts\netbox_synthetic_inventory.py rollback
```

## Run

```bat
.venv\Scripts\streamlit run app\streamlit_app.py
```

Open http://localhost:8501. Tests (no VLM needed): `.venv\Scripts\python -m pytest -q`.
End-to-end smoke run with the VLM: `.venv\Scripts\python scripts\smoke_agent.py`.

## Repository layout

```
app/streamlit_app.py            Streamlit console
ondm/                           agent, VLM backend, GNPy engine, inventory, sandbox, topology, viz
sandbox/                        Dockerfile + runner for isolated code execution
scripts/netbox_synthetic_inventory.py   reversible NetBox import (tagged ondm-synthetic)
scripts/smoke_agent.py          end-to-end run of all workflows
integrations/gnpy/              ORIGINAL research converters (unchanged)
data/semantic_pilot/            ORIGINAL 30-topology dataset (unchanged)
simulations/examples/           original GNPy example outputs
docs/                           dataset notes, scope, GNPy integration notes, presentation
tests/                          integration checks
DEVELOPMENT_HANDOFF.md          status, limitations, configuration, next steps
```

## Important limitations

- Synthetic data only; NetBox content is generated from the dataset (+3 tagged demo constraints).
- GNPy uses the **example** equipment library (`eqpt_config.json`): fibre, EDFA, ROADM and transceiver values are
  assumptions, not vendor or field data. Test transceivers at every ROADM are a simulation assumption.
- The VLM makes mistakes (wrong ids, buggy code); these are visible in the trace and handled by validation, bounded
  correction and labelled trusted fallbacks. No benchmark results are claimed.
- Dataset splits are preliminary, not leakage-free holdouts.

Do not commit API tokens, `.env`, model weights, or real operator data.
