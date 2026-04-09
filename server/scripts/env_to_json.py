#!/usr/bin/env python3
"""
Print `server/.env` as JSON (same shape as Railway / Vercel bulk env paste).

Run from repo root:
  python3 server/scripts/env_to_json.py

Warning: output contains secrets. Do not commit or paste into public chats.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> None:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.is_file():
        print(f"No file: {env_path}", file=sys.stderr)
        sys.exit(1)
    out: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip()
        if key:
            out[key] = val
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
