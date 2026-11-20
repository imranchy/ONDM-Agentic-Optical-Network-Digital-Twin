# ONDM_Optical_Topology_Pilot_125 — Dataset Report

Generated from `data/pilot/ONDM_pilot_125` (generator v0.1.0, master seed 20261120, config SHA-256 `e22074a3784e99e6…`, git `fd37f7f65e`, 2026-11-20T12:16:10+00:00).
All numbers in this report are read from generated/validated files by `src/reporting/build_report.py`.
**Status: PILOT — awaiting independent review. Not approved for scale-up, training or evaluation.**

## 1. Methodology summary

- Task: 5-class classification of optical transport *architecture* from an engineering schematic (taxonomy: `docs/TAXONOMY.md`).
- 125 scenarios, balanced (Long-haul / Core 25, Metro Optical Ring 25, Metro Aggregation 25, Data Center Interconnect 25, Submarine 25).
- **Long-haul / Core**: 25 distinct real topologies from Topology Bench (Matzner et al., JOCN 17(1):7-27; doi:10.5281/zenodo.13921775, CC-BY-4.0); 28 of 105 passed the eligibility filter, 77 were excluded with recorded reasons (`generation_log.json`). Graph, coordinates and lengths are real-derived; equipment is synthetic.
- **Metro ring, metro aggregation, DCI**: documented architectural templates with synthetic sites placed around real anchor cities (pool of 1654 unique Topology Bench node locations).
- **Submarine**: documented templates (point-to-point, branched trunk with BUs, festoon) with fully synthetic coordinates.
- Graph vertices are *sites*; inline amplifiers / repeaters are span equipment attached to links (never vertices).
- One uniform schematic style for every class (identical symbols, fonts, monochrome palette, fixed legend; no map background); scenario ids are assigned after a seeded global shuffle.

## 2. Generation families

| Class | Families (count) |
|---|---|
| Long-haul / Core | tb_real_derived_mesh (25) |
| Metro Optical Ring | dual_ring (10), dual_hub_ring (8), single_ring (7) |
| Metro Aggregation | partial_mesh_2hub (11), ring_2hub (6), ring_1hub (4), partial_mesh_1hub (4) |
| Data Center Interconnect | regional_dci (14), metro_dci (11) |
| Submarine | branched_trunk (12), festoon (8), point_to_point (5) |

## 3. Structural and geographic statistics (min / median / max)

| Class | Nodes | Links | Mean degree | Mean link km | Extent km | Inline amps |
|---|---|---|---|---|---|---|
| Long-haul / Core | 8 / 19 / 28 | 7 / 23 / 43 | 1.75 / 2.57 / 3.90 | 263.2 / 787.7 / 1353.3 | 1674 / 3216 / 4395 | 59 / 192 / 507 |
| Metro Optical Ring | 5 / 9 / 12 | 5 / 10 / 13 | 2.00 / 2.00 / 2.33 | 5.2 / 10.9 / 28.6 | 14 / 25 / 63 | 0 / 0 / 0 |
| Metro Aggregation | 9 / 15 / 21 | 14 / 24 / 36 | 2.46 / 3.20 / 3.69 | 10.5 / 18.5 / 30.8 | 23 / 40 / 61 | 0 / 0 / 0 |
| Data Center Interconnect | 3 / 6 / 9 | 3 / 7 / 12 | 2.00 / 2.33 / 3.00 | 14.7 / 101.2 / 528.4 | 20 / 179 / 649 | 0 / 6 / 23 |
| Submarine | 4 / 10 / 17 | 3 / 10 / 20 | 1.50 / 2.14 / 2.50 | 101.1 / 461.6 / 2748.8 | 404 / 4051 / 8097 | 0 / 84 / 301 |

| Class | Distinct unlabelled structures (WL) | Structural cues (validator, informative) |
|---|---|---|
| Long-haul / Core | 25 | structure_tree: 2, structure_ring_like: 3 |
| Metro Optical Ring | 18 | – |
| Metro Aggregation | 25 | distribution_tier_is_ring: 18 |
| Data Center Interconnect | 21 | structure_ring_like: 17, long_links_like_long_haul: 6 |
| Submarine | 25 | structure_tree: 5, long_links_like_long_haul: 17, structure_ring_like: 4 |

