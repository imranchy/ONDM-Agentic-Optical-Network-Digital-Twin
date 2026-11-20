# GNPy Integration — Scope and Limitations

The source research archives contain topology-to-GNPy converter scripts, generated network examples, equipment assumptions and simulation logs. They are a foundation for a simulation-backed optical digital twin.

## Existing vs planned

**Existing in supplied archive:** proof-of-concept topology converter; corrected equipment-semantic converter; sample generated GNPy files and simulation outputs. Some spans are modeled with inline optical amplification and ROADMs are switching nodes.

**Not independently established here:** a reproducible GNPy setup running on every user machine; calibration to deployed equipment; generic pass/fail GSNR/OSNR thresholds; a dynamic agent-to-GNPy execution pipeline.

## Recommended integration path

1. Standardize graph-to-GNPy transformation and document equipment assumptions.
2. Reproduce GNPy runs and record software versions, service modes and thresholds.
3. Add a deterministic `assess_optical_path` tool with validated topology and service arguments.
4. Present OSNR/GSNR, feasibility conditions and assumptions alongside a candidate NetworkX route.
5. Introduce NetBox equipment mapping when reliable inventory objects and identifiers exist.

**Important:** a shortest graph path is not evidence of transmission feasibility; a GNPy result is only meaningful under the specified channel/equipment model and acceptance thresholds.
