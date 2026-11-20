# Reproduce the 125-network ONDM pilot end-to-end (deterministic for a given config + seed).
Set-Location (Split-Path $PSScriptRoot -Parent)
$py = ".venv\Scripts\python.exe"
$steps = @(
  @("-m", "src.generation.topology_bench", "--raw", "references/topology_bench/raw/real", "--out", "references/topology_bench/real_catalog.json"),
  @("-m", "src.generation.generate_dataset", "--config", "configs/pilot_125.json", "--clean"),
  @("-m", "src.validation.validate_dataset", "--data", "data/pilot/ONDM_pilot_125", "--out", "reports/pilot_125"),
  @("-m", "src.reporting.figures", "--data", "data/pilot/ONDM_pilot_125", "--reports", "reports/pilot_125", "--out", "figures/pilot_125"),
  @("-m", "src.reporting.build_report", "--data", "data/pilot/ONDM_pilot_125", "--reports", "reports/pilot_125"),
  @("-m", "pytest", "-q", "tests")
)
foreach ($s in $steps) {
  Write-Host ">> python $($s -join ' ')"
  & $py @s
  if ($LASTEXITCODE -ne 0) { Write-Error "step failed: $($s -join ' ')"; exit $LASTEXITCODE }
}
Write-Host "pilot pipeline complete"
