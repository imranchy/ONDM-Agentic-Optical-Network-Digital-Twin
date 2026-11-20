# ONDM 2027: equipment-semantic correction (pilot)

## Purpose

The previous generator assigned ILA and TRANSCEIVER to arbitrary graph vertices. The previous GNPy converter turned these vertices into ROADM proxies. These replacement scripts eliminate that behavior: graph vertices are switching ROADM sites; in-line amplification belongs to physical fiber spans; test transceivers attach to ROADMs. This is a **physically structured synthetic reference design**, not a validated operator digital twin.

## Replace these exact filenames

- `scripts/data-generator.py`
- `integrations/gnpy/full_topology_to_gnpy.py`

Back up the existing scripts first. Keep the original 500-sample dataset and all old pilot outputs unchanged until the new pilot is validated.

## Windows Command Prompt

```bat
cd /d "C:\Users\dipto\Downloads\Projects\Imran ONDM 27"
.venv\Scripts\activate
copy scripts\data-generator.py scripts\data-generator.pre_semantics.py
copy integrations\gnpy\full_topology_to_gnpy.py integrations\gnpy\full_topology_to_gnpy.pre_semantics.py
```

Copy the new scripts into the above paths, retaining their filenames.

```bat
python scripts\data-generator.py --output-dir optical_topology_semantics_pilot --num-samples 30 --min-nodes 6 --max-nodes 12 --topologies ring star mesh tree hybrid random --difficulty mixed --seed 2027
python integrations\gnpy\full_topology_to_gnpy.py --graph optical_topology_semantics_pilot\graphs\topo_0003.json --reference .venv\Lib\site-packages\gnpy\example-data\edfa_example_network.json --source A --target C --output simulations\generated\semantic_topo_0003.json

gnpy-transmission-example simulations\generated\semantic_topo_0003.json Trx_A Trx_C --save-network simulations\generated\semantic_topo_0003_designed.json > simulations\generated\semantic_topo_0003.log 2>&1
type simulations\generated\semantic_topo_0003.log
```

If the example model fails, send the full log; do not interpret an unsuccessful design as a model-performance result.

## Important limitations before generating 2,000+ samples

1. The revised generator still draws ROADM switching sites as the main vertices. Terminal transceiver attachments and in-line amplifier locations are currently represented as *simulation metadata and converter elements*, not individually rendered and annotated equipment icons. Add explicit physical-layer diagram rendering before using the dataset to benchmark detection of ILA or transceiver symbols.
2. The GNPy converter attaches test transceivers at every ROADM site to enable arbitrary endpoint testing; these are simulation assumptions, not discovered equipment.
3. It uses the installed example fiber/EDFA/ROADM equipment parameters, not measured or vendor-specific profiles.
4. The current dataset uses random train/validation/test splits. For research, implement topology/source-group holdouts and deduplicate before model training.
5. Verify YOLO overlays and image legibility; generator execution alone is not annotation QA.
6. Do not treat `GSNR` as a feasibility decision until a transceiver mode and required threshold are defined.

## Dataset retention

Archive the original 500 dataset and old pilots as immutable snapshots, with checksums and generation scripts. Keep old results out of training and current evaluation. Do not delete any files until archives have been verified and at least one other copy exists. Small dataset archives are unlikely to be the principal storage problem relative to OTSE checkpoints.
