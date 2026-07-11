#!/usr/bin/env python3
"""Run the complete empirical evidence pipeline on one downloaded real dataset."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from mcs.empirical_evidence import build_evidence_report, file_sha256
from mcs.real_adapters import prepare_hydraulic, prepare_ims_bearings, prepare_metropt3


def _prepare(slug: str, root: Path):
    if slug == "metropt3":
        return prepare_metropt3(root)
    if slug == "hydraulic":
        return prepare_hydraulic(root)
    if slug.startswith("ims_bearings"):
        test_name = slug.removeprefix("ims_bearings_") or "2nd_test"
        return prepare_ims_bearings(root, test_name=test_name)
    raise ValueError(f"unknown dataset {slug}")


def _plot(prepared, report: dict, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    x = np.arange(len(prepared.L))
    fig, axes = plt.subplots(4, 1, figsize=(14, 10), sharex=True)
    axes[0].plot(x, prepared.L, linewidth=0.8, label="L")
    axes[0].set_ylabel("L")
    axes[1].plot(x, prepared.R, linewidth=0.8, label="R")
    axes[1].set_ylabel("R")
    axes[2].plot(x, prepared.B, linewidth=0.8, label="B")
    axes[2].set_ylabel("B")
    from mcs.empirical_evidence import detector_scores

    score = detector_scores(prepared.L, prepared.R, prepared.B)["mcs_complet"]
    axes[3].plot(x, score, linewidth=0.9, label="-M (risque)")
    mcs = next(item for item in report["detectors"] if item["name"] == "mcs_complet")
    axes[3].axhline(mcs["threshold"], linestyle="--", linewidth=1, label="seuil calibré")
    axes[3].set_ylabel("-M")
    axes[3].set_xlabel("pas temporel réel")
    for ax in axes:
        ax.axvline(prepared.validation_start, linestyle=":", linewidth=1)
        for event in prepared.events:
            ax.axvspan(event.start, event.end, alpha=0.12)
        ax.grid(alpha=0.2)
    axes[3].legend(loc="best")
    fig.suptitle(f"{prepared.dataset} — proxys mesurés, split temporel et événements externes")
    fig.tight_layout()
    fig.savefig(output / f"{prepared.dataset}_timeline.png", dpi=170, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", choices=["metropt3", "hydraulic", "ims_bearings_1st_test", "ims_bearings_2nd_test", "ims_bearings_3rd_test"])
    parser.add_argument("--data-root", default="data/real")
    parser.add_argument("--reports", default="reports/real")
    parser.add_argument("--target-fpr", type=float, default=0.05)
    parser.add_argument("--horizon", type=int, default=None)
    args = parser.parse_args()

    base_slug = "ims_bearings" if args.dataset.startswith("ims_bearings") else args.dataset
    root = Path(args.data_root) / base_slug
    prepared = _prepare(args.dataset, root)
    protocol_path = Path("protocols/real") / ("ims_bearings_v1.yaml" if base_slug == "ims_bearings" else f"{base_slug}_v1.yaml")
    horizon = args.horizon or {"metropt3": 96, "hydraulic": 20, "ims_bearings": 48}[base_slug]
    limitations = tuple(
        x for x in [
            prepared.metadata.get("interpretation_warning"),
            "Proxy definitions are engineering hypotheses and not direct measurements of the latent MCS constructs.",
            "A positive result is evidence on this dataset and protocol only; it is not universal validation.",
        ] if x
    )
    report = build_evidence_report(
        dataset=prepared.dataset,
        source_sha256=prepared.source_sha256,
        protocol_sha256=file_sha256(protocol_path),
        L=prepared.L,
        R=prepared.R,
        B=prepared.B,
        events=list(prepared.events),
        calibration_end=prepared.calibration_end,
        validation_start=prepared.validation_start,
        horizon=horizon,
        target_fpr=args.target_fpr,
        limitations=limitations,
    ).as_dict()
    report["metadata"] = prepared.metadata
    report["events"] = [vars(x) for x in prepared.events]
    out = Path(args.reports)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{prepared.dataset}_evidence.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _plot(prepared, report, out)
    print(path)


if __name__ == "__main__":
    main()
