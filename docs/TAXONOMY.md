# Five-Class Optical Transport Architecture Taxonomy

**Version:** 0.1 (pilot) · 2026-11-20 · Machine-readable constants: `src/generation/taxonomy.py`

The task is to classify the **operational architecture** of an optical transport network from an
engineering schematic. Labels describe *what the network is for and how it is built*, not just
graph shape. Rings appear in core networks; meshes appear in metro aggregation; DCI links can be
long; submarine systems hand off to terrestrial networks. So every class is defined by a
**conjunction of visible engineering evidence** (site roles, equipment, link medium, distance
scale, hierarchy), with graph structure as supporting evidence only.

Passive Optical Networks (PON) are out of scope.

> All numeric ranges here are **generation assumptions** consistent with commonly reported
> practice (see `ASSUMPTIONS` in `taxonomy.py`). None is claimed to be a standardised limit.

## Common visual vocabulary (identical in every diagram)

| Symbol | Meaning | Graph object |
|---|---|---|
| Square | ROADM switching site (`ROADM`, `HUB ROADM`, backhaul `POP ROADM`) | node |
| Diamond | OADM add/drop site | node |
| Circle | Central-office access site with terminal equipment (`CO`) | node |
| Hexagon | Data-centre site (`DC`) with coherent DCI terminals | node |
| Pentagon | Cable landing station (`CLS`, hosts SLTE + power feed) | node |
| Small filled circle | Undersea branching unit (`BU`) | node |
| Small triangles on a link | Inline amplifiers (`ILA`, terrestrial) / repeaters (`RPT`, undersea) | edge equipment |
| Solid line | Terrestrial fibre link | edge |
| Dashed line | Undersea cable segment | edge |

Every node shows a neutral site code (`S01`…) and its equipment line (for example `ROADM-3D` or `CO TRM×2`).
Every link shows its fibre length and, when present, the amplifier or repeater count. The same legend,
colours, fonts and canvas size are used for all classes. Category names never appear.

---

## 1. Long-haul / Core (`long_haul_core`)

| Aspect | Definition |
|---|---|
| Purpose | Carry aggregated traffic between cities and regions across a country or continent |
| Structure | Meshed or partially meshed ROADM network. Rings and spurs are allowed. |
| Node roles | ROADM switching sites only (multi-degree); terminals collocated at ROADMs |
| Equipment | Multi-degree ROADMs, coherent transponders, boosters/pre-amps, **inline amplifier sites on most links** |
| Spans | Links of hundreds to thousands of km, divided into ~70–100 km amplified spans |
| Geographic scope | National / continental. Pilot sources: geographic extent 1,500–6,000 km. |
| Transmission | Coherent DWDM over amplified spans (C/C+L band). Not modelled further. |
| Resilience | Mesh path diversity (protection/restoration). Degree ≥ 2 is typical but not required. |
| Allowed variations | Ladder, mesh, ring-plus-chords, spurs to edge cities |
| Inclusion | All sites are ROADMs **and** link scale is long (mean link ≥ 150 km or extent ≥ 800 km) **and** ILAs are present on links |
| Exclusion | Any DC, CLS, BU, CO or undersea segment |
| Ambiguity | Regional DCI with ROADMs and ILAs; large regional networks with short links (metro-regional). Flagged by the validator. |

**Provenance:** derived from real topologies in Topology Bench (Matzner et al., JOCN 17(1), 2024/25;
doi:10.5281/zenodo.13921775, CC-BY-4.0). The topology, coordinates and lengths are real-derived.
The equipment is synthetic.

## 2. Metro Optical Ring (`metro_ring`)

| Aspect | Definition |
|---|---|
| Purpose | Interconnect central offices or sites within one metropolitan area over protected rings |
| Structure | One ring or two rings interconnected at shared hub sites. Most nodes have degree 2. |
| Node roles | 1–2 `HUB ROADM`s (gateway / ring interconnect) plus `OADM`s or 2-degree ROADMs |
| Equipment | OADM/2-degree ROADMs, hub multi-degree ROADM, transponders. Usually **no ILAs** (short spans). |
| Spans | Links of 3–35 km. Ring circumference of tens to ~200 km. |
| Geographic scope | One metro area. Extent ≤ ~80 km in the pilot. |
| Transmission | DWDM, often unamplified or with terminal amplifiers only |
| Resilience | Ring protection (two disjoint paths between any pair) |
| Allowed variations | Single ring, dual-hub ring, two rings sharing hubs (figure-8 / ladder) |
| Inclusion | Every node lies on a cycle, ≥ 60% of nodes have degree 2, short links, no access tier, no DC/CLS |
| Exclusion | Dual-homed access tiers, DC endpoints, undersea segments, links > 100 km |
| Ambiguity | Metro aggregation networks whose aggregation tier is a ring |

**Provenance:** synthetic architectural template. Anchor city coordinates come from Topology Bench;
site positions are synthetic.

