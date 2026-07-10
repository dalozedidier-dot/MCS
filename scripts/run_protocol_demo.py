"""Demonstration Phase 2 : protocole gele -> donnees CSV -> rapport.

Le protocole examples/protocols/equipe_projet.yaml a ete gele AVANT
toute lecture des donnees (empreinte SHA-256 + horodatage). Ce script
verifie l'empreinte, applique les normalisations § 9.3 et produit
reports/rapport_equipe_projet.md avec M(t) +- IC, D(t) en indicateur
avance et zones ordinales confirmees.

Usage : python scripts/run_protocol_demo.py
"""

from pathlib import Path

from mcs.protocol import Protocol, compute_series, load_csv

ROOT = Path(__file__).resolve().parent.parent
proto = Protocol.load(ROOT / "examples/protocols/equipe_projet.yaml")
proto.verify()  # leve si non gele ou altere
rows = load_csv(ROOT / "examples/data/equipe_projet.csv")
rep = compute_series(proto, rows)

out = ROOT / "reports" / "rapport_equipe_projet.md"
out.parent.mkdir(exist_ok=True)
out.write_text(rep.to_markdown(), encoding="utf-8")

lic = rep.leading_indicator_check()
print(f"Rapport ecrit : {out}")
print(
    f"D(0) = {rep.D0:.3f}, M final = {rep.M[-1]:+.3f} "
    f"+- {rep.M_err[-1]:.3f}, zone finale = {rep.zone[-1]}"
)
print(
    f"Dette croissante des t = {lic['debt_rising_at']}, premiere "
    f"alerte a t = {lic['first_alert']} (avance {lic['lead']} pas)"
)
