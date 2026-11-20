# ONDM Cleanup & Preservation Manifest

**Prepared:** 2026-11-20 · **Status:** APPROVED "as proposed" by the PI and EXECUTED on 2026-11-20 (branch `research/vlm-topology-classification`). `.env` was moved to `archive/unrelated/` rather than deleted (least-destructive option); backup tags pushed to GitHub.
**Project root:** `C:\Users\dipto\Downloads\Projects\Imran ONDM 27`
**Scope:** this folder only. Sibling folders in `Downloads\Projects\` (including `OTSE_Research_Archive`) are not touched.

---

## 0. Pre-cleanup safety actions already done (non-destructive)

| Action | Result |
|---|---|
| Git remote | `origin` → `https://github.com/imranchy/ONDM-Agentic-Optical-Network-Digital-Twin.git` |
| Current branch | `feature/agentic-digital-twin-demo` @ `6f5447c` (in sync with origin). `main` @ `7e4532e` is **5 commits behind** (it lacks the GNPy converters and the agentic prototype). |
| Backup tag (feature) | `backup/pre-research-restructure-2026-11-20` → `6f5447c` ✅ verified, **local only** |
| Backup tag (main) | `backup/main-pre-research-restructure-2026-11-20` → `7e4532e` ✅ verified, **local only** |
| Uncommitted work preserved | Copied to `archive/pre_cleanup_uncommitted_2026-11-20/` (7 files + `uncommitted_tracked_changes.diff`, SHA-256 recorded) |

Uncommitted state at audit time:

| File | Change |
|---|---|
| `app/streamlit_app.py` | modified (+20/−28) |
| `docs/CODING_AGENT_BRIEF.md` | modified |
| `docs/presentation/ONDM_Merged_Presentation.pptx` | modified (8.48 → 8.49 MB) |
| `integrations/gnpy/full_topology_to_gnpy.py` | trailing newline only |
| `integrations/gnpy/topology_to_gnpy_poc.py` | trailing newline only |
| `ONDM_semantic_update_README.md` | untracked (research note) |
| `Test Questions.docx` | untracked |

## 0.1 Environment findings

| Item | Finding | Action |
|---|---|---|
| Python env | `.venv` (Python 3.12.10, ~693 MB) has gnpy 3.0.1, networkx, matplotlib, etc. | **KEEP**. Nothing is uninstalled. App-only packages are dropped from `requirements.txt` but stay installed. |
| GPU | NVIDIA RTX 3500 Ada Laptop, 12 GB VRAM, driver 596.58 | (Phase 10 reference) |
| Ollama | `qwen3-vl:8b-instruct`, `qwen3-vl:8b`, `qwen3:32b`, several `otse-*` models (OTSE project), … | **Not touched** |
| Secrets | `.env` holds NetBox URL + read and write tokens (gitignored, never committed) | See R-14 |

---

## 1. Historical datasets → ARCHIVE to `archive/historical_datasets/` (names and inner structure kept)

| ID | Path | Type | Size | Contents / purpose | Action | Note |
|---|---|---|---|---|---|---|
| A-1 | `optical_topology_dataset.zip` | zip | 28.3 MB | **The original 500-topology dataset**: 501 graphs/images/YOLO labels, splits, `generation_config.json`, `data-generator.py`, `pix2struct_train/eval.py`, `References/` | ARCHIVE | Moved byte-for-byte, not unzipped. Gitignored (too large to commit); a SHA-256 is recorded in the archive README. |
| A-2 | `optical_topology_pilot/` | dataset | 2.7 MB, 95 files | Earliest 30-topology pilot (graphs, images, YOLO, splits, config) | ARCHIVE | |
| A-3 | `optical_topology_v2_pilot/` | dataset | 1.4 MB, 97 files | v2 30-topology pilot + `manifest.csv` | ARCHIVE | |
| A-4 | `optical_topology_semantics_pilot/` | dataset | 1.5 MB, 97 files | **Corrected 30-topology semantic pilot** (seed 2027, 6–12 nodes) | ARCHIVE | |
| A-5 | `data/semantic_pilot/` (tracked) | dataset | 1.5 MB, 97 files | Copy of A-4 used by the agent app | ARCHIVE (`git mv`) | Identical to A-4 apart from the `path:` line in `dataset.yaml`. Both are kept and the duplicate is documented. |
| A-6 | `results/figures/`, `results/statistics/` | PNG / CSV | 2.5 MB, 10 files | Historical contact sheets, structural statistics, `validation_issues.csv` | ARCHIVE → `archive/historical_datasets/results_2026-10/` | |
| A-7 | `simulations/examples/`, `simulations/generated/` (tracked) | GNPy JSON / logs | ~0.5 MB | Real GNPy runs on `topo_0003` (designed networks + logs) | ARCHIVE → `archive/historical_datasets/gnpy_runs/` | Evidence of GNPy execution on the **old** pilot only |
| A-8 | `simulations/cache/` | GNPy JSON | ~0.27 MB | `topo_00{02,03,13,23}_span80` conversions made by the agent app | ARCHIVE (same folder as A-7) | Small enough to keep |

