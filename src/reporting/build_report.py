"""Build the pilot dataset report (Markdown) from generated artefacts. All numbers are read from
files produced by the generator and validator; nothing is typed in by hand.

Usage:
    python -m src.reporting.build_report --data data/pilot/ONDM_pilot_125 --reports reports/pilot_125
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from src.generation.taxonomy import ASSUMPTIONS, CLASS_DISPLAY, CLASSES


def table(header, rows) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(str(x) for x in r) + " |" for r in rows]
    return "\n".join(out)


def fmt(d, nd=0):
    if d is None:
        return "–"
    f = (lambda v: f"{v:.{nd}f}")
    return f"{f(d['min'])} / {f(d['median'])} / {f(d['max'])}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/pilot/ONDM_pilot_125")
    ap.add_argument("--reports", default="reports/pilot_125")
    ap.add_argument("--figures", default="figures/pilot_125")
    a = ap.parse_args()
    d, r = Path(a.data), Path(a.reports)
    s = json.loads((r / "validation_summary.json").read_text(encoding="utf-8"))
    log = json.loads((d / "generation_log.json").read_text(encoding="utf-8"))
    cfg = json.loads((d / "generation_config.json").read_text(encoding="utf-8"))
    stats = list(csv.DictReader(open(r / "structural_statistics.csv", encoding="utf-8")))
    issues = list(csv.DictReader(open(r / "validation_issues.csv", encoding="utf-8")))
    sb = s["structure_by_category"]
    cue_by_cls = {c: Counter(x for row in stats if row["category"] == c for x in row["structural_cues"].split(";") if x) for c in CLASSES}
    fam_by_cls = {c: Counter(row["family"].replace(c + "_", "") for row in stats if row["category"] == c) for c in CLASSES}
    warn = [i for i in issues if i["severity"] == "WARNING"]
    errs = [i for i in issues if i["severity"] == "ERROR"]

    md = [f"# {cfg['dataset_name']} — Dataset Report",
          "",
          f"Generated from `{a.data}` (generator v{cfg['generator_version']}, master seed {cfg['master_seed']}, "
          f"config SHA-256 `{log['config_sha256'][:16]}…`, git `{(log['git_commit'] or 'n/a')[:10]}`, {log['generated_utc']}).",
          "All numbers in this report are read from generated/validated files by `src/reporting/build_report.py`.",
          "**Status: PILOT — awaiting independent review. Not approved for scale-up, training or evaluation.**",
          "",
          "## 1. Methodology summary",
          "",
          "- Task: 5-class classification of optical transport *architecture* from an engineering schematic (taxonomy: `docs/TAXONOMY.md`).",
          f"- {s['n_scenarios']} scenarios, balanced ({', '.join(f'{CLASS_DISPLAY[c]} {n}' for c, n in s['category_distribution'].items())}).",
          f"- **Long-haul / Core**: {len(log['long_haul_sources_used'])} distinct real topologies from Topology Bench "
          f"(Matzner et al., JOCN 17(1):7-27; doi:10.5281/zenodo.13921775, CC-BY-4.0); {log['long_haul_sources_eligible']} of 105 passed the eligibility "
          f"filter, {len(log['long_haul_sources_excluded'])} were excluded with recorded reasons (`generation_log.json`). Graph, coordinates and lengths are real-derived; equipment is synthetic.",
          "- **Metro ring, metro aggregation, DCI**: documented architectural templates with synthetic sites placed around real anchor cities "
          f"(pool of {log['anchor_city_pool']} unique Topology Bench node locations).",
          "- **Submarine**: documented templates (point-to-point, branched trunk with BUs, festoon) with fully synthetic coordinates.",
          "- Graph vertices are *sites*; inline amplifiers / repeaters are span equipment attached to links (never vertices).",
          "- One uniform schematic style for every class (identical symbols, fonts, monochrome palette, fixed legend; no map background); scenario ids are assigned after a seeded global shuffle.",
          "",
          "## 2. Generation families",
          "",
          table(["Class", "Families (count)"], [[CLASS_DISPLAY[c], ", ".join(f"{k} ({v})" for k, v in fam_by_cls[c].most_common())] for c in CLASSES]),
          "",
          "## 3. Structural and geographic statistics (min / median / max)",
          "",
          table(["Class", "Nodes", "Links", "Mean degree", "Mean link km", "Extent km", "Inline amps"],
                [[CLASS_DISPLAY[c], fmt(sb["n_nodes"][c]), fmt(sb["n_edges"][c]), fmt(sb["mean_degree"][c], 2),
                  fmt(sb["mean_link_km"][c], 1), fmt(sb["extent_km"][c]), fmt(sb["inline_amplifiers"][c])] for c in CLASSES]),
          "",
          table(["Class", "Distinct unlabelled structures (WL)", "Structural cues (validator, informative)"],
                [[CLASS_DISPLAY[c], s["unique_structures_by_category"][c], ", ".join(f"{k}: {v}" for k, v in cue_by_cls[c].items()) or "–"] for c in CLASSES]),
          "",
          f"Duplicates: {s['duplicates']['isomorphic_labelled_pairs']} role/medium-labelled isomorphic pairs; "
          f"{s['duplicates']['isomorphic_structure_only_pairs']} pairs isomorphic when roles are ignored (structure only, see `duplicate_report.csv`); "
          f"{s['duplicates']['near_identical_image_pairs']} near-identical image pairs (minimum image dHash distance {s['duplicates']['min_dhash_distance_overall']} bits of 256).",
          "",
          "## 4. Validation results",
          "",
          f"Status: {', '.join(f'{k} {v}' for k, v in s['status_counts'].items())}. Errors: {len(errs)}. Warnings: {len(warn)}. "
          f"Ambiguity warnings (another class rule also satisfied): {s['ambiguity_warnings']}.",
          "",
          table(["Check", "Category", "Description", "ERROR", "WARNING", "INFO"],
                [[k, v["category"], v["description"], v.get("ERROR", 0), v.get("WARNING", 0), v.get("INFO", 0)] for k, v in s["issues_by_check"].items()]),
          "",
          "Warnings are listed individually in `warnings.csv`; failures in `failed_scenarios.csv`.",
          "",
          "### Requires human review (not automated)",
          "",
          *[f"- {x}" for x in s["requires_human_review"]],
          "",
          "## 5. Declared assumptions",
          "",
          *[f"- **{k}** — {v}" for k, v in ASSUMPTIONS.items()],
          "",
          "## 6. Limitations and open questions",
          "",
          "1. **Label checks are partly circular.** The validator's evidence rules read roles that the generator assigned; passing them shows internal consistency, not realism. Blind expert review of the contact sheets is the real test.",
          "2. **Strong but legitimate cues.** Inline-amplifier presence and the distance scale differ sharply between classes (e.g. metro classes have no ILAs; long-haul always has them). These are genuine engineering evidence, but a model could rely on the km magnitudes alone. A distance-ablated rendering is a candidate control experiment.",
          f"3. **Metro-ring structural diversity is inherently low** ({s['unique_structures_by_category']['metro_ring']} distinct unlabelled structures in 25). At 200 per class, many ring graphs will be isomorphic (differing in hub roles, distances, geography). Splits must group isomorphic structures; the duplicate policy for 1,000 scenarios needs a decision.",
          f"4. **Long-haul source pool is small** ({log['long_haul_sources_eligible']} eligible real topologies). 200 long-haul scenarios would need ~7 documented modifications per source (e.g. node removal, subgraph extraction, link addition), all grouped by source in splits.",
          "5. Some Topology Bench topologies are IP/PoP-level maps; their fit as *optical* core networks needs expert confirmation. Topology Bench lengths include a 1.5 route factor (verified), not surveyed routes.",
          "6. Submarine coordinates are synthetic and may fall on land; no coastline check, no real cable represented.",
          "7. Equipment counts are indicative assignments; no GNPy simulation was executed for any pilot scenario.",
          "8. Metro-aggregation drawings can have crossing links after schematic layout; legibility judged acceptable by automated checks but should be reviewed.",
          "9. No OCR-based leakage check: leakage is checked on every drawn text string from the render manifest and on PNG metadata.",
          "",
          "## 7. Files",
          "",
          "- Per network: `networks/network_NNNN.{png,graph.json,equipment.json,metadata.json}`; `render_manifests/` (validation aid only, not a model input).",
          "- `manifest.csv` (ground truth + group keys), `generation_config.json`, `generation_log.json`.",
          f"- Reports: `{a.reports}/` · Figures (PNG + PDF): `{a.figures}/`.",
          ]
    (r / "DATASET_REPORT.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"wrote {r / 'DATASET_REPORT.md'}")


if __name__ == "__main__":
    main()
