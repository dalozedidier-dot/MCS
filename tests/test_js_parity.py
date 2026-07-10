"""Parite entre le moteur Python et le portage JS du simulateur web.

Le simulateur de docs/ n'est pas une approximation pedagogique : c'est
le MEME modele. Ce test execute docs/mcs-engine.js sous Node sur des
configurations couvrant toutes les extensions et compare les
trajectoires (M, D, theta, C, zones) au moteur Python a 1e-9 pres.
Skip si Node est absent de l'environnement.
"""

import json
import math
import shutil
import subprocess
from pathlib import Path

import pytest

from mcs import SimConfig, simulate
from mcs.extensions import ControlParams, RecoveryParams, ThetaParams

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "docs" / "mcs-engine.js"

node = shutil.which("node")
pytestmark = pytest.mark.skipif(node is None,
                                reason="Node absent : parite JS non testable")

RUNNER = ROOT / "tests" / "parity_runner.js"


def run_js(cfg_json: dict, n: int) -> dict:
    cfg_json = dict(cfg_json, __n=n)
    out = subprocess.run(
        [node, str(RUNNER), str(ENGINE), json.dumps(cfg_json)],
        capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


CASES = [
    # noyau pur
    (SimConfig(L=0.4, R=0.8, B=0.8, rho=0.7),
     {"L": 0.4, "R": 0.8, "B": 0.8, "rho": 0.7}),
    # substituabilite + charge en liste
    (SimConfig(L=[0.3, 0.5, 0.9, 0.4], R=0.75, B=0.6, rho=0.85, s=0.4),
     {"L_ramp": [0.3, 0.5, 0.9, 0.4], "R": 0.75, "B": 0.6,
      "rho": 0.85, "s": 0.4}),
    # remboursement 6.1 + Theta evolutif 6.2
    (SimConfig(L=0.45, R=0.7, B=0.65, rho=0.85, mu0=0.4, gamma=1.2,
               D_crit=0.6,
               theta_params=ThetaParams(theta0=1.0, theta_min=0.3,
                                        alpha=0.25, beta=0.15, tau=0.15)),
     {"L": 0.45, "R": 0.7, "B": 0.65, "rho": 0.85, "mu0": 0.4,
      "gamma": 1.2, "D_crit": 0.6,
      "theta_params": {"theta0": 1.0, "theta_min": 0.3, "alpha": 0.25,
                       "beta": 0.15, "tau": 0.15}}),
    # controle 6.3 + recuperation 6.5 (tout couple)
    (SimConfig(L=0.45, R=0.7, B=0.6, rho=0.8, mu0=0.3, D_crit=0.6,
               control=ControlParams(chi=0.15, kappa=0.4, eta=0.5,
                                     delta=0.05, u_max=1.5, gain=4.0,
                                     m_ref=0.2),
               recovery=RecoveryParams(delta_D=0.3, delta_B=0.5,
                                       B_crit=0.4, R_min=0.2)),
     {"L": 0.45, "R": 0.7, "B": 0.6, "rho": 0.8, "mu0": 0.3,
      "D_crit": 0.6,
      "control": {"chi": 0.15, "kappa": 0.4, "eta": 0.5, "delta": 0.05,
                  "u_max": 1.5, "gain": 4.0, "m_ref": 0.2},
      "recovery": {"delta_D": 0.3, "delta_B": 0.5, "B_crit": 0.4,
                   "R_min": 0.2}}),
    # incapacite critique C -> 0 via B = 0 (conventions de cas limites)
    (SimConfig(L=0.4, R=0.8, B=0.0, rho=0.7),
     {"L": 0.4, "R": 0.8, "B": 0.0, "rho": 0.7}),
]


@pytest.mark.parametrize("py_cfg,js_cfg", CASES,
                         ids=["noyau", "liste+s", "6.1+6.2",
                              "6.3+6.5", "C=0"])
def test_trajectories_match(py_cfg, js_cfg):
    n = 60
    py = simulate(py_cfg, n)
    js = run_js(js_cfg, n)
    for i in range(n):
        m_js = -math.inf if js["M"][i] == "-inf" else js["M"][i]
        if math.isinf(py.M[i]):
            assert math.isinf(m_js) and m_js < 0
        else:
            assert m_js == pytest.approx(py.M[i], abs=1e-9)
        assert js["D"][i] == pytest.approx(py.D[i], abs=1e-9)
        assert js["theta"][i] == pytest.approx(py.theta[i], abs=1e-9)
        assert js["C"][i] == pytest.approx(py.C[i], abs=1e-9)
        assert js["U"][i] == pytest.approx(py.U[i], abs=1e-9)
        assert js["mu"][i] == pytest.approx(py.mu[i], abs=1e-9)
        assert js["zone"][i] == py.zone[i].value
