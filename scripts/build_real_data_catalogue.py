#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from mcs.realdata import catalogue

out = Path("docs/data/real_datasets.json")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({"status":"catalogue_only_no_empirical_results_bundled","datasets":catalogue()}, ensure_ascii=False, indent=2), encoding="utf-8")
print(out)