Duplicates: 0 role/medium-labelled isomorphic pairs; 18 pairs isomorphic when roles are ignored (structure only, see `duplicate_report.csv`); 0 near-identical image pairs (minimum image dHash distance 13 bits of 256).

## 4. Validation results

Status: PASS 114, PASS_WITH_WARNINGS 11. Errors: 0. Warnings: 29. Ambiguity warnings (another class rule also satisfied): 0.

| Check | Category | Description | ERROR | WARNING | INFO |
|---|---|---|---|---|---|
| S1_node_ids | structural | node ids unique and well-formed (S\d\d) | 0 | 0 | 0 |
| S2_edge_endpoints | structural | every edge endpoint is a defined node | 0 | 0 | 0 |
| S3_dup_edges | structural | no duplicate edges or self-loops | 0 | 0 | 0 |
| S4_connected | structural | graph connected, no isolated nodes | 0 | 0 | 0 |
| S5_counts | structural | declared node/edge counts match lists | 0 | 0 | 0 |
| S6_class_structure | structural | class-specific structural requirements | 0 | 0 | 9 |
| S7_duplicates | structural | no isomorphic (role+medium labelled) duplicate graphs in dataset | 0 | 0 | 0 |
| S8_near_duplicate_images | structural | no near-identical images (dHash Hamming <= 4) | 0 | 0 | 0 |
| E1_locations | equipment | every equipment item references a valid node or edge | 0 | 0 | 0 |
| E2_switching | equipment | ROADM/OADM equipment degree equals graph degree; one per site | 0 | 0 | 0 |
| E3_amplifiers | equipment | ILA only on terrestrial links, repeaters only undersea; counts/positions consistent | 0 | 0 | 0 |
| E4_spans | equipment | spans x span length = link length; span length <= declared maximum | 0 | 0 | 0 |
| E5_class_compat | equipment | equipment types compatible with the network class | 0 | 0 | 0 |
| E6_terminals | equipment | terminal-bearing sites have terminal equipment; BUs have none | 0 | 0 | 0 |
| E7_dci_reach | equipment | 400ZR pluggables only where DC-to-DC path <= declared reach | 0 | 0 | 0 |
| E8_attributes | equipment | every equipment item carries type, location and assumption id | 0 | 0 | 0 |
| G1_latlon | geographic | latitude/longitude within valid ranges | 0 | 0 | 0 |
| G2_length_ge_gc | geographic | fibre length >= great-circle distance recomputed from coordinates | 0 | 0 | 0 |
| G3_route_factor | geographic | fibre/great-circle ratio within [1.0, 2.0] | 0 | 19 | 0 |
| G4_scope | geographic | geographic extent and link lengths plausible for the class | 0 | 1 | 0 |
| G5_provenance | geographic | coordinate/length provenance recorded and consistent with class | 0 | 0 | 0 |
| D1_image | diagram | image readable, expected size, not blank | 0 | 0 | 0 |
| D2_complete | diagram | every node and edge drawn; drawn labels match graph JSON | 0 | 0 | 0 |
| D3_in_bounds | diagram | all labels inside the drawing area | 0 | 0 | 0 |
| D4_font | diagram | label font size >= 14 px (node) / 12 px (link) at native resolution | 0 | 0 | 0 |
| D5_overlap | diagram | label overlaps (area > 15% of smaller label) | 0 | 9 | 0 |
| D6_leakage | diagram | no category names / hints in drawn text or PNG metadata | 0 | 0 | 0 |
| D7_style | diagram | identical style hash and legend in every image | 0 | 0 | 0 |
| D8_symbols | diagram | drawn equipment line matches inventory | 0 | 0 | 0 |
| D9_amp_markers | diagram | amplifier markers drawn = min(count, 5) | 0 | 0 | 0 |
| L1_rule | label | assigned class satisfies its own evidence rule | 0 | 0 | 0 |
| L2_ambiguity | label | no other class rule satisfied (else ambiguity warning) | 0 | 0 | 0 |
| L3_structural_cue | label | structure-only cues pointing elsewhere (informative) | 0 | 0 | 72 |

Warnings are listed individually in `warnings.csv`; failures in `failed_scenarios.csv`.

### Requires human review (not automated)

