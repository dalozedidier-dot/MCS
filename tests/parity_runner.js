// Runner du test de parite JS/Python (tests/test_js_parity.py).
const path = process.argv[2];
const cfg = JSON.parse(process.argv[3]);
const n = cfg.__n; delete cfg.__n;
if (cfg.L_ramp) { cfg.L = cfg.L_ramp; delete cfg.L_ramp; }
const MCS = require(path);
const res = MCS.simulate(cfg, n);
const safe = x => (x === -Infinity ? "-inf" : x);
console.log(JSON.stringify({
  M: res.M.map(safe), D: res.D, theta: res.theta, C: res.C,
  zone: res.zone, U: res.U, mu: res.mu,
}));
