"""Pipeline runner."""
from __future__ import annotations

import sys
from typing import Callable

from src.run import PipelineError, ProcessingRun

Stage = Callable[[ProcessingRun], None]


def default_stages() -> list[Stage]:
    """Return the processing stages."""
    return []  # teammates add stages here


def run_pipeline(cfg: dict) -> int:
    """Run the pipeline; return 0 on success, 1 on failure."""
    run = ProcessingRun(cfg)
    try:
        run.prepare_staging()
        for stage in default_stages():
            stage(run)
        run.write_reports()
        if not run.checks:
            raise PipelineError("No validation checks were recorded; no stage ran.")
        if not run.all_passed:
            raise PipelineError("One or more validation checks failed.")
        run.publish()
    except Exception as error:
        report = run.save_failure_report(f"{type(error).__name__}: {error}")
        print(f"FAILED: {error}\nReport: {report}", file=sys.stderr)
        return 1
    print(f"Run complete. Outputs in {run.output_dir}")
    return 0