- Engineering realism of each architecture template and of the equipment assignment (expert judgement).
- Visual legibility at the resolution a VLM actually receives (automated check uses native 1600x1200 px).
- Whether a human expert can identify the class from each diagram without metadata (blind review of contact sheets).
- Submarine synthetic coordinates may fall on land; not checked against coastlines (assumption A8).
- Whether Topology Bench networks selected as long-haul are optical core networks rather than IP-layer PoP maps.
- Overlap of link labels with amplifier markers or lines below the overlap threshold.

## 5. Declared assumptions

- **A1_tb_lengths** — Long-haul link lengths are Topology Bench 'Computed Length (km)' values, copied unchanged. For 104/105 real topologies these equal 1.5 x great-circle distance (verified in references/topology_bench/real_catalog.json), i.e. Topology Bench already applies a route factor; no further factor is applied. They are not surveyed fibre routes.
- **A2_synthetic_route_factor** — Synthetic terrestrial fibre length = great-circle distance x route factor drawn uniformly from [1.2, 1.6]. Synthetic undersea length = great-circle x [1.05, 1.25]. These are modelling assumptions, not measured rights-of-way or real cable routes.
- **A3_terrestrial_span** — Terrestrial inline amplifier (ILA/EDFA) count per link = ceil(L / S) - 1 with a per-scenario maximum span length S drawn from [70, 100] km; spans are equal length. ~80 km spans are a common planning assumption (e.g. GNPy example networks); not a standard.
- **A4_submarine_repeater** — Repeatered undersea segments: repeater count = ceil(L / S) - 1 with S drawn from [50, 90] km. Segments <= 350 km may be unrepeatered (festoon). Assumption, not a design.
- **A5_dci_reach** — Metro DCI links up to 120 km are terminated by coherent pluggables (400ZR-class, OIF 400ZR targets amplified point-to-point links of roughly 80-120 km); longer DCI links use ZR+/transponder-class terminals and inline amplifiers per A3.
- **A6_terminals** — Transponder / pluggable counts per site are synthetic and indicative only; they encode where traffic is terminated, not dimensioned capacity.
- **A7_coordinates_metro** — Metro ring, metro aggregation and DCI site coordinates are synthetic offsets around a real anchor city taken from the Topology Bench node lists; the anchor is real, the sites are not.
- **A8_coordinates_submarine** — Submarine landing-station and branching-unit coordinates are fully synthetic, were not checked against coastlines, and do not represent any existing cable system.
- **A9_roadm_degree** — ROADM degree equals the number of fibre links at the site.

## 6. Limitations and open questions

1. **Label checks are partly circular.** The validator's evidence rules read roles that the generator assigned; passing them shows internal consistency, not realism. Blind expert review of the contact sheets is the real test.
2. **Strong but legitimate cues.** Inline-amplifier presence and the distance scale differ sharply between classes (e.g. metro classes have no ILAs; long-haul always has them). These are genuine engineering evidence, but a model could rely on the km magnitudes alone. A distance-ablated rendering is a candidate control experiment.
3. **Metro-ring structural diversity is inherently low** (18 distinct unlabelled structures in 25). At 200 per class, many ring graphs will be isomorphic (differing in hub roles, distances, geography). Splits must group isomorphic structures; the duplicate policy for 1,000 scenarios needs a decision.
4. **Long-haul source pool is small** (28 eligible real topologies). 200 long-haul scenarios would need ~7 documented modifications per source (e.g. node removal, subgraph extraction, link addition), all grouped by source in splits.
5. Some Topology Bench topologies are IP/PoP-level maps; their fit as *optical* core networks needs expert confirmation. Topology Bench lengths include a 1.5 route factor (verified), not surveyed routes.
6. Submarine coordinates are synthetic and may fall on land; no coastline check, no real cable represented.
7. Equipment counts are indicative assignments; no GNPy simulation was executed for any pilot scenario.
8. Metro-aggregation drawings can have crossing links after schematic layout; legibility judged acceptable by automated checks but should be reviewed.
9. No OCR-based leakage check: leakage is checked on every drawn text string from the render manifest and on PNG metadata.

## 7. Files

- Per network: `networks/network_NNNN.{png,graph.json,equipment.json,metadata.json}`; `render_manifests/` (validation aid only, not a model input).
- `manifest.csv` (ground truth + group keys), `generation_config.json`, `generation_log.json`.
- Reports: `reports/pilot_125/` · Figures (PNG + PDF): `figures/pilot_125/`.
