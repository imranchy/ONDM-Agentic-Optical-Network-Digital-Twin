# Optical Network Topology Classification with Compact Vision-Language Models (ONDM)

Research code and data for testing how accurately **compact VLMs** can classify realistic **optical
transport network architectures** from engineering topology diagrams. A later study will test whether
optical-domain supervised fine-tuning improves accuracy.

> **Current phase (Nov 2026): dataset pilot under review.** 125 networks (5 × 25) have been generated
> and validated. The 1,000-network dataset, VLM evaluation and fine-tuning are **not started** and
> wait for pilot approval.

The previous agentic digital-twin prototype (Streamlit / NetBox / sandboxed codegen) was retired on
2026-11-20. It is preserved in git (tag `backup/pre-research-restructure-2026-11-20`), and its datasets
are kept under `archive/`.

## Five classes

| Class | Key visible evidence |
|---|---|
| Long-haul / Core | ROADM mesh over national or continental distances; amplified links (ILAs) |
| Metro Optical Ring | Ring(s) of OADM/ROADM sites with hub ROADMs; short unamplified links |
| Metro Aggregation | Hub → distribution ROADMs → many single- or dual-homed CO access sites |
| Data Center Interconnect | DC sites with coherent DCI terminals (400ZR / ZR+); diverse routes |
| Submarine | Cable landing stations, undersea segments with repeaters, BUs, terrestrial backhaul |

The full definitions, inclusion and exclusion rules, and ambiguities are in [docs/TAXONOMY.md](docs/TAXONOMY.md).
Long-haul topologies are derived from **Topology Bench** (Matzner et al., JOCN 17(1):7-27;
doi:10.5281/zenodo.13921775, CC-BY-4.0). The other classes are synthetic templates with declared assumptions.

## Repository layout

```text
archive/            historical datasets (500-topology set, 30-topology pilots), legacy code, notes, decks
configs/            generation configs (pilot_125.json)
data/pilot/         generated pilot (JSON committed; PNGs regenerable, gitignored)
docs/               taxonomy and methodology
figures/pilot_125/  contact sheets and statistics figures (PNG + PDF)
references/         Topology Bench catalogue + provenance notes, GNPy notes
reports/            cleanup manifest, validation reports, dataset report
scripts/            reproduction and packaging scripts
src/generation/     Topology Bench loader, taxonomy, scenario builders, renderer, dataset generator
src/validation/     validator, independent label rules, GNPy converters (kept, not used by the pilot)
src/reporting/      figures and report builder
src/evaluation/     (reserved for the zero-shot VLM benchmark, after approval)
tests/              pytest suite
```

## Reproduce the pilot (Windows PowerShell)

```powershell
.venv\Scripts\python -m pip install -r requirements.txt
.\scripts\run_pilot.ps1
```

`run_pilot.ps1` rebuilds the Topology Bench catalogue (Topology Bench `real_topologies.zip` must be
in `references/topology_bench/raw/`, see `references/topology_bench/README.md`). It then generates
the 125 networks, validates them, draws the figures, writes `reports/pilot_125/DATASET_REPORT.md`
and runs the tests. The output is deterministic for a given config and seed.

Status and next steps: [RESEARCH_HANDOFF.md](RESEARCH_HANDOFF.md).
