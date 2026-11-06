"""Section 3 stage: read, validate, quarantine, de-duplicate and reconcile the inputs."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.common import ConflictingKeyError
from src.compare import compare_tables
from src.config import input_path
from src.readers import read_records
from src.run import PipelineError, ProcessingRun
from src.validation import (check_conflicting_keys, remove_exact_duplicates,
                            validate_records)

CANONICAL_COLUMNS = ["country", "continent", "year", "lifeExp", "pop", "gdpPercap"]
QUARANTINE_COLUMNS = ["source_file", "source_record", "reason"] + CANONICAL_COLUMNS
DUPLICATE_COLUMNS = ["source_file", "source_record", "country", "year",
                     "duplicate_of_source_record"]
EXPECTED_QUARANTINED = 24   # from the handout, all four files together
EXPECTED_DUPLICATES = 8     # from the handout, all four files together


def stage_recover_inputs(run: ProcessingRun) -> None:
    """Recover every configured input, reconcile them, and store run.canonical."""
    cfg = run.cfg
    rules = {key: cfg[key] for key in ("allowed_continents", "allowed_years") if key in cfg}
    tables: dict[str, pd.DataFrame] = {}
    quarantine: list[dict] = []
    duplicates: list[dict] = []

    for entry in cfg["inputs"]:
        name = entry["name"]
        source_file = Path(entry["path"]).name
        raw = read_records(str(input_path(cfg, entry)), entry)  # FileLevelError stops the run
        run.log_step(source_file, "read", f"{entry['format']} reader", None, len(raw))

        result = validate_records(raw, source_file, rules)
        quarantine.extend(result.quarantine_records)
        run.log_step(source_file, "validate", "quarantine invalid records",
                     len(raw), result.counts["valid"])
        run.add_check(f"{name}: rows read = valid + quarantined",
                      len(raw), result.counts["valid"] + result.counts["rejected"])

        deduped, dup_log = remove_exact_duplicates(result.valid_df, source_file)
        duplicates.extend(dup_log)
        run.log_step(source_file, "deduplicate", "drop exact 6-field duplicates",
                     len(result.valid_df), len(deduped))

        try:
            check_conflicting_keys(deduped)
        except ConflictingKeyError:
            run.add_check(f"{name}: no conflicting country/year keys", True, False)
            raise
        run.add_check(f"{name}: no conflicting country/year keys", True, True)
        tables[name] = deduped

    run.add_check("total quarantined records", EXPECTED_QUARANTINED, len(quarantine))
    run.add_check("total exact duplicates", EXPECTED_DUPLICATES, len(duplicates))

    differences = compare_tables(tables)
    run.add_check("recovered tables agree", 0, len(differences))
    if differences:
        raise PipelineError("Recovered tables do not agree: " + "; ".join(differences))

    pd.DataFrame(quarantine, columns=QUARANTINE_COLUMNS).to_csv(
        run.staging_dir / "quarantine.csv", index=False)
    pd.DataFrame(duplicates, columns=DUPLICATE_COLUMNS).to_csv(
        run.staging_dir / "duplicate_log.csv", index=False)

    first = next(iter(tables.values()))
    run.canonical = (first[CANONICAL_COLUMNS].sort_values(["country", "year"])
                     .reset_index(drop=True))