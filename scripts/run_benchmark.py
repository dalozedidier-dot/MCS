"""Execute le benchmark aveugle et publie JSON + Markdown + figure.

Usage : python scripts/run_benchmark.py
Sorties : reports/benchmark.json, reports/benchmark.md,
          reports/benchmark.png (+ copie docs/assets/)
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from mcs.benchmark import benchmark_markdown, run_benchmark  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "reports"
OUT.mkdir(exist_ok=True)

res = run_benchmark()
(OUT / "benchmark.json").write_text(
    json.dumps(res.as_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
)
(OUT / "benchmark.md").write_text(benchmark_markdown(res), encoding="utf-8")

order = sorted(res.detectors, key=lambda d: d.median_lead or 0)
names = [d.name for d in order]
leads = [d.median_lead or 0 for d in order]
sens = [d.sensitivity for d in order]
colors = [
    "#2f6b4f" if n == "mcs_complet" else ("#b8892b" if n.startswith("mcs_") else "#9aa5a0")
    for n in names
]
fig, ax = plt.subplots(figsize=(9.2, 4.8))
bars = ax.barh(names, leads, color=colors)
max_lead = max(leads, default=1.0)
# Reserve a dedicated right-hand annotation zone so sensitivity labels
# never leave the plotting area, even for the longest bar.
ax.set_xlim(0, max_lead + 4.2)
for b, s in zip(bars, sens, strict=True):
    ax.text(
        min(b.get_width() + 0.25, max_lead + 3.15),
        b.get_y() + b.get_height() / 2,
        f"sens. {s:.2f}",
        va="center",
        fontsize=8,
        color="#65726d",
    )
ax.set_xlabel(
    "avance mediane avant evenement (pas, parmi les evenements detectes)\n"
    "seuils calibres vers un FPR cible commun de 10 %"
)
ax.set_title(
    f"Benchmark aveugle — {res.n_validation} trajectoires de validation\n"
    "parametres fixes avant evaluation"
)
fig.tight_layout()
fig.savefig(OUT / "benchmark.png", dpi=150)
plt.close(fig)
shutil.copy(OUT / "benchmark.png", ROOT / "docs" / "assets" / "benchmark.png")
h = res.headline
print(
    f"gain median apparie (vs {h['baseline_la_plus_defavorable']}) : "
    f"{h['gain_median']:+.1f} pas ; JSON/MD/PNG ecrits dans reports/"
)
