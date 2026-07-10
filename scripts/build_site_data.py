"""Compile docs/data/results.json depuis les artefacts du depot.

Principe (audit, niveau H) : la page GitHub Pages ne doit contenir
aucun nombre saisi a la main. Ce script collecte les valeurs a la
source et le site les injecte au chargement :

- nombre de tests : collecte pytest reelle (pas un chiffre recopie)
- version : mcs.__version__
- falsification : execution reelle du harnais (PASS/FAIL detailles)
- benchmark : reports/benchmark.json s'il existe (sinon regenere)
- provenance : date UTC de generation + commit (env GITHUB_SHA en CI)

Usage : python scripts/build_site_data.py
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs" / "data"
DATA.mkdir(parents=True, exist_ok=True)


def count_tests() -> int:
    out = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    last = [ln for ln in out.stdout.splitlines() if "test" in ln][-1]
    # format : "N tests collected in ..." ou "N/M tests collected"
    for tok in last.split():
        if tok.isdigit():
            return int(tok)
    raise RuntimeError(f"comptage de tests illisible : {last!r}")


def falsification() -> list[dict]:
    from mcs.baselines import falsification_run

    return [
        {"name": r.name, "passed": r.passed, "prediction": r.prediction}
        for r in falsification_run()
    ]


def coverage_summary() -> dict:
    """Lit le rapport coverage.py JSON s'il a ete produit par la CI."""
    path = ROOT / "reports" / "coverage.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    totals = data.get("totals", {})
    return {
        "percent_covered": totals.get("percent_covered"),
        "num_statements": totals.get("num_statements"),
        "missing_lines": totals.get("missing_lines"),
        "num_branches": totals.get("num_branches"),
    }


def benchmark_summary() -> dict:
    path = ROOT / "reports" / "benchmark.json"
    if not path.exists():
        from mcs.benchmark import run_benchmark

        res = run_benchmark().as_dict()
    else:
        res = json.loads(path.read_text(encoding="utf-8"))
    return {
        "headline": res["headline"],
        "n_validation": res["n_validation"],
        "target_fpr": res["target_fpr"],
        "detectors": [
            {
                "name": d["name"],
                "sensitivity": d["sensitivity"],
                "false_alarm_rate": d["false_alarm_rate"],
                "median_lead": d["median_lead"],
            }
            for d in res["detectors"]
        ],
    }


def main() -> None:
    sys.path.insert(0, str(ROOT / "src"))
    import mcs

    fal = falsification()
    payload = {
        "version": mcs.__version__,
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "commit": os.environ.get("GITHUB_SHA", "local"),
        "n_tests": count_tests(),
        "falsification": fal,
        "falsification_pass": sum(r["passed"] for r in fal),
        "falsification_total": len(fal),
        "benchmark": benchmark_summary(),
        "python_ci": "3.10–3.12",
        "coverage": coverage_summary(),
    }
    out = DATA / "results.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        f"{out} : v{payload['version']}, {payload['n_tests']} tests, "
        f"falsification {payload['falsification_pass']}/"
        f"{payload['falsification_total']}, commit {payload['commit'][:8]}"
    )


if __name__ == "__main__":
    main()
