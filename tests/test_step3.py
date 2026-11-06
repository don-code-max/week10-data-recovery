import os
import pandas as pd
from src.readers import read_records
from src.validation import validate_records, remove_exact_duplicates, check_conflicting_keys
from src.compare import compare_tables

def _resolve_path(cfg: dict, entry: dict) -> str:
    """Locally resolves the file path to avoid missing utils dependencies."""
    input_dir = cfg.get("input_dir", "data")
    filename = entry.get("path", entry.get("file", ""))
    return os.path.join(input_dir, filename)

def run_section3_stage(cfg: dict, run):
    """Pipeline hook for section 3[cite: 1, 4]."""
    tables = {}
    all_quarantine = []
    all_duplicates = []
    
    rules = cfg.get("rules", {})
    staging_dir = cfg.get("staging_dir", "staging")
    os.makedirs(staging_dir, exist_ok=True)
    
    for entry in cfg.get("inputs", []):
        path = _resolve_path(cfg, entry)
        settings = entry.get("settings", {})
        
        # 1. Read
        raw_df = read_records(path, settings)
        
        # 2. Validate
        res = validate_records(raw_df, path, rules=rules)
        all_quarantine.extend(res.quarantine_records)
        
        # 3. Deduplicate
        deduped_df, dup_logs = remove_exact_duplicates(res.valid_df, path)
        all_duplicates.extend(dup_logs)
        
        # 4. Check Conflicts
        check_conflicting_keys(deduped_df)
        
        tables[path] = deduped_df
        
        # 5. Log progress via run object[cite: 5]
        if hasattr(run, "add_check"):
            run.add_check(f"Validation for {os.path.basename(path)}", res.counts)
        
    # 6. Compare[cite: 3]
    differences = compare_tables(tables)
    if differences:
        raise ValueError(f"Reconciliation failed. Tables do not agree: {differences}")
        
    if hasattr(run, "log_step"):
        run.log_step("Section 3 Complete: All data files reconciled successfully.")
    
    # 7. Write Quarantine and Duplicate logs[cite: 3]
    pd.DataFrame(all_quarantine).to_csv(os.path.join(staging_dir, "quarantine.csv"), index=False)
    pd.DataFrame(all_duplicates).to_csv(os.path.join(staging_dir, "duplicate_log.csv"), index=False)
    
    return tables

def default_stages():
    """Register the stage for main.py."""
    return [
        ("section3_recovery", run_section3_stage)
    ]