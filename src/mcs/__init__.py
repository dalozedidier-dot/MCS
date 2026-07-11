"""MCS - Modele de Coherence Systemique.

Indice de Marge Systemique M(t), dette invisible D(t) et pre-rupture.
Implementation du document de travail de Didier Daloze.

Avertissement : cadre exploratoire et pedagogique, confrontable aux
donnees. Ce n'est PAS un outil de diagnostic clinique, psychologique
ou organisationnel valide.
"""

from .baselines import (
    ComparisonRecord,
    FalsificationRecord,
    compare_detectors,
    falsification_report,
    falsification_run,
    mcs_alarm,
)
from .benchmark import (
    BenchmarkResult,
    Trajectory,
    benchmark_markdown,
    generate,
    paired_median_gain,
    run_benchmark,
)
from .core import (
    DEFAULT_THRESHOLDS,
    HysteresisClassifier,
    Zone,
    bounded_margin_index,
    capacity,
    classify,
    debt_rest_level,
    debt_update,
    leak,
    margin,
    margin_index,
    margin_uncertainty,
    overflow,
    total_load,
)
from .experiments import (
    HysteresisLoop,
    RegimeMap,
    hysteresis_loop,
    load_ramp,
    memoryless_config,
    perturbation_slope,
    regime_map,
)
from .extensions import (
    ControlParams,
    RecoveryParams,
    ThetaParams,
    alpha_runaway,
    control_command,
    debt_update_with_repayment,
    effective_feedback,
    effective_load,
    effective_recovery,
    normalized_debt,
    optimal_control,
    repayment_rate,
    rescale_time_step,
    theta_target,
    theta_update,
    viability_repayment_threshold,
)
from .network import NetworkConfig, saturation, simulate_network
from .protocol import Protocol, ProtocolError, ProxySpec, compute_series
from .robustness import (
    cascade_sweep,
    false_alarm_study,
    monte_carlo,
    network_stability,
    sensitivity_tornado,
    spectral_radius,
)
from .simulator import SimConfig, SimResult, simulate

__version__ = "0.8.2"
__all__ = [
    "DEFAULT_THRESHOLDS",
    "HysteresisClassifier",
    "Zone",
    "bounded_margin_index",
    "capacity",
    "classify",
    "debt_rest_level",
    "debt_update",
    "leak",
    "margin",
    "margin_index",
    "margin_uncertainty",
    "overflow",
    "total_load",
    "ControlParams",
    "RecoveryParams",
    "ThetaParams",
    "alpha_runaway",
    "control_command",
    "debt_update_with_repayment",
    "effective_feedback",
    "effective_load",
    "effective_recovery",
    "normalized_debt",
    "optimal_control",
    "repayment_rate",
    "rescale_time_step",
    "theta_target",
    "theta_update",
    "viability_repayment_threshold",
    "NetworkConfig",
    "saturation",
    "simulate_network",
    "SimConfig",
    "SimResult",
    "simulate",
    "Protocol",
    "ProtocolError",
    "ProxySpec",
    "compute_series",
    "cascade_sweep",
    "false_alarm_study",
    "monte_carlo",
    "network_stability",
    "sensitivity_tornado",
    "spectral_radius",
    "ComparisonRecord",
    "FalsificationRecord",
    "compare_detectors",
    "falsification_report",
    "falsification_run",
    "mcs_alarm",
    "HysteresisLoop",
    "RegimeMap",
    "hysteresis_loop",
    "load_ramp",
    "memoryless_config",
    "perturbation_slope",
    "regime_map",
    "BenchmarkResult",
    "Trajectory",
    "benchmark_markdown",
    "generate",
    "paired_median_gain",
    "run_benchmark",
]
