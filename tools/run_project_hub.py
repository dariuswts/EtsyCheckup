#!/usr/bin/env python3
"""Launch the local POD Opportunity Intelligence project hub."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HUB_DIR = ROOT / "tools" / "project_hub"
if str(HUB_DIR) not in sys.path:
    sys.path.insert(0, str(HUB_DIR))

from hub_server import run_server  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local project hub.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host. Only 127.0.0.1 is allowed.")
    parser.add_argument("--port", default=8765, type=int, help="Local port.")
    args = parser.parse_args()
    if args.host != "127.0.0.1":
        raise SystemExit("Project hub only binds to 127.0.0.1.")
    run_server(host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
