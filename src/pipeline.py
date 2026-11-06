"""Orchestrate one run: stages, reports, and publish-or-fail."""
from __future__ import annotations

import sys
from typing import Callable

from src.recover import stage_recover_inputs
from src.analysis import stage_analysis
from src.exports import stage_exports
from src.run import PipelineError, ProcessingRun

Stage = Callable[[ProcessingRun], None]


def default_stages() -> list[Stage]:
    """Return the ordered processing stages (teammates add theirs here)."""
    return [
        stage_recover_inputs,   # Step 3: read, map, validate, quarantine, dedupe, compare
        stage_analysis,       # Step 4: pandas tables + NumPy matrix
        stage_exports,        # Step 4/5: four exports, reload, compare
    ]


def run_pipeline(cfg: dict) -> int:
    """Run all stages in staging; publish on success, else report failure. Return exit code."""
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
    except Exception as error:  # any failure must give a nonzero exit, never silent success
        report = run.save_failure_report(f"{type(error).__name__}: {error}")
        print(f"FAILED: {error}\nReport: {report}", file=sys.stderr)
        return 1
    print(f"Run complete. Outputs in {run.output_dir}")
    return 0