"""Garde-fous de configuration et cas limites."""

import pytest

from mcs import core
from mcs import extensions as ext
from mcs.network import NetworkConfig, simulate_network
from mcs.protocol import Protocol, ProtocolError, ProxySpec
from mcs.simulator import SimConfig, simulate


def test_empty_series_and_invalid_steps_are_rejected():
    with pytest.raises(ValueError, match="vide"):
        SimConfig(L=[])
    with pytest.raises(ValueError, match="n_steps"):
        simulate(SimConfig(), 0)


def test_threshold_order_and_hysteresis_are_validated():
    with pytest.raises(ValueError, match="seuils"):
        SimConfig(thresholds={"viable": 0.1, "tension": 0.2,
                              "saturation": 0.05, "pre_rupture": -0.05})
    with pytest.raises(ValueError, match="hysteresis"):
        SimConfig(hysteresis_k=0)


def test_extension_parameter_domains_are_validated():
    with pytest.raises(ValueError):
        ext.ThetaParams(theta0=0)
    with pytest.raises(ValueError):
        ext.ThetaParams(theta0=1, theta_min=2)
    with pytest.raises(ValueError):
        ext.ControlParams(eta=-1)
    with pytest.raises(ValueError):
        ext.RecoveryParams(R_min=1.5)


def test_core_rejects_invalid_leak_inputs():
    with pytest.raises(ValueError):
        core.leak(-1, 0.5, 0.5)
    with pytest.raises(ValueError):
        core.leak(1, 1.2, 0.5)


def test_network_configuration_is_validated():
    with pytest.raises(ValueError, match="vide"):
        NetworkConfig([], [])
    with pytest.raises(ValueError, match="n x n"):
        NetworkConfig([SimConfig()], [[0, 1]])
    with pytest.raises(ValueError):
        NetworkConfig([SimConfig()], [[-0.1]])
    with pytest.raises(ValueError, match="n_steps"):
        simulate_network(NetworkConfig([SimConfig()], [[0.0]]), 0)


def test_protocol_rejects_incoherent_or_ambiguous_declarations():
    base = dict(name="p", author="a", time_step="semaine", L_crit=1,
                t_regulation_cible=1, delai_critique=1)
    with pytest.raises(ProtocolError):
        Protocol(**base, rho=1.2).freeze()
    with pytest.raises(ProtocolError, match="uniques"):
        Protocol(**base, proxies=[ProxySpec("L", "0", "1"),
                                  ProxySpec("L", "0", "1")]).freeze()
    with pytest.raises(ProtocolError, match="poids manquants"):
        Protocol(**base, aggregation="weighted", weights={"L": 1},
                 proxies=[ProxySpec("L", "0", "1"),
                          ProxySpec("R", "0", "1")]).freeze()
