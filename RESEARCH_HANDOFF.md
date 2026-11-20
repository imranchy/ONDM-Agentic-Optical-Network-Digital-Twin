# RESEARCH_HANDOFF — ONDM VLM Optical Topology Classification

_Last updated: 2026-11-20 · branch `research/vlm-topology-classification`_

## 1. Completed

| Step | Result |
|---|---|
| Audit + cleanup manifest | `reports/CLEANUP_MANIFEST.md`, approved by the PI on 2026-11-20 |
| Backups | Tags `backup/pre-research-restructure-2026-11-20` (6f5447c) and `backup/main-pre-research-restructure-2026-11-20` (7e4532e), pushed to GitHub. Uncommitted files copied to `archive/pre_cleanup_uncommitted_2026-11-20/`. |
| Preservation | 500-topology ZIP, three 30-topology pilots, the app copy of the semantic pilot, historical results, GNPy runs, legacy generator, notes and decks are all under `archive/` (see `archive/README.md`) |
| Removal | Streamlit app, agent, Docker sandbox, NetBox client and importer, agent tests, `.env.example` (approved items R-1…R-18). The local NetBox `.env` was moved to `archive/unrelated/` (gitignored). |
| Taxonomy | `docs/TAXONOMY.md` + `src/generation/taxonomy.py` (5 classes, evidence rules, declared assumptions A1–A9) |
| Topology Bench inspection | `references/topology_bench/README.md`. 105 real topologies converted to `real_catalog.json`. Route factor of 1.5 confirmed. 11 sources found inconsistent. |
| Pilot generation | 125 networks (5 × 25), `data/pilot/ONDM_pilot_125/`, 4 files per network + render manifests |
| Validation | 33 automated checks (`src/validation/validate_dataset.py`) and independent label rules (`label_rules.py`) |
| Figures / report | `figures/pilot_125/` (13 figures, PNG + PDF), `reports/pilot_125/DATASET_REPORT.md` |
| Tests | `tests/test_pipeline.py`: 26 tests pass |
| Review package | `ONDM_Optical_Topology_Pilot_125_Review.zip` (project root, gitignored), built by `scripts/package_review.py` |

## 2. Dataset-generation methodology (short)

- **Long-haul / core:** 25 distinct real Topology Bench topologies (from 28 eligible), unchanged graph, coordinates
  and lengths. ROADM at every site. ILAs at ceil(L/S)−1 per link, with S ~ U[70,100] km per scenario.
- **Metro ring:** single ring, dual-hub ring or two rings sharing hubs. OADM ring sites, HUB ROADMs. Links of 5–29 km.
- **Metro aggregation:** 1–2 hubs → 3–6 distribution ROADMs (ring or partial mesh) → 4–14 CO sites, dual-homed with probability p.
- **DCI:** metro (3–7 DCs, mesh or ring+chords, 400ZR if every DC-DC path is ≤ 120 km) or regional (2–4 campuses in
  real cities 80–450 km apart, optional campus ROADMs, diverse route through an intermediate ROADM, ZR+ with ILAs).
- **Submarine:** point-to-point (optional dual landing), branched trunk (1–3 BUs) or festoon. Repeaters every 50–90 km
  on segments over 350 km. Each CLS has one or two diverse backhaul POPs.
- Sites are graph nodes; amplifiers and repeaters are link equipment. Synthetic fibre length = great-circle × U[1.2,1.6]
  (undersea × U[1.05,1.25]).
- Uniform monochrome schematic: fixed symbols and legend, collision-aware labels, ids shuffled globally.

## 3. Generated dataset inventory

| Item | Location | In git? |
|---|---|---|
| Pilot JSON (graph / equipment / metadata), manifests | `data/pilot/ONDM_pilot_125/` | yes |
| Pilot PNG diagrams (125 × ~0.2 MB) | same | no (regenerable; in review ZIP) |
| Figures | `figures/pilot_125/` | yes |
| Reports | `reports/pilot_125/` | yes |
| Historical datasets | `archive/historical_datasets/` | yes, except the 28 MB 500-topology ZIP (local, SHA-256 recorded) |

## 4. Validation findings (pilot)

- **0 failures**, 114 PASS, 11 PASS_WITH_WARNINGS, 0 ambiguity warnings, 0 labelled duplicates, 0 near-identical images.
- Warnings:
  - 9 label-overlap warnings (long-haul and submarine)
  - 19 link-level route-ratio warnings (ratio 2.0–2.75) in two real-derived long-haul sources (JPN12, JPN25)
  - 1 DCI link of 1,027 km above the 900 km plausibility envelope
- Fixes found by validation during development, before this pilot:
  - A Topology Bench source with impossible lengths (now excluded by rule)
  - Long-haul sources with links over 3,000 km (now excluded)
  - Regional DCI sites without diverse routes (builder fixed)
  - Clipped legend text (renderer fixed)
- See `reports/pilot_125/DATASET_REPORT.md` §4 and §6.

## 5. Scientific assumptions

A1–A9 in `src/generation/taxonomy.py` (copied into every equipment file and into the report). None is presented as
a standard. **No GNPy simulation was run for any pilot scenario.** The GNPy converters are kept in `src/validation/gnpy/`
for later engineering checks.

## 6. Reproduction

```powershell
.\scripts\run_pilot.ps1
.venv\Scripts\python scripts\package_review.py
```

## 7. Known limitations

1. Label rules read generator-assigned roles. They show internal consistency, not realism. Blind expert review is needed.
2. Distance scale and ILA presence are strong, legitimate cues. A distance-ablated control rendering is recommended.
3. Metro rings have low structural diversity (18 distinct structures in 25).
4. The long-haul pool has only 28 real sources.
5. Some Topology Bench networks may be IP or PoP maps.
6. Submarine coordinates are synthetic and are not checked against coastlines.
7. Metro-aggregation drawings can contain crossing links.
8. Leakage is checked on rendered text strings and PNG metadata, not by OCR.

## 8. Pending decisions (PI)

1. **Approve or revise the pilot** after the independent review. Scaling to 1,000 is blocked until then.
2. Duplicate policy at 200 per class: accept role/distance-distinct isomorphic rings (grouped in splits), or add ring
   variants (ring + chords, three or more interconnected rings)?
3. Long-haul scale-up: documented modifications of the 28 sources (node removal, subgraph extraction, link addition) ×
   ~7 each, grouped by source? Or add further published core topologies?
4. Whether to add a distance-ablated rendering as a control (later, not a second style for training).
5. VLM shortlist availability: Qwen3-VL-2B/4B, SmolVLM2-2.2B and Gemma 3 4B are **not** in Ollama yet
   (present: `qwen3-vl:8b(-instruct)`, `gemma3:12b-it-qat`; `gemma3:4b` was not listed). Downloads need approval.

## 9. Next milestones

1. Independent review of `ONDM_Optical_Topology_Pilot_125_Review.zip`, then fixes.
2. Generate 1,000 networks (200/class) with a group-aware duplicate policy; validate.
3. Group-based 70/15/15 splits (group keys: Topology Bench source, isomorphism class for rings, synthetic family seed).
4. Zero-shot benchmark of 4 compact VLMs (accuracy, macro-F1, per-class P/R/F1, confusion matrix, invalid rate, latency).
5. Domain-specific SFT on train/val only, compared on the identical test split.
6. Monday 23 Nov 2026 stakeholder deck: dataset method, validation and roadmap. No model results yet.
