"""Input integrity: compare input files with the manifest's SHA-256 hashes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from src.config import resolve_path
from src.run import PipelineError, ProcessingRun


def verify_input_hashes(manifest: dict, data_dir: Path) -> list[str]:
    """Return one problem string per input file that is missing or altered."""
    problems: list[str] = []
    for entry in manifest["files"]:
        path = Path(data_dir) / entry["file"]
        if not path.exists():
            problems.append(f"{entry['file']}: file is missing")
            continue
        data = path.read_bytes()
        if len(data) != entry["bytes"]:
            problems.append(f"{entry['file']}: size {len(data)} != {entry['bytes']}")
        if hashlib.sha256(data).hexdigest() != entry["sha256"]:
            problems.append(f"{entry['file']}: SHA-256 does not match manifest")
    return problems


def stage_check_input_integrity(run: ProcessingRun) -> None:
    """First pipeline stage: stop the run if an input file differs from data/manifest.json.

    Set "verify_input_hashes": false in the config to skip the check (for example
    when an input file is deliberately edited for a test).
    """
    cfg = run.cfg
    if not cfg.get("verify_input_hashes", True):
        run.log_step("manifest.json", "integrity check", "skipped: verify_input_hashes is false",
                     None, None)
        return
    data_dir = resolve_path(cfg, cfg.get("data_dir", ""))
    manifest_path = data_dir / "manifest.json"
    if not manifest_path.exists():
        raise PipelineError(f"Input manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    problems = verify_input_hashes(manifest, data_dir)
    checked = len(manifest["files"])
    run.log_step("manifest.json", "integrity check", "SHA-256 and size of each input file",
                 checked, checked - len(problems))
    run.add_check("input files match manifest SHA-256 hashes", 0, len(problems))
    if problems:
        raise PipelineError("Input integrity check failed: " + "; ".join(problems))