#!/usr/bin/env python3
"""Shadow-audit CLI only; production reports use backend_report.py."""
from __future__ import annotations

from geo_presales_core.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
