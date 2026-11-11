#!/usr/bin/env python3
"""Inject the aggregate metrics snapshot into the one-page site (no network, no dependencies).

    pos metrics --vault <private vault> --out metrics/snapshot.json
    python3 site/build.py
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
template = (ROOT / "site/template.html").read_text(encoding="utf-8")
snapshot = (ROOT / "metrics/snapshot.json").read_text(encoding="utf-8").replace("</", "<\\/")
(ROOT / "site/index.html").write_text(template.replace("__SNAPSHOT__", snapshot), encoding="utf-8")
print("wrote site/index.html")
