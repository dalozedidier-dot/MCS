#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from mcs.realdata import verify_provenance


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", help="Ex. data/real/metropt3")
    parser.add_argument("--output")
    args = parser.parse_args()
    result = verify_provenance(args.root)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    print(text)
    if not result["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