## 2. Reusable code and notes → KEEP or ARCHIVE

| ID | Path | Type | Size | Purpose | Action | Reason |
|---|---|---|---|---|---|---|
| K-1 | `integrations/gnpy/full_topology_to_gnpy.py` | py | 7.6 KB | ROADM graph → GNPy network converter | **KEEP** → `src/validation/gnpy/` | Reused for optional engineering checks (Phase 3.3) |
| K-2 | `integrations/gnpy/topology_to_gnpy_poc.py` | py | 3.9 KB | Single-link GNPy proof of concept | **KEEP** → `src/validation/gnpy/` | Historical and still useful |
| K-3 | `scripts/data-generator.py` | py | 15 KB | v2 semantic generator (ring/star/mesh/tree/hybrid/random) | ARCHIVE → `archive/legacy_code/` | Superseded: it labels **graph shape**, not operational architecture. Rendering ideas are reused. |
| K-4 | `scripts/audit_optical_dataset.py` | py | 5 KB | Read-only dataset audit | ARCHIVE → `archive/legacy_code/` | Seed for the new validator |
| K-5 | `scripts/inspect_pilot.py` | py | 1 KB | Contact-sheet helper | ARCHIVE → `archive/legacy_code/` | |
| K-6 | `ondm/gnpy_engine.py` | py | 15 KB | Runs GNPy design + propagation on a routed path | ARCHIVE → `archive/legacy_code/` | May become the GNPy validation hook later |
| K-7 | `ondm/vlm.py` | py | 5.9 KB | Ollama VLM client | ARCHIVE → `archive/legacy_code/` | Reference for the Phase 10 evaluation harness |
| K-8 | `docs/GNPY_INTEGRATION.md` | md | 1.4 KB | GNPy usage notes | **KEEP** → `references/` | |
| K-9 | `docs/SEMANTIC_DATASET_NOTES.md`, `ONDM_semantic_update_README.md` | md | 3.5 KB each | Equipment-semantics correction notes and known limitations | ARCHIVE → `archive/notes/` | Provenance of the old pilots |
| K-10 | `DEVELOPMENT_HANDOFF.md`, `docs/CODING_AGENT_BRIEF.md`, `docs/PROJECT_SCOPE.md` | md | 15 / 2.8 / 1 KB | Agentic-app handoff and scope | ARCHIVE → `archive/notes/` | Replaced by `RESEARCH_HANDOFF.md` and a new README |
| K-11 | `docs/presentation/*` (2 pptx, `build_deck.js`, `build_merged_deck.py`, `make_figures.py`, `img/`) | pptx / js / py / img | 8.7 MB | Previous stakeholder decks | ARCHIVE → `archive/presentations/` | Background slides may be reused on Monday |
| K-12 | `Untitled.ipynb` | ipynb | 444 KB | Ad-hoc dataset analysis; paths point to "Imran Journal 2 …" | ARCHIVE → `archive/notes/` | Not ONDM-specific, but kept |
| K-13 | `Test Questions.docx` | docx | 15 KB | Agent-app test questions | ARCHIVE → `archive/notes/` | |
| K-14 | `simulations/netbox/import_manifest.json` | json | 103 KB | Record of synthetic objects created in local NetBox | ARCHIVE → `archive/legacy_code/netbox/` | **Needed if you ever want to roll back the NetBox import.** Do not delete. |
| K-15 | `Document-OCR.zip` | zip | 9.4 MB | Older, separate OCR/topology-extractor Streamlit project (Feb 2026) | ARCHIVE → `archive/unrelated/` (gitignored) | Not ONDM, but not mine to delete |
| K-16 | `.venv/` | env | 693 MB | ONDM Python environment | **KEEP** | |

## 3. Files to REPLACE (rewritten in place; old versions stay in git history and the backup tag)

| ID | Path | Reason |
|---|---|---|
| P-1 | `README.md` | Rewritten for the VLM classification research objective |
| P-2 | `requirements.txt` | Drop `streamlit`, `plotly`, `pynetbox`, `python-dotenv`, `python-pptx`, `requests`; keep gnpy, networkx, numpy, scipy, pandas, matplotlib, pillow, pytest (plus pyyaml/imagehash if needed) |
| P-3 | `.gitignore` | Add `archive/historical_datasets/**/*.zip`, `data/generated/`, review ZIP; keep secrets and env rules |
| P-4 | `.claude/launch.json` (gitignored) | Remove the Streamlit `ondm-app` entry |