## 3. Metro Aggregation (`metro_aggregation`)

| Aspect | Definition |
|---|---|
| Purpose | Collect traffic from many access sites and concentrate it towards hub/gateway sites |
| Structure | **Hierarchical:** hub tier → aggregation tier (ring or partial mesh) → access tier (single- or dual-homed spurs) |
| Node roles | 1–2 `HUB ROADM`s, 3–6 aggregation `ROADM`s, 4–14 access `CO` sites |
| Equipment | Multi-degree ROADMs at hubs and aggregation sites; terminal equipment at COs. ILAs are rare. |
| Spans | Access links 2–20 km. Aggregation and hub links 8–60 km. |
| Geographic scope | One metro area or region. Extent ≤ ~150 km. |
| Resilience | Dual-homing of access sites. Ring or mesh at the aggregation tier. |
| Allowed variations | Ring or mesh aggregation tier; mix of single- and dual-homed COs; 1 or 2 hubs |
| Inclusion | Three visible tiers (HUB, ROADM, CO), ≥ 4 CO sites, short links, no DC/CLS |
| Exclusion | Flat single ring with no access tier; DC endpoints; undersea segments |
| Ambiguity | Aggregation tier forming a ring (structurally similar to a metro ring). Flagged. |

**Provenance:** synthetic architectural template (same anchor-city rule as class 2).

## 4. Data Center Interconnect (`dci`)

| Aspect | Definition |
|---|---|
| Purpose | High-capacity connectivity between data-centre sites (campus, metro or regional) |
| Structure | Point-to-point, full mesh or dual-star between DC sites, optionally via ROADM sites. Diverse routes. |
| Node roles | 2–8 `DC` sites. Regional variants may include 1–3 intermediate `ROADM`s. |
| Equipment | Coherent DCI terminals at DCs: 400ZR-class pluggables for links ≤ 120 km, ZR+/transponders beyond. ILAs on regional links. |
| Spans | Metro DCI 10–80 km. Regional DCI 80–600 km. |
| Geographic scope | Metro to regional |
| Resilience | Every DC has ≥ 2 diverse links |
| Inclusion | ≥ 2 DC sites, and DCs are the dominant terminal sites |
| Exclusion | CLS/undersea segments; CO access tiers |
| Ambiguity | Regional DCI with ROADMs and ILAs can resemble long-haul. Flagged when the mean link is ≥ 250 km. |

**Provenance:** synthetic architectural template (same anchor-city rule as class 2).

## 5. Submarine Optical Network (`submarine`)

| Aspect | Definition |
|---|---|
| Purpose | Carry traffic across seas and oceans between landing points |
| Structure | Trunk between cable landing stations, optionally with branching units and branches, or a coastal festoon. Each CLS has terrestrial backhaul to a POP ROADM. |
| Node roles | 2–6 `CLS`, 0–3 `BU`, 1 `POP ROADM` per CLS |
| Equipment | SLTE and power feed equipment at CLS. **Undersea repeaters** on repeatered segments. BUs (no terminals). |
| Spans | Trunks of 1,000–9,000 km with repeaters every 50–90 km. Festoon segments of 80–350 km, unrepeatered. Backhaul of 10–150 km. |
| Geographic scope | Trans-oceanic, regional sea or coastal |
| Inclusion | ≥ 2 CLS **and** ≥ 1 undersea segment |
| Exclusion | None. Undersea segments are decisive. |
| Ambiguity | None expected in the pilot. Real systems with long terrestrial backhaul would need review. |

**Provenance:** synthetic architectural template with **fully synthetic coordinates** (not checked
against coastlines; no real cable represented).

---

## Classification rules used by the validator (`src/validation/label_rules.py`)

These rules are implemented separately from the generator. They read only the graph and
equipment files, i.e. evidence that is drawn in the diagram:

| Class | Rule satisfied when |
|---|---|
| submarine | ≥ 2 CLS and ≥ 1 undersea edge |
| dci | ≥ 2 DC and DC ≥ 50% of terminal-bearing sites, no undersea edge |
| metro_ring | no DC/CLS/CO, every node on a cycle, ≥ 60% degree-2, max link ≤ 100 km |
| metro_aggregation | no DC/CLS, HUB + ROADM + ≥ 4 CO present, max link ≤ 100 km |
| long_haul_core | only ROADM sites, (mean link ≥ 150 km or extent ≥ 800 km), ILAs present |

- If the assigned class does not satisfy its own rule, the scenario **fails**.
- If more than one rule is satisfied, the scenario gets an **ambiguity warning**.
- **Structural-similarity warnings** record when graph shape alone points to a different class (for example a ring-like long-haul source).

Labels are never reassigned automatically.

**Caveat:** the generator assigns roles by construction, so these checks show internal consistency.
They do not independently prove that the networks are realistic. Human expert review of the contact sheets is required.
