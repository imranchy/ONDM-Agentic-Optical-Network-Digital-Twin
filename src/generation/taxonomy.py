"""Five-class optical transport architecture taxonomy and declared modelling assumptions.

The human-readable definitions live in docs/TAXONOMY.md; this module holds the machine-readable
constants shared by the generator, the renderer and the validator.

IMPORTANT: every numeric range below is a *declared generation assumption* chosen to be
consistent with commonly reported engineering practice. None of them is a standardised limit.
"""
from __future__ import annotations

CLASSES = [
    "long_haul_core",
    "metro_ring",
    "metro_aggregation",
    "dci",
    "submarine",
]

CLASS_DISPLAY = {
    "long_haul_core": "Long-haul / Core",
    "metro_ring": "Metro Optical Ring",
    "metro_aggregation": "Metro Aggregation",
    "dci": "Data Center Interconnect",
    "submarine": "Submarine",
}

# Node roles (graph vertices are *sites*; inline amplifiers/repeaters are span equipment on edges)
ROLE_ROADM = "ROADM"            # reconfigurable switching site (degree >= 2)
ROLE_HUB_ROADM = "HUB_ROADM"    # ROADM acting as hub / gateway towards the wider network
ROLE_OADM = "OADM"              # fixed/two-degree add-drop site on a ring or chain
ROLE_CO = "CO"                  # access-side central-office site with terminal equipment
ROLE_DC = "DC"                  # data-centre site terminating coherent DCI optics
ROLE_CLS = "CLS"                # cable landing station (hosts SLTE and power feed equipment)
ROLE_BU = "BU"                  # undersea branching unit (passive/ROADM-BU, no terminal equipment)
ROLE_POP = "POP_ROADM"          # terrestrial point of presence reached by CLS backhaul

ALL_ROLES = [ROLE_ROADM, ROLE_HUB_ROADM, ROLE_OADM, ROLE_CO, ROLE_DC, ROLE_CLS, ROLE_BU, ROLE_POP]
SWITCHING_ROLES = {ROLE_ROADM, ROLE_HUB_ROADM, ROLE_POP}
TERMINAL_BEARING_ROLES = {ROLE_ROADM, ROLE_HUB_ROADM, ROLE_OADM, ROLE_CO, ROLE_DC, ROLE_CLS, ROLE_POP}

MEDIUM_TERRESTRIAL = "terrestrial"
MEDIUM_SUBMARINE = "submarine"

# Words that must never appear in diagram text (category names / direct hints).
LEAKAGE_TOKENS = [
    "long-haul", "long haul", "longhaul", "core", "backbone", "metro", "ring", "aggregation",
    "agg", "dci", "interconnect", "submarine", "subsea", "class", "category", "label",
]

# ---------------------------------------------------------------------------------------------
# Declared assumptions (referenced by id from equipment / metadata files)
# ---------------------------------------------------------------------------------------------
ASSUMPTIONS = {
    "A1_tb_lengths": (
        "Long-haul link lengths are Topology Bench 'Computed Length (km)' values, copied unchanged. "
        "For 104/105 real topologies these equal 1.5 x great-circle distance (verified in "
        "references/topology_bench/real_catalog.json), i.e. Topology Bench already applies a "
        "route factor; no further factor is applied. They are not surveyed fibre routes."
    ),
    "A2_synthetic_route_factor": (
        "Synthetic terrestrial fibre length = great-circle distance x route factor drawn "
        "uniformly from [1.2, 1.6]. Synthetic undersea length = great-circle x [1.05, 1.25]. "
        "These are modelling assumptions, not measured rights-of-way or real cable routes."
    ),
    "A3_terrestrial_span": (
        "Terrestrial inline amplifier (ILA/EDFA) count per link = ceil(L / S) - 1 with a "
        "per-scenario maximum span length S drawn from [70, 100] km; spans are equal length. "
        "~80 km spans are a common planning assumption (e.g. GNPy example networks); not a standard."
    ),
    "A4_submarine_repeater": (
        "Repeatered undersea segments: repeater count = ceil(L / S) - 1 with S drawn from "
        "[50, 90] km. Segments <= 350 km may be unrepeatered (festoon). Assumption, not a design."
    ),
    "A5_dci_reach": (
        "Metro DCI links up to 120 km are terminated by coherent pluggables (400ZR-class, "
        "OIF 400ZR targets amplified point-to-point links of roughly 80-120 km); longer DCI links "
        "use ZR+/transponder-class terminals and inline amplifiers per A3."
    ),
    "A6_terminals": (
        "Transponder / pluggable counts per site are synthetic and indicative only; they encode "
        "where traffic is terminated, not dimensioned capacity."
    ),
    "A7_coordinates_metro": (
        "Metro ring, metro aggregation and DCI site coordinates are synthetic offsets around a "
        "real anchor city taken from the Topology Bench node lists; the anchor is real, the sites "
        "are not."
    ),
    "A8_coordinates_submarine": (
        "Submarine landing-station and branching-unit coordinates are fully synthetic, were not "
        "checked against coastlines, and do not represent any existing cable system."
    ),
    "A9_roadm_degree": "ROADM degree equals the number of fibre links at the site.",
}
