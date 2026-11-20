# Reproduce the 125-network ONDM pilot end-to-end (deterministic for a given config + seed).
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$py = ".venv\Scripts\python.exe"
& $py -m src.generation.topology_bench --raw references/topology_bench/raw/real --out references/topology_bench/real_catalog.json
& $py -m src.generation.generate_dataset --config configs/pilot_125.json --clean
& $py -m src.validation.validate_dataset --data data/pilot/ONDM_pilot_125 --out reports/pilot_125
& $py -m src.reporting.figures --data data/pilot/ONDM_pilot_125 --reports reports/pilot_125 --out figures/pilot_125
& $py -m src.reporting.build_report --data data/pilot/ONDM_pilot_125 --reports reports/pilot_125
& $py -m pytest -q tests
