"""Tests Phase 3 - baselines naives et harnais de falsification (§ 9.7)."""

import math

from mcs import SimConfig
from mcs.baselines import (
    baseline_moving_average,
    baseline_threshold,
    compare_detectors,
    falsification_report,
    falsification_run,
    moving_average,
)


def test_moving_average_no_lookahead():
    L = [0.0, 0.0, 3.0, 3.0]
    ma = moving_average(L, window=2)
    assert ma[1] == 0.0            # avant le saut, aucune fuite du futur
    assert ma[2] == 1.5


def test_baselines_fire_only_on_load():
    L = [0.4] * 30
    assert baseline_threshold(L, 1.0) is None
    assert baseline_moving_average(L, 4, 1.0) is None
    L2 = [0.4] * 10 + [1.2] * 5 + [0.4] * 10
    assert baseline_threshold(L2, 1.0) == 10


def test_silent_degradation_gives_infinite_lead():
    """Charge constante sous-critique : la baseline ne peut pas alerter,
    le MCS le doit - c'est l'apport specifique de la dette invisible."""
    cfg = SimConfig(L=0.4, R=0.7, B=0.6, rho=0.9, D_crit=0.6)
    rec = compare_detectors(cfg, 80, "silencieux", L_threshold=1.0)
    assert rec.mcs is not None
    assert rec.naive_threshold is None
    assert rec.lead_vs_threshold == math.inf


def test_falsification_harness_passes_canonical_scenarios():
    recs = falsification_run()
    by_name = {r.name: r for r in recs}
    assert by_name["F1_degradation_silencieuse"].passed
    assert by_name["F2_choc_absorbe"].passed
    assert by_name["F3_avance_de_signal"].passed
    report = falsification_report(recs)
    assert "PASS" in report and "falsification" in report.lower()


def test_falsification_report_documents_failures():
    """Un echec doit apparaitre en clair, pas etre masque."""
    from mcs.baselines import FalsificationRecord
    fake = [FalsificationRecord("cas_ad_hoc", "prediction X", False,
                                {"raison": "contre-exemple"})]
    report = falsification_report(fake)
    assert "FAIL" in report and "contre-exemple" in report
    assert "0/1 PASS" in report
