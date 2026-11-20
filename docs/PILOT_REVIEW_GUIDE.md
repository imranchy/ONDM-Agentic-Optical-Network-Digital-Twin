# Pilot Review Guide — ONDM Optical Topology Pilot (125)

This package contains a **pilot** dataset for 5-class optical transport architecture classification from
engineering schematics. Please review it independently before it is scaled to 1,000 networks.

## Where to look

| What | Path |
|---|---|
| Class definitions, evidence rules, ambiguities | `docs/TAXONOMY.md` |
| Dataset report (method, statistics, validation, limitations) | `reports/pilot_125/DATASET_REPORT.md` |
| All 125 diagrams at a glance | `figures/pilot_125/01_contact_sheet_all.png` |
| Per-class sheets (25 each) | `figures/pilot_125/02…06_contact_sheet_*.png` |
| One per class | `figures/pilot_125/07_representative_per_class.png` |
| Individual network files | `data/pilot/ONDM_pilot_125/networks/network_NNNN.*` |
| Ground truth | `data/pilot/ONDM_pilot_125/manifest.csv` (also each `*.metadata.json`) |
| Validation outputs | `reports/pilot_125/*.csv`, `validation_summary.json` |
| Source-data inspection (Topology Bench) | `references/topology_bench/README.md` |
| Code | `src/generation`, `src/validation`, `src/reporting`; reproduce with `scripts/run_pilot.ps1` |

## Questions we would like answered

1. **Blind classification:** without opening `manifest.csv`, can you assign each diagram to one of the 5 classes from `docs/TAXONOMY.md`? Which ones are ambiguous, and why?
2. **Engineering realism:** are the templates (ring, aggregation, DCI, submarine), equipment assignments and declared assumptions A1–A9 defensible? Is anything unrealistic or over-simplified?
3. **Shortcut risk:** do diagrams contain non-engineering cues that reveal the class (layout, density, label patterns)? Are the legitimate cues (distance scale, ILA/repeater presence, site roles) too easy?
4. **Long-haul sources:** are the selected Topology Bench networks suitable as optical core examples?
5. **Legibility:** are the labels readable at typical VLM input resolutions (e.g. 448–1024 px on the long side)?
6. **Scale-up:** see RESEARCH_HANDOFF.md §8 (duplicate policy for rings, long-haul source modifications).

Class names appear only in captions outside the diagrams on the contact sheets. They are never drawn inside a dataset image.
