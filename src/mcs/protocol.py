"""Phase 2 - Protocole empirique minimal (ROADMAP, § 9.2-9.3).

Rendre le MCS testable sur donnees reelles SANS circularite : les
proxys, ancrages, regles d'agregation, pas de temps et seuils sont
declares et GELES (hash SHA-256 + date) AVANT tout calcul de M.
Le module refuse de calculer M(t) sur un protocole non gele ou modifie
apres gel : l'anti-circularite est appliquee par le code, pas seulement
promise par le texte.

Pipeline :
    Protocol -> freeze() -> save (YAML/JSON) ... collecte ...
    load -> verify() -> load_csv -> compute_series -> report

Normalisations du § 9.3 :
    L(t)  = charge observee / charge critique declaree
    R(t)  = clip(temps cible de regulation / temps observe, 0, 1)
    B(t)  = clip(delai critique / delai signal->decision observe, 0, 1)
    D(0)  = somme des irritants ouverts, ponderes par anciennete
Agregation multi-proxys : "worst" (minimum, lecture prudente) ou
"weighted" (moyenne ponderee declaree).

YAML si PyYAML est installe (extra [protocol]), JSON sinon.
"""

from __future__ import annotations

import csv
import datetime as _dt
import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import core
from .core import HysteresisClassifier, clip
from .validation import non_negative, positive, unit_interval, validate_thresholds

try:  # dependance optionnelle
    import yaml as _yaml
except ImportError:  # pragma: no cover
    _yaml = None


class ProtocolError(RuntimeError):
    """Violation du protocole pre-enregistre (non gele, altere...)."""


# ---------------------------------------------------------------------------
# Declaration pre-enregistree
# ---------------------------------------------------------------------------

@dataclass
class ProxySpec:
    """Declaration d'un proxy avec ses ancrages 0 et 1 (§ 9.2).

    anchor_zero / anchor_one : description operatoire de ce que
    signifient les valeurs extremes, redigee AVANT la collecte.
    """
    name: str
    anchor_zero: str
    anchor_one: str
    rel_err: float = 0.10          # erreur relative declaree (§ 4)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("le nom du proxy ne peut pas etre vide")
        if not self.anchor_zero.strip() or not self.anchor_one.strip():
            raise ValueError("les deux ancrages du proxy doivent etre decrits")
        non_negative("rel_err", self.rel_err)


@dataclass
class Protocol:
    """Protocole complet, gele avant tout calcul de M."""
    name: str
    author: str
    time_step: str                                 # "jour", "semaine"...
    L_crit: float                                  # charge critique
    t_regulation_cible: float                      # temps cible (R)
    delai_critique: float                          # delai critique (B)
    aggregation: str = "worst"                     # "worst" | "weighted"
    weights: dict[str, float] = field(default_factory=dict)
    proxies: list[ProxySpec] = field(default_factory=list)
    thresholds: dict[str, float] = field(
        default_factory=lambda: dict(core.DEFAULT_THRESHOLDS))
    hysteresis_k: int = 3
    rho: float = 0.8
    theta0: float = 1.0
    s: float = 0.0
    irritant_age_weight: float = 0.1     # ponderation par pas d'anciennete
    declared_at: str = ""
    frozen_at: str | None = None
    fingerprint: str | None = None

    # -- gel / verification --------------------------------------------

    def _canonical(self) -> str:
        d = asdict(self)
        d.pop("frozen_at", None)
        d.pop("fingerprint", None)
        return json.dumps(d, sort_keys=True, ensure_ascii=True)

    def _validate(self) -> None:
        if not self.name.strip() or not self.author.strip() or not self.time_step.strip():
            raise ProtocolError("name, author et time_step sont obligatoires")
        if self.aggregation not in ("worst", "weighted"):
            raise ProtocolError("aggregation doit etre 'worst' ou 'weighted'")
        try:
            positive("L_crit", self.L_crit)
            positive("t_regulation_cible", self.t_regulation_cible)
            positive("delai_critique", self.delai_critique)
            unit_interval("rho", self.rho)
            positive("theta0", self.theta0)
            unit_interval("s", self.s)
            non_negative("irritant_age_weight", self.irritant_age_weight)
            self.thresholds = validate_thresholds(self.thresholds)
        except (TypeError, ValueError) as exc:
            raise ProtocolError(str(exc)) from exc
        if self.hysteresis_k < 1:
            raise ProtocolError("hysteresis_k doit etre superieur ou egal a 1")
        names = [proxy.name for proxy in self.proxies]
        if len(names) != len(set(names)):
            raise ProtocolError("les noms de proxys doivent etre uniques")
        if self.aggregation == "weighted":
            if not self.weights:
                raise ProtocolError("agregation ponderee sans poids declares")
            missing = [name for name in names if name not in self.weights]
            if missing:
                raise ProtocolError(f"poids manquants pour les proxys : {missing}")
            extra = [name for name in self.weights if name not in names]
            if extra:
                raise ProtocolError(f"poids sans proxy declare : {extra}")
            if any(weight <= 0 for weight in self.weights.values()):
                raise ProtocolError("les poids doivent etre strictement positifs")

    def freeze(self) -> Protocol:
        """Valide puis gele le protocole par empreinte SHA-256."""
        self._validate()
        if not self.declared_at:
            self.declared_at = _dt.date.today().isoformat()
        self.frozen_at = _dt.datetime.now(_dt.timezone.utc).isoformat(
            timespec="seconds")
        self.fingerprint = hashlib.sha256(
            self._canonical().encode()).hexdigest()
        return self

    def verify(self) -> None:
        """Leve ProtocolError si non gele, invalide ou altere apres gel."""
        if not self.frozen_at or not self.fingerprint:
            raise ProtocolError(
                "protocole non gele : declarer puis freeze() AVANT "
                "toute lecture des donnees (anti-circularite, § 9.2)")
        if hashlib.sha256(self._canonical().encode()).hexdigest() \
                != self.fingerprint:
            raise ProtocolError(
                "protocole modifie apres gel : empreinte SHA-256 invalide")
        self._validate()

    # -- serialisation --------------------------------------------------

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        d = asdict(self)
        if path.suffix in (".yaml", ".yml"):
            if _yaml is None:
                raise ProtocolError("PyYAML absent : pip install "
                                    "'mcs-model[protocol]' ou utiliser .json")
            path.write_text(_yaml.safe_dump(d, allow_unicode=True,
                                            sort_keys=False),
                            encoding="utf-8")
        else:
            path.write_text(json.dumps(d, indent=2, ensure_ascii=False),
                            encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: str | Path) -> Protocol:
        path = Path(path)
        text = path.read_text(encoding="utf-8")
        if path.suffix in (".yaml", ".yml"):
            if _yaml is None:
                raise ProtocolError("PyYAML absent pour lire du YAML")
            d = _yaml.safe_load(text)
        else:
            d = json.loads(text)
        d["proxies"] = [ProxySpec(**p) for p in d.get("proxies", [])]
        return cls(**d)


