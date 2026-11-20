# Topology Bench — source inspection notes

**Citation:** R. Matzner, A. Ahuja, R. Sadeghi, M. Doherty, A. Beghelli, S. J. Savory, P. Bayvel,
"Topology Bench: systematic graph-based benchmarking for core optical networks", *J. Opt. Commun.
Netw.* 17(1):7–27 (Zenodo record citation; the user brief refers to it as JOCN 2025).
**Dataset:** Zenodo record 13921775, v4, doi:10.5281/zenodo.13921775 (concept doi 10.5281/zenodo.12593794).
**Licence:** CC-BY-4.0. Reuse with attribution is permitted. `real_catalog.json` is a derived format
conversion and keeps this attribution.

## Files on the record (inspected 2026-11-20)

| File | Bytes | MD5 | Downloaded? |
|---|---:|---|---|
| `real_topologies.zip` | 896,114 | bcb92010a9116f575851781436528eb0 | yes (MD5 verified) |
| `small_snythetic.zip` (sic) | 1,673,379 | 91bc2cb0bf99dc5569eb7823803dfcf2 | yes (MD5 verified); **not opened** (see below) |
| `large_synthetic.zip` | 577,427,125 | 827c31832c407ee52295c7261bb35b56 | no |
| `synthetic_csv_data.zip` | 2,714,298,961 | 5c5b082d235ec326e0d7e988ab19705a | no |

Raw files are stored in `raw/` (gitignored).

## What the real topologies contain

- 105 Excel workbooks (`TOP_<n>_<NAME>.xlsx`), each with two sheets:
  - **Nodes:** `Node_ID, Latitude, Longitude, Location Name, Country`.
  - **Edges:** `Edge_ID, Source, Destination, Computed Length (km)`.
- `info.md` says only: "Final formatted topologies and verified for paper".
- For 104/105 topologies, `Computed Length` ≈ **1.5 × great-circle distance** (median ratio 1.50). This means
  Topology Bench applies a route factor. The lengths are not surveyed fibre routes. We use them unchanged
  and apply no second factor (assumption A1).
- **11 topologies have lengths inconsistent with their coordinates.** Some ratios are below 1.0, which is
  physically impossible (CANARIE TB_012, CERNET, CESNET, DT17, SANET). One ratio is 229 (METRONA).
  We report these and exclude them from long-haul use rather than correcting them.
- Scope: Topology Bench targets **core** optical networks. It contains no labelled metro-ring,
  metro-aggregation, DCI or submarine examples. Some networks are PoP/IP-level maps. We use it **only** for the
  long-haul / core class, and as a pool of real anchor-city coordinates for the metro and DCI templates.

## Synthetic sets

- `small_snythetic.zip` holds only a Python **pickle** (`small_synthetic_graphs.pickle`). Unpickling untrusted data can run
  arbitrary code, so it was **not loaded**. Its methodology (the SNR-BA generator in the paper) could be
  re-implemented from the paper if needed.
- The large synthetic sets (≈3.3 GB) were not downloaded. They are core-network graphs and are not needed for the pilot.

## Long-haul eligibility (configs/pilot_125.json → long_haul_core)

A source is eligible only if all of these hold:
- 8–30 nodes (legibility)
- connected
- geographic extent 1,500–6,000 km
- mean link ≥ 250 km
- longest link ≤ 3,000 km
- every link's length / great-circle ratio is in [0.999, 3.0]

28/105 are eligible. Every excluded source and its reason is listed in
`data/pilot/ONDM_pilot_125/generation_log.json`.
