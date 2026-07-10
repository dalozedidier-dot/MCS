"""Build a provenance manifest for every public result figure.

The manifest records the generator, SHA-256 digest, and verifies that the
public GitHub Pages asset is byte-for-byte identical to the report output.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"
ASSETS = ROOT / "docs" / "assets"

FIGURES = {
    "benchmark.png": "scripts/run_benchmark.py",
    "monte_carlo.png": "scripts/run_robustness.py",
    "hysteresis_k.png": "scripts/run_robustness.py",
    "cascade.png": "scripts/run_robustness.py",
    "tornado.png": "scripts/run_robustness.py",
    "oscillations.png": "scripts/run_robustness.py",
    "irreversibilite.png": "scripts/run_demo_dossier.py",
    "carte_regime.png": "scripts/run_demo_dossier.py",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    records = []
    for name, generator in FIGURES.items():
        report = REPORTS / name
        public = ASSETS / name
        if not report.exists() or not public.exists():
            raise FileNotFoundError(f"figure manquante: {name}")
        report_hash = sha256(report)
        public_hash = sha256(public)
        if report_hash != public_hash:
            raise RuntimeError(f"figure publique désynchronisée: {name}")
        records.append(
            {
                "figure": name,
                "generator": generator,
                "report_sha256": report_hash,
                "public_sha256": public_hash,
                "byte_identical": True,
            }
        )
    out = REPORTS / "figures_manifest.json"
    out.write_text(json.dumps({"figures": records}, indent=2), encoding="utf-8")
    print(f"{out}: {len(records)} figures vérifiées")


if __name__ == "__main__":
    main()