# ---------------------------------------------------------------------------
# Normalisations (§ 9.3)
# ---------------------------------------------------------------------------

def normalize_load(load: float, L_crit: float) -> float:
    """L(t) = charge observee / charge critique declaree (peut depasser 1)."""
    if L_crit <= 0:
        raise ValueError("L_crit doit etre strictement positif")
    return max(0.0, load / L_crit)


def normalize_recovery(t_observed: float, t_target: float) -> float:
    """R(t) = clip(temps cible / temps observe, 0, 1).

    Reguler aussi vite que la cible => R = 1 ; deux fois plus lentement
    => R = 0.5. t_observed <= 0 (jamais regule) => R = 0.
    """
    if t_target <= 0:
        raise ValueError("t_target doit etre strictement positif")
    if t_observed <= 0:
        return 0.0
    return clip(t_target / t_observed, 0.0, 1.0)


def normalize_feedback(delay_observed: float, delay_critical: float) -> float:
    """B(t) = clip(delai critique / delai signal->decision, 0, 1)."""
    if delay_critical <= 0:
        raise ValueError("delay_critical doit etre strictement positif")
    if delay_observed <= 0:
        return 1.0
    return clip(delay_critical / delay_observed, 0.0, 1.0)


def initial_debt(irritants: list[tuple[float, int]],
                 age_weight: float) -> float:
    """D(0) = somme des irritants ouverts ponderes par anciennete :
    sum severite_i * (1 + age_weight * age_i)."""
    if age_weight < 0:
        raise ValueError("age_weight doit etre positif ou nul")
    if any(age < 0 for _, age in irritants):
        raise ValueError("l'anciennete des irritants doit etre positive ou nulle")
    return sum(sev * (1.0 + age_weight * age)
               for sev, age in irritants if sev > 0)


def aggregate(values: dict[str, float], proto: Protocol) -> float:
    """Regle d'agregation declaree : 'worst' = min (prudente),
    'weighted' = moyenne ponderee par proto.weights."""
    if not values:
        raise ValueError("aucune valeur a agreger")
    if proto.aggregation == "worst":
        return min(values.values())
    w = {k: proto.weights.get(k, 0.0) for k in values}
    total = sum(w.values())
    if total <= 0:
        raise ProtocolError("poids d'agregation nuls ou absents")
    return sum(values[k] * w[k] for k in values) / total


# ---------------------------------------------------------------------------
# Donnees et calcul
# ---------------------------------------------------------------------------

REQUIRED_COLUMNS = ("t", "load", "t_regulation", "delai_signal_decision")


