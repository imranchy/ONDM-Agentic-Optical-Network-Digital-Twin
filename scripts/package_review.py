"""Package all pilot artefacts into ONDM_Optical_Topology_Pilot_125_Review.zip (project root).

Usage:  .venv\\Scripts\\python scripts\\package_review.py
"""
from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "ONDM_Optical_Topology_Pilot_125_Review"
INCLUDE = [
    "data/pilot/ONDM_pilot_125",
    "configs", "src/generation", "src/validation", "src/reporting", "scripts", "tests",
    "reports/pilot_125", "figures/pilot_125",
    "docs/TAXONOMY.md", "docs/PILOT_REVIEW_GUIDE.md",
    "references/topology_bench/README.md", "references/topology_bench/real_catalog.json",
    "README.md", "RESEARCH_HANDOFF.md", "requirements.txt",
]
SKIP_PARTS = {"__pycache__", ".pytest_cache"}


def main() -> None:
    files = []
    for inc in INCLUDE:
        p = ROOT / inc
        if not p.exists():
            raise SystemExit(f"missing {inc}")
        files += [p] if p.is_file() else sorted(f for f in p.rglob("*") if f.is_file() and not (SKIP_PARTS & set(f.parts)))
    out = ROOT / f"{NAME}.zip"
    manifest = []
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for f in files:
            rel = f.relative_to(ROOT).as_posix()
            data = f.read_bytes()
            z.writestr(f"{NAME}/{rel}", data)
            manifest.append({"path": rel, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        z.writestr(f"{NAME}/PACKAGE_MANIFEST.json", json.dumps(
            {"created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "n_files": len(manifest),
             "files": manifest}, indent=1))
    n_png = sum(1 for m in manifest if m["path"].startswith("data/pilot") and m["path"].endswith(".png"))
    print(f"{out}  files={len(manifest)}  pilot_png={n_png}  size={out.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
