/* Moteur MCS - portage JavaScript fidele du noyau Python (src/mcs).
 *
 * Couvre : noyau (A, C, M, M~, dette, zones + hysteresis), extensions
 * 6.1 (remboursement), 6.2 (Theta evolutif), 6.3 (controle), 6.5
 * (recuperation effective), et la boucle simulate() dans l'ORDRE EXACT
 * du § 5.1 (anti-circularite).
 *
 * La fidelite n'est pas promise mais TESTEE : tests/test_js_parity.py
 * execute ce fichier sous Node et compare les trajectoires au moteur
 * Python a 1e-9 pres. Toute divergence casse la CI.
 *
 * Utilisable en navigateur (window.MCS) et sous Node (module.exports).
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.MCS = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const clip = (x, lo, hi) => Math.max(lo, Math.min(hi, x));

  // -- noyau ---------------------------------------------------------------
  function capacity(theta, R, B, s) {
    s = s || 0.0;
    return theta * (s * (R + B) / 2.0 + (1.0 - s) * R * B);
  }
  function marginIndex(A, C) {
    if (A === 0.0) return 1.0;
    if (C === 0.0) return -Infinity;
    return 1.0 - A / C;
  }
  function boundedMarginIndex(A, C) {
    if (A === 0.0) return 1.0;
    if (C === 0.0 && A > 0.0) return -1.0;
    return (C - A) / (C + A);
  }
  const leak = (L, R, B) => (1.0 - R) * L * (1.0 - B);
  const overflow = (L, C) => Math.max(0.0, L - C);
  const debtUpdate = (D, L, R, B, C, rho) =>
    rho * D + leak(L, R, B) + overflow(L, C);
  const debtRestLevel = (L, R, B, rho) => leak(L, R, B) / (1.0 - rho);

  // -- zones + hysteresis ----------------------------------------------------
  const ZONES = ["coherence_viable", "tension_constructive", "saturation",
                 "pre_rupture", "rupture"];
  const DEFAULT_THRESHOLDS = {viable: 0.30, tension: 0.10,
                              saturation: 0.05, pre_rupture: -0.05};
  function classify(M, th) {
    th = th || DEFAULT_THRESHOLDS;
    if (M > th.viable) return "coherence_viable";
    if (M > th.tension) return "tension_constructive";
    if (M > th.saturation) return "saturation";
    if (M >= th.pre_rupture) return "pre_rupture";
    return "rupture";
  }
  class HysteresisClassifier {
    constructor(k, thresholds) {
      this.k = k === undefined ? 3 : k;
      this.thresholds = thresholds || null;
      this._current = null; this._candidate = null; this._count = 0;
    }
    update(M) {
      const raw = classify(M, this.thresholds || undefined);
      if (this._current === null) { this._current = raw; return raw; }
      if (raw === this._current) { this._candidate = null; this._count = 0; }
      else if (raw === this._candidate) {
        this._count += 1;
        if (this._count >= this.k) {
          this._current = raw; this._candidate = null; this._count = 0;
        }
      } else { this._candidate = raw; this._count = 1; }
      return this._current;
    }
  }

  // -- extensions ---------------------------------------------------------------
  const normalizedDebt = (D, Dcrit) => Math.min(1.0, D / Dcrit);
  const repaymentRate = (mu0, Reff, Dn, gamma) =>
    mu0 * Reff / (1.0 + gamma * Dn);
  function debtUpdateWithRepayment(D, L, R, B, C, rho, mu, extraRepay) {
    const slack = Math.max(0.0, C - L);
    return Math.max(0.0, rho * D + leak(L, R, B) + overflow(L, C)
                    - (mu + (extraRepay || 0.0)) * slack);
  }
  const thetaTarget = (p, Dn, B) =>
    Math.max(p.theta_min, p.theta0 * (1.0 - p.alpha * Dn - p.beta * (1.0 - B)));
  const thetaUpdate = (theta, p, Dn, B) =>
    theta + p.tau * (thetaTarget(p, Dn, B) - theta);
  const alphaRunaway = (rho, Dcrit, theta0, R, B) =>
    (1.0 - rho) * Dcrit / (theta0 * R * B);
  const effectiveLoad = (L, U, p) => L + p.chi * U;
  const effectiveFeedback = (B, U, p) =>
    clip(B * (1.0 + p.kappa * U - p.eta * U * U), 0.0, 1.0);
  const optimalControl = (p) => p.eta <= 0 ? Infinity : p.kappa / (2.0 * p.eta);
  const controlCommand = (Mprev, p) =>
    clip(p.gain * (p.m_ref - Mprev), 0.0, p.u_max);
  const effectiveRecovery = (Rbrut, Dn, Beff, p) =>
    clip(Rbrut - p.delta_D * Dn - p.delta_B * Math.max(0.0, p.B_crit - Beff),
         p.R_min, 1.0);
  const marginUncertainty = (M, A, C, eA, eTh, eR, eB) =>
    C === 0.0 ? Infinity
      : Math.abs(A / C) * (eA || 0) + Math.abs(1.0 - M)
        * ((eTh || 0) + (eR || 0) + (eB || 0));

  // -- simulate (ordre § 5.1, identique a simulator.py) ---------------------------
  const at = (x, t) => typeof x === "function" ? x(t)
    : (typeof x === "number" ? x : x[Math.min(t, x.length - 1)]);

  function simulate(cfg, nSteps) {
    const c = Object.assign({
      L: 0.4, R: 0.8, B: 0.8, theta0: 1.0, D0: 0.0, rho: 0.8, s: 0.0,
      mu0: 0.0, gamma: 1.0, D_crit: 1.0, theta_params: null, control: null,
      recovery: null, hysteresis_k: 3, thresholds: null,
    }, cfg || {});
    const res = {t: [], L: [], L_eff: [], D: [], R_eff: [], B_eff: [],
                 theta: [], A: [], C: [], M: [], M_bounded: [], U: [],
                 mu: [], zone: []};
    const classifier = new HysteresisClassifier(c.hysteresis_k, c.thresholds);
    let D = c.D0;
    let theta = c.theta_params ? c.theta_params.theta0 : c.theta0;
    let ReffState = null;
    let U = 0.0;

    for (let t = 0; t < nSteps; t++) {
      const L = at(c.L, t);
      const Rbrut = at(c.R, t);
      const Bbrut = at(c.B, t);
      const R = ReffState !== null ? ReffState : Rbrut;

      let Leff, Beff;
      if (c.control) {
        Leff = effectiveLoad(L, U, c.control);
        Beff = effectiveFeedback(Bbrut, U, c.control);
      } else { Leff = L; Beff = Bbrut; }

      const C = capacity(theta, R, Beff, c.s);
      const A = Leff + D;
      const M = marginIndex(A, C);

      res.t.push(t); res.L.push(L); res.L_eff.push(Leff); res.D.push(D);
      res.R_eff.push(R); res.B_eff.push(Beff); res.theta.push(theta);
      res.A.push(A); res.C.push(C); res.M.push(M);
      res.M_bounded.push(boundedMarginIndex(A, C)); res.U.push(U);
      res.zone.push(classifier.update(M));

      const Unext = c.control ? controlCommand(M, c.control) : 0.0;

      const Dn = normalizedDebt(D, c.D_crit);
      let mu;
      if (c.mu0 > 0.0) {
        mu = repaymentRate(c.mu0, R, Dn, c.gamma);
        const extra = c.control ? c.control.delta * U : 0.0;
        D = debtUpdateWithRepayment(D, Leff, R, Beff, C, c.rho, mu, extra);
      } else {
        mu = 0.0;
        D = debtUpdate(D, Leff, R, Beff, C, c.rho);
      }
      res.mu.push(mu);

      if (c.recovery) {
        const DnNew = normalizedDebt(D, c.D_crit);
        ReffState = effectiveRecovery(at(c.R, t + 1), DnNew, Beff, c.recovery);
      }
      if (c.theta_params) {
        theta = thetaUpdate(theta, c.theta_params,
                            normalizedDebt(D, c.D_crit), Beff);
      }
      U = Unext;
    }
    return res;
  }

  return {
    clip, capacity, marginIndex, boundedMarginIndex, leak, overflow,
    debtUpdate, debtRestLevel, normalizedDebt, repaymentRate,
    debtUpdateWithRepayment, thetaTarget, thetaUpdate, alphaRunaway,
    effectiveLoad, effectiveFeedback, optimalControl, controlCommand,
    effectiveRecovery, marginUncertainty, classify, HysteresisClassifier,
    DEFAULT_THRESHOLDS, ZONES, simulate,
  };
});
