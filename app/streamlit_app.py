"""Prototype interactif MCS (§ 8) - simulateur a curseurs Streamlit.

Lancer :  streamlit run app/streamlit_app.py

Outil d'exploration et de formation, PAS un outil de diagnostic valide.
Le tableau de bord affiche M(t) avec bande d'incertitude et D(t) comme
indicateur avance, plutot que M(t) seul.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd
import streamlit as st

from mcs import (ControlParams, RecoveryParams, SimConfig, ThetaParams,
                 core, simulate)
from mcs.scenarios import ALL_SCENARIOS

st.set_page_config(page_title="MCS - Indice de Marge Systemique",
                   layout="wide")
st.title("Modele de Coherence Systemique - prototype interactif")
st.caption("Outil d'exploration pedagogique. Ce n'est pas un diagnostic "
           "valide : M(t) se lit comme un indice ordinal avec incertitude.")

with st.sidebar:
    st.header("Noyau")
    L = st.slider("Charge L", 0.0, 1.5, 0.40, 0.01)
    R = st.slider("Recuperation R", 0.0, 1.0, 0.75, 0.01)
    B = st.slider("Boucles de retour B", 0.0, 1.0, 0.75, 0.01)
    theta0 = st.slider("Capacite nominale Theta0", 0.1, 3.0, 1.0, 0.05)
    D0 = st.slider("Dette initiale D0", 0.0, 1.0, 0.0, 0.01)
    rho = st.slider("Memoire de dette rho", 0.0, 1.0, 0.85, 0.01)
    s = st.slider("Substituabilite s (0 = produit pur)", 0.0, 1.0, 0.0, 0.05)
    n_steps = st.slider("Nombre de pas", 10, 200, 60, 5)

    st.header("Extensions")
    use_repay = st.checkbox("6.1 Remboursement actif")
    mu0 = st.slider("mu0", 0.0, 1.0, 0.3, 0.05) if use_repay else 0.0
    gamma = st.slider("gamma (piege de dette)", 0.0, 5.0, 1.0, 0.1) if use_repay else 1.0

    use_theta = st.checkbox("6.2 Capacite evolutive")
    tp = None
    if use_theta:
        alpha = st.slider("alpha (dette -> usure)", 0.0, 1.0, 0.25, 0.05)
        beta = st.slider("beta (boucles -> usure)", 0.0, 1.0, 0.15, 0.05)
        tau = st.slider("tau (inertie)", 0.05, 1.0, 0.2, 0.05)
        tp = ThetaParams(theta0=theta0, theta_min=0.2,
                         alpha=alpha, beta=beta, tau=tau)

    use_ctrl = st.checkbox("6.3 Controle")
    cp = None
    if use_ctrl:
        gain = st.slider("gain du regulateur", 0.0, 12.0, 2.0, 0.5)
        chi = st.slider("chi (cout de charge)", 0.0, 0.5, 0.15, 0.01)
        kappa = st.slider("kappa (restauration de B)", 0.0, 1.0, 0.4, 0.05)
        eta = st.slider("eta (degradation de B)", 0.05, 1.0, 0.5, 0.05)
        cp = ControlParams(chi=chi, kappa=kappa, eta=eta,
                           delta=0.05, u_max=1.5, gain=gain, m_ref=0.15)
        st.caption(f"U* = kappa/(2 eta) = {kappa / (2 * eta):.2f}")

    use_rec = st.checkbox("6.5 Recuperation evolutive")
    rp = None
    if use_rec:
        dD = st.slider("delta_D (dette -> R_eff)", 0.0, 1.0, 0.3, 0.05)
        dB = st.slider("delta_B (boucles -> R_eff)", 0.0, 1.0, 0.5, 0.05)
        rp = RecoveryParams(delta_D=dD, delta_B=dB, B_crit=0.4, R_min=0.1)

    st.header("Incertitude")
    err = st.slider("Erreur relative des proxys (%)", 0, 30, 10) / 100.0

cfg = SimConfig(L=L, R=R, B=B, theta0=theta0, D0=D0, rho=rho, s=s,
                mu0=mu0, gamma=gamma, D_crit=0.6,
                theta_params=tp, control=cp, recovery=rp)
res = simulate(cfg, n_steps)

df = pd.DataFrame(res.to_dict()).set_index("t")
df["dM"] = [core.margin_uncertainty(m, a, c, rel_err_R=err, rel_err_B=err)
            for m, a, c in zip(df["M"], df["A"], df["C"])]
df["M_lo"], df["M_hi"] = df["M"] - df["dM"], df["M"] + df["dM"]

c1, c2 = st.columns(2)
with c1:
    st.subheader("Indice de Marge Systemique M(t)")
    st.line_chart(df[["M", "M_lo", "M_hi"]],
                  color=["#1f77b4", "#c0c0c0", "#c0c0c0"])
    st.caption("Zones pedagogiques : viable > 0.30 | tension > 0.10 | "
               "saturation > 0.05 | pre-rupture [-0.05, 0.05] | rupture < -0.05")
with c2:
    st.subheader("Dette invisible D(t) - indicateur avance")
    st.line_chart(df[["D"]], color=["#d62728"])

c3, c4 = st.columns(2)
with c3:
    st.subheader("Capacite C(t) vs charge totale A(t)")
    st.line_chart(df[["A", "C"]])
with c4:
    st.subheader("Etats internes")
    st.line_chart(df[["R_eff", "B_eff", "theta", "U"]])

last = df.iloc[-1]
zone = res.zone[-1].value.replace("_", " ")
st.metric("Zone finale (avec hysteresis)", zone,
          delta=f"M = {last['M']:.3f} +/- {last['dM']:.3f}")

st.divider()
st.subheader("Scenarios pedagogiques (§ 7)")
name = st.selectbox("Charger un scenario", ["-"] + list(ALL_SCENARIOS))
if name != "-":
    out = ALL_SCENARIOS[name]()
    if isinstance(out, list):     # reseau couple
        for i, r in enumerate(out):
            st.line_chart(pd.DataFrame({"M": r.M, "D": r.D}),
                          height=200)
    else:
        st.line_chart(pd.DataFrame({"M": out.M, "D": out.D}))