def load_csv(path: str | Path) -> list[dict]:
    """Lit un CSV (agenda, tickets, incidents). Colonnes requises :
    t, load, t_regulation, delai_signal_decision. Optionnelles :
    irritant_severite, irritant_age (lignes de dette initiale, t < 0).
    """
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = [c for c in REQUIRED_COLUMNS
                   if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"colonnes manquantes : {missing}")
        for row in reader:
            rows.append({k: (float(v) if v not in (None, "",) else math.nan)
                         for k, v in row.items()})
    return rows


@dataclass
class Report:
    """Rapport automatique : M(t) +- IC, D(t), zones ordinales."""
    protocol_name: str
    fingerprint: str
    t: list[int]
    L: list[float]
    R: list[float]
    B: list[float]
    D: list[float]
    M: list[float]
    M_err: list[float]
    zone: list[str]
    D0: float

    def leading_indicator_check(self) -> dict:
        """La dette monte-t-elle AVANT que M ne sorte de la zone viable ?
        Retourne {debt_rising_at, first_alert, lead} (pas de temps)."""
        rising = next((i for i in range(1, len(self.D))
                       if self.D[i] > self.D[i - 1] + 1e-12), None)
        alert = next((i for i, z in enumerate(self.zone)
                      if z != core.Zone.VIABLE.value), None)
        lead = (alert - rising) if (rising is not None
                                    and alert is not None) else None
        return {"debt_rising_at": rising, "first_alert": alert,
                "lead": lead}

    def to_markdown(self) -> str:
        lines = [
            f"# Rapport MCS - {self.protocol_name}",
            f"Protocole gele, empreinte `{self.fingerprint[:16]}...`",
            f"D(0) = {self.D0:.3f} (irritants ponderes par anciennete)",
            "",
            "| t | L | R | B | D | M +- dM | zone |",
            "|---|---|---|---|---|---------|------|",
        ]
        for i in range(len(self.t)):
            lines.append(
                f"| {self.t[i]} | {self.L[i]:.2f} | {self.R[i]:.2f} "
                f"| {self.B[i]:.2f} | {self.D[i]:.3f} "
                f"| {self.M[i]:+.3f} +- {self.M_err[i]:.3f} "
                f"| {self.zone[i]} |")
        lic = self.leading_indicator_check()
        lines += [
            "",
            f"Dette croissante des t = {lic['debt_rising_at']}, "
            f"premiere alerte de zone a t = {lic['first_alert']} "
            f"(avance : {lic['lead']} pas).",
            "",
            "> Garde-fous (§ 9.8) : M est un indice ORDINAL, rapporte "
            "avec incertitude ; aucun diagnostic sur une valeur isolee ; "
            "les proxys ont ete geles avant calcul.",
        ]
        return "\n".join(lines)


def compute_series(proto: Protocol, rows: list[dict]) -> Report:
    """Applique le protocole gele aux donnees : normalisations § 9.3,
    D(0) depuis les irritants, dynamique de dette du noyau, M +- IC,
    zones confirmees par hysteresis. Refuse un protocole non gele."""
    proto.verify()

    irritants = [(r.get("irritant_severite", 0.0) or 0.0,
                  int(r.get("irritant_age", 0) or 0))
                 for r in rows if r["t"] < 0]
    D0 = initial_debt([(s, a) for s, a in irritants if s > 0],
                      proto.irritant_age_weight)

    data = sorted((r for r in rows if r["t"] >= 0), key=lambda r: r["t"])
    rel = {p.name: p.rel_err for p in proto.proxies}
    eL = rel.get("L", 0.10)
    eR = rel.get("R", 0.10)
    eB = rel.get("B", 0.10)

    rep = Report(proto.name, proto.fingerprint or "", [], [], [], [],
                 [], [], [], [], D0)
    classifier = HysteresisClassifier(k=proto.hysteresis_k,
                                      thresholds=proto.thresholds)
    D = D0
    for row in data:
        L = normalize_load(row["load"], proto.L_crit)
        R = normalize_recovery(row["t_regulation"],
                               proto.t_regulation_cible)
        B = normalize_feedback(row["delai_signal_decision"],
                               proto.delai_critique)
        C = core.capacity(proto.theta0, R, B, proto.s)
        A = core.total_load(L, D)
        M = core.margin_index(A, C)
        dM = core.margin_uncertainty(M, A, C, rel_err_A=eL,
                                     rel_err_R=eR, rel_err_B=eB)
        rep.t.append(int(row["t"]))
        rep.L.append(L)
        rep.R.append(R)
        rep.B.append(B)
        rep.D.append(D)
        rep.M.append(M)
        rep.M_err.append(dM)
        rep.zone.append(classifier.update(M).value)
        D = core.debt_update(D, L, R, B, C, proto.rho)
    return rep
