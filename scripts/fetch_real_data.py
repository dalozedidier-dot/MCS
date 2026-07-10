#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from mcs.realdata import DATASETS, catalogue, fetch_dataset, verify_provenance


def main() -> None:
    parser = argparse.ArgumentParser(description="Télécharge uniquement des jeux de données réels officiels.")
    parser.add_argument("dataset", nargs="?", choices=sorted(DATASETS))
    parser.add_argument("--all", action="store_true", help="Télécharger les trois sources réelles")
    parser.add_argument("--base-dir", default="data/real")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()
    if args.list:
        print(json.dumps(catalogue(), ensure_ascii=False, indent=2))
        return
    selected = list(DATASETS) if args.all else ([args.dataset] if args.dataset else [])
    if not selected:
        parser.error("Choisir un dataset ou --all")
    for slug in selected:
        root = fetch_dataset(slug, args.base_dir, force=args.force)
        check = verify_provenance(root)
        print(f"{slug}: {root} — intégrité {'OK' if check['ok'] else 'ECHEC'}")


if __name__ == "__main__":
    main()
