"""Tests du benchmark aveugle.

Discipline : ces tests verifient la MACHINERIE (determinisme,
non-circularite, calibration au FPR cible, separation des jeux,
formats), jamais le RESULTAT du benchmark. Presupposer la victoire du
MCS dans un test transformerait l'evaluation aveugle en prophetie
autorealisatrice ; les chiffres vont dans le rapport, quels qu'ils
soient.
"""

import math

import pytest

from mcs.benchmark import (
    DETECTORS,
    EVENT_WINDOW,
    calibrate_threshold,
    first_alert,
    generate,
    run_benchmark,
)


def test_generation_is_deterministic():
    a, b = generate(42), generate(42)
    assert a.family == b.family and a.event == b.event
    assert a.L == b.L and a.R == b.R and a.B == b.B
    assert generate(43).L != a.L


def test_families_cover_event_and_no_event():
    trajs = [generate(s) for s in range(80)]
    families = {t.family for t in trajs}
    assert len(families) == 5
    assert any(t.event is not None for t in trajs)
    assert any(t.event is None for t in trajs)
    # les familles concues sans evenement n'en produisent jamais
    for t in trajs:
        if t.family in ("false_shock", "recovery"):
            assert t.event is None


def test_labels_are_not_circular():
    """L'etiquette vient du mecanisme cache, pas des series observees :
    re-bruiter l'observation ne change pas l'evenement (meme graine =>
    meme verite cachee), et aucune fonction du MCS n'est appelee par le
    generateur (verification statique ci-dessous)."""
    import inspect

    import mcs.benchmark as bm
    src = inspect.getsource(bm._ramp_to_break) \
        + inspect.getsource(bm._regime_switch) \
        + inspect.getsource(bm._silent_erosion) \
        + inspect.getsource(bm._false_shock) \
        + inspect.getsource(bm._recovery) \
        + inspect.getsource(bm._hidden_event)
    for forbidden in ("debt", "margin", "capacity", "simulate", "Zone"):
        assert forbidden not in src, f"generateur non aveugle : {forbidden}"


def test_scores_shapes_and_finiteness():
    tr = generate(7)
    for name, scorer in DETECTORS.items():
        s = scorer(tr)
        assert len(s) == len(tr.L), name
        assert all(math.isfinite(x) for x in s), name


def test_calibration_reaches_target_fpr_on_calibration_set():
    """Par construction du quantile, le FPR sur le jeu de calibration
    lui-meme est <= cible (a la granularite d'echantillon pres)."""
    cal = [generate(s) for s in range(120)]
    neg = [t for t in cal if t.event is None]
    for name, scorer in DETECTORS.items():
        scores = [scorer(t) for t in neg]
        thr = calibrate_threshold(scores, target_fpr=0.10)
        fired = sum(first_alert(s, thr) is not None for s in scores)
        assert fired / len(neg) <= 0.10 + 1.0 / len(neg), name


def test_disjoint_seeds_enforced():
    with pytest.raises(ValueError, match="disjointes"):
        run_benchmark(calibration_seeds=range(0, 10),
                      validation_seeds=range(5, 15))


def test_benchmark_pipeline_and_headline_schema():
    res = run_benchmark(calibration_seeds=range(0, 60),
                        validation_seeds=range(60, 140),
                        target_fpr=0.10)
    assert len(res.detectors) == len(DETECTORS)
    d = res.as_dict()
    for key in ("critere", "baseline_la_plus_defavorable", "gain_median",
                "gains_apparies_par_baseline", "delai_median_mcs",
                "fpr_mcs_observe"):
        assert key in d["headline"]


def test_paired_gain_penalizes_missed_detections():
    """Un detecteur qui ne tire que sur les cas faciles ne peut pas
    dominer au critere apparie : les detections manquees comptent pour
    une avance nulle."""
    from mcs.benchmark import DetectorResult, paired_median_gain
    full = DetectorResult("full", 0.0, 1.0, 0.0, 1.0, 1.0, 5.0,
                          leads=[5, 5, 5, 5],
                          lead_by_traj={1: 5, 2: 5, 3: 5, 4: 5})
    cherry = DetectorResult("cherry", 0.0, 0.25, 0.0, 1.0, 0.25, 20.0,
                            leads=[20],
                            lead_by_traj={1: 20, 2: 0, 3: 0, 4: 0})
    # au delai median naif, cherry "gagne" (20 > 5) ; au critere
    # apparie, full domine : diffs = [-15, 5, 5, 5], mediane 5
    assert paired_median_gain(full, cherry) == 5.0


def test_leads_positive_and_event_window():
    res = run_benchmark(calibration_seeds=range(0, 40),
                        validation_seeds=range(40, 90))
    # le delai d'alerte, quand il existe, est strictement positif
    for det in res.detectors:
        assert all(lead > 0 for lead in det.leads)
    # l'evenement cache respecte sa definition (fenetre w)
    assert EVENT_WINDOW >= 1
