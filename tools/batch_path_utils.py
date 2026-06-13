from __future__ import annotations

import re
from pathlib import Path


def latest_batch_by_timestamp(project_root: Path, prefix: str) -> Path:
    batches_dir = project_root / "05_DATA_MODEL" / "sample_intake_tests" / "batches"
    pattern = re.compile(rf"^{re.escape(prefix)}_(\d{{8}}_\d{{6}})$")
    candidates = [path for path in batches_dir.glob(f"{prefix}_*") if path.is_dir() and pattern.match(path.name)]
    if candidates:
        return max(candidates, key=lambda item: pattern.match(item.name).group(1))
    return batches_dir / f"{prefix}_EXPLICIT_BATCH_REQUIRED"
