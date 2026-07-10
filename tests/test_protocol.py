"""Tests Phase 2 - protocole empirique pre-enregistre (§ 9.2-9.3)."""

import pytest

from mcs.protocol import (
    Protocol,
    ProtocolError,
    ProxySpec,
    aggregate,
    compute_series,
    initial_debt,
    load_csv,
    normalize_feedback,
    normalize_load,
    normalize_recovery,
)


def make_protocol() -> Protocol:
    return Protocol(
        name="equipe_projet_test",
        author="test",
        time_step="semaine",
        L_crit=40.0,
        t_regulation_cible=2.0,
        delai_critique=3.0,
        proxies=[
            ProxySpec("L", "aucune tache", "charge critique", 0.1),
            ProxySpec("R", "jamais regule", "regulation a la cible", 0.1),
            ProxySpec("B", "signal ignore", "decision immediate", 0.1),
        ],
        rho=0.85,
    )


ROWS = [
    {
        "t": -1,
        "load": 0,
        "t_regulation": 0,
        "delai_signal_decision": 0,
        "irritant_severite": 0.1,
        "irritant_age": 4,
    },
    {"t": 0, "load": 20, "t_regulation": 3.0, "delai_signal_decision": 4.0},
    {"t": 1, "load": 24, "t_regulation": 3.5, "delai_signal_decision": 5.0},
    {"t": 2, "load": 24, "t_regulation": 4.0, "delai_signal_decision": 6.0},
]


# -- anti-circularite appliquee par le code ----------------------------------


def test_compute_refuses_unfrozen_protocol():
    with pytest.raises(ProtocolError, match="non gele"):
        compute_series(make_protocol(), ROWS)


def test_tampering_after_freeze_is_detected():
    p = make_protocol().freeze()
    p.thresholds["viable"] = 0.9  # retouche apres coup
    with pytest.raises(ProtocolError, match="modifie apres gel"):
        compute_series(p, ROWS)


def test_freeze_sets_fingerprint_and_roundtrip(tmp_path):
    p = make_protocol().freeze()
    p.verify()
    for ext in (".json", ".yaml"):
        path = p.save(tmp_path / f"proto{ext}")
        q = Protocol.load(path)
        q.verify()
        assert q.fingerprint == p.fingerprint


def test_weighted_aggregation_requires_weights():
    p = make_protocol()
    p.aggregation = "weighted"
    with pytest.raises(ProtocolError, match="poids"):
        p.freeze()


# -- normalisations § 9.3 -----------------------------------------------------


def test_normalizations_anchors():
    assert normalize_load(20, 40) == 0.5
    assert normalize_load(60, 40) == 1.5  # peut depasser 1
    assert normalize_recovery(2.0, 2.0) == 1.0  # a la cible
    assert normalize_recovery(4.0, 2.0) == 0.5  # deux fois trop lent
    assert normalize_recovery(0.0, 2.0) == 0.0  # jamais regule
    assert normalize_feedback(6.0, 3.0) == 0.5
    assert normalize_feedback(1.0, 3.0) == 1.0  # borne a 1


def test_initial_debt_weights_by_age():
    d = initial_debt([(0.1, 0), (0.1, 10)], age_weight=0.1)
    assert d == pytest.approx(0.1 + 0.1 * 2.0)


def test_aggregate_worst_and_weighted():
    p = make_protocol()
    vals = {"a": 0.9, "b": 0.4}
    assert aggregate(vals, p) == 0.4  # lecture du pire
    p.aggregation = "weighted"
    p.weights = {"a": 3.0, "b": 1.0}
    assert aggregate(vals, p) == pytest.approx((0.9 * 3 + 0.4) / 4)


# -- pipeline complet ---------------------------------------------------------


def test_compute_series_full_pipeline(tmp_path):
    p = make_protocol().freeze()
    rep = compute_series(p, ROWS)
    assert rep.D0 == pytest.approx(0.1 * 1.4)
    assert len(rep.t) == 3
    # B se degrade (delai qui s'allonge) => la dette monte
    assert rep.D[-1] > rep.D[0]
    # incertitude strictement positive et rapportee partout
    assert all(e > 0 for e in rep.M_err)
    md = rep.to_markdown()
    assert "ORDINAL" in md and p.fingerprint[:16] in md
    lic = rep.leading_indicator_check()
    assert lic["debt_rising_at"] is not None


def test_load_csv_checks_columns(tmp_path):
    f = tmp_path / "bad.csv"
    f.write_text("t,load\n0,1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="colonnes manquantes"):
        load_csv(f)
    g = tmp_path / "ok.csv"
    g.write_text("t,load,t_regulation,delai_signal_decision\n0,20,3.0,4.0\n", encoding="utf-8")
    rows = load_csv(g)
    assert rows[0]["load"] == 20.0
