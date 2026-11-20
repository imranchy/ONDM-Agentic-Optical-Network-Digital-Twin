# Archive — historical ONDM research evidence

Everything here is preserved as-is from before the 2026-11-20 research restructure
(see `reports/CLEANUP_MANIFEST.md`). Nothing here is used by the active pipeline.
Full pre-restructure repository state: git tags `backup/pre-research-restructure-2026-11-20`
(feature branch, 6f5447c) and `backup/main-pre-research-restructure-2026-11-20` (main, 7e4532e).

| Folder | Contents |
|---|---|
| `historical_datasets/optical_topology_dataset.zip` | **Original 500-topology dataset** (501 graphs/images/YOLO labels, splits, generator, pix2struct scripts). Local only (gitignored). SHA-256 `42ff3933e952712dc2c50e0ed3854c6ca64fd1f20f4395f0cdba2dfce7418950`, 28,336,517 bytes. |
| `historical_datasets/optical_topology_pilot/` | Earliest 30-topology pilot |
| `historical_datasets/optical_topology_v2_pilot/` | v2 30-topology pilot |
| `historical_datasets/optical_topology_semantics_pilot/` | Corrected 30-topology semantic pilot (seed 2027) |
| `historical_datasets/data_semantic_pilot_app_copy/` | Former `data/semantic_pilot` — identical to the semantic pilot except `dataset.yaml` path |
| `historical_datasets/results_2026-10/` | Historical figures and structural/validation statistics |
| `historical_datasets/gnpy_runs/` | GNPy conversion/design outputs and logs for old-pilot `topo_0003` (+ agent-app span-80 cache) |
| `legacy_code/` | Previous generator (v2), audit/inspect scripts, `gnpy_engine.py`, `vlm.py`, NetBox import manifest (needed for NetBox rollback) |
| `notes/` | Previous handoff, scope, coding brief, semantic notes, analysis notebook, test questions |
| `presentations/` | Previous stakeholder decks and their build scripts |
| `pre_cleanup_uncommitted_2026-11-20/` | Copies of files that were uncommitted at audit time + diff |
| `unrelated/` (gitignored) | `Document-OCR.zip` (separate older project, SHA-256 `2e13f737…b407`) and the local NetBox `.env` |
