"""Exemple minimal : reproduit la micro-simulation equipe projet (§ 9.4)
et affiche la lecon de la semaine 8."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mcs.core import classify
from mcs.scenarios import project_team

res = project_team()
print(f"{'sem':>4} {'L':>6} {'D':>7} {'C':>7} {'M':>8}  zone")
for t in range(8):
    print(f"{t + 1:>4} {res.L[t]:>6.2f} {res.D[t]:>7.3f} "
          f"{res.C[t]:>7.3f} {res.M[t]:>8.3f}  {classify(res.M[t]).value}")

print("\nLecon : en semaine 8 la charge redescend (0.32) mais la dette "
      f"accumulee ({res.D[7]:.3f}) maintient l'equipe hors zone viable "
      f"(M = {res.M[7]:.3f}). Baisse de pression != recuperation reelle.")