## 4. DELETION MANIFEST — obsolete agentic application (needs your approval)

Every **tracked** item below stays recoverable from the tag `backup/pre-research-restructure-2026-11-20` and from GitHub history.
**Untracked** items (marked ⚠) are **not** in git, so deleting them cannot be undone unless they are archived first.

| ID | Path | Type | Size | Purpose | Tracked? |
|---|---|---|---|---|---|
| R-1 | `app/streamlit_app.py` | py | 27 KB | Streamlit agentic UI | yes (its uncommitted edits are backed up) |
| R-2 | `.streamlit/config.toml` | toml | 250 B | Streamlit theme | yes |
| R-3 | `ondm/agent.py` | py | 54 KB | VLM planning → codegen → sandbox → GNPy/NetBox agent loop | yes |
| R-4 | `ondm/sandbox.py` | py | 7 KB | Docker sandbox for VLM-generated NetworkX code | yes |
| R-5 | `ondm/inventory.py` | py | 13 KB | NetBox read client + fallback | yes |
| R-6 | `ondm/viz.py` | py | 4 KB | Plotly NOC-style rendering | yes |
| R-7 | `ondm/topology.py` | py | 4.6 KB | Loader for `data/semantic_pilot` (app-only) | yes |
| R-8 | `ondm/config.py`, `ondm/__init__.py` | py | 2.3 KB | App configuration | yes |
| R-9 | `ondm/__pycache__/` | pyc | — | Bytecode cache | no (regenerable) |
| R-10 | `sandbox/Dockerfile`, `sandbox/runner.py` | docker / py | 2.3 KB | Codegen sandbox image | yes |
| R-11 | `scripts/netbox_synthetic_inventory.py` | py | 15 KB | NetBox import/rollback | yes |
| R-12 | `scripts/smoke_agent.py` | py | 2.9 KB | Agent smoke test | yes |
| R-13 | `tests/test_core.py` | py | 3.7 KB | Tests for agent/sandbox/inventory only | yes |
| R-14 | `.env.example` | env | 638 B | NetBox variable template | yes |
| R-15 ⚠ | `.env` | env | 364 B | **Local NetBox tokens** | no — irreversible; see question 2 |
| R-16 ⚠ | `simulations/smoke/smoke_20261113_171023.json` | json | 5.8 KB | Agent smoke-run output | no |
| R-17 ⚠ | `.pytest_cache/`, `.ipynb_checkpoints/` | cache | 5 KB | Tool caches (the checkpoint is a 72-byte empty notebook) | no (regenerable) |
| R-18 | `notebooks/`, then empty `app/`, `ondm/`, `sandbox/`, `simulations/`, `results/` | dir | 0 | Empty after the archive moves | — |

**Not deleted:** any historical dataset, GNPy converter, research note, presentation, Ollama model, CUDA/driver, `.venv`, or anything outside this folder.

---

## 5. Proposed git procedure (after approval)

1. `git push origin backup/pre-research-restructure-2026-11-20 backup/main-pre-research-restructure-2026-11-20`, so the backup also exists on GitHub. **Needs your OK, because it publishes to GitHub.**
2. Create the branch `research/vlm-topology-classification` from `feature/agentic-digital-twin-demo`. That branch has the GNPy converters, which `main` lacks.
3. Commit the archive moves (`git mv`), then the approved deletions, then the new skeleton. Each step is a separate ordinary commit. No force-push and no history rewrite.
4. Push the branch and open a PR to `main` when you're ready.

## 6. Target layout

```text
archive/{historical_datasets, legacy_code, notes, presentations, unrelated, pre_cleanup_uncommitted_2026-11-20}
configs/  data/{pilot,generated,splits}  src/{generation,validation,evaluation}
scripts/  figures/  reports/  references/  tests/
README.md  RESEARCH_HANDOFF.md  requirements.txt  .gitignore
```

## 7. Decisions needed from you

1. **Approve deletion items R-1 … R-18** (all, or list any to keep).
2. **`.env` (R-15):** delete it, or move it to `archive/` (gitignored, never committed)? The read and write tokens would be lost if deleted.
3. **Push the two backup tags to GitHub** (step 5.1)?
4. **Branching:** use the new branch `research/vlm-topology-classification` (recommended), or restructure directly on `feature/agentic-digital-twin-demo`?
5. **Large archives:** keep the 28 MB 500-topology ZIP and `Document-OCR.zip` local-only (gitignored; recommended) rather than committing them?
