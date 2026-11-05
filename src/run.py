"""Run state: audit records, validation checks, and safe staged publishing."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import pandas as pd

from src.config import resolve_path

AUDIT_COLUMNS: list[str] = ["step", "source_file", "operation", "rule", "rows_before", "rows_after"]
CHECK_COLUMNS: list[str] = ["check", "expected", "actual", "tolerance", "pass"]


class PipelineError(Exception):
    """Raised when processing or comparison must stop the run."""


class ProcessingRun:
    """Hold one run's config, audit list, checks, and staging/output folders."""

    def __init__(self, cfg: dict) -> None:
        """Store the config and resolve the output and staging folders."""
        self.cfg = cfg
        self.output_dir: Path = resolve_path(cfg, cfg["output_dir"])
        staging = cfg.get("staging_dir") or f"{cfg['output_dir']}_staging"
        self.staging_dir: Path = resolve_path(cfg, staging)
        self.audit: list[dict] = []
        self.checks: list[dict] = []

    def prepare_staging(self) -> Path:
        """Create an empty staging folder, discarding leftovers from earlier runs."""
        shutil.rmtree(self.staging_dir, ignore_errors=True)
        self.staging_dir.mkdir(parents=True)
        return self.staging_dir

    def log_step(self, source_file: str, operation: str, rule: str,
                 rows_before: int | None = None, rows_after: int | None = None) -> None:
        """Append one audit record; the step number is assigned automatically."""
        self.audit.append({"step": len(self.audit) + 1, "source_file": source_file,
                           "operation": operation, "rule": rule,
                           "rows_before": rows_before, "rows_after": rows_after})

    def add_check(self, check: str, expected, actual,
                  tolerance: float = 0.0, passed: bool | None = None) -> bool:
        """Record one validation check; numbers use the tolerance, others compare exactly."""
        if passed is None:
            numeric = (int, float)
            if (isinstance(expected, numeric) and isinstance(actual, numeric)
                    and not isinstance(expected, bool) and not isinstance(actual, bool)):
                passed = abs(expected - actual) <= tolerance
            else:
                passed = expected == actual
        self.checks.append({"check": check, "expected": expected, "actual": actual,
                            "tolerance": tolerance, "pass": bool(passed)})
        return bool(passed)

    @property
    def all_passed(self) -> bool:
        """Return True when every recorded check passed."""
        return all(item["pass"] for item in self.checks)

    def write_reports(self) -> None:
        """Write audit_log.csv and validation.csv into the staging folder."""
        pd.DataFrame(self.audit, columns=AUDIT_COLUMNS).to_csv(
            self.staging_dir / "audit_log.csv", index=False)
        pd.DataFrame(self.checks, columns=CHECK_COLUMNS).to_csv(
            self.staging_dir / "validation.csv", index=False)

    def publish(self) -> None:
        """Move staged files into the output folder, only if every check passed."""
        if not self.all_passed:
            raise PipelineError("Refusing to publish: at least one check failed.")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        for item in sorted(self.staging_dir.iterdir()):
            if item.is_file():
                os.replace(item, self.output_dir / item.name)
        shutil.rmtree(self.staging_dir, ignore_errors=True)

    def save_failure_report(self, reason: str) -> Path:
        """Save failed_validation_report.csv and discard staging; final files stay untouched."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        rows = self.checks + [{"check": "run completed", "expected": True,
                               "actual": reason, "tolerance": 0.0, "pass": False}]
        report = self.output_dir / "failed_validation_report.csv"
        pd.DataFrame(rows, columns=CHECK_COLUMNS).to_csv(report, index=False)
        shutil.rmtree(self.staging_dir, ignore_errors=True)
        return report


