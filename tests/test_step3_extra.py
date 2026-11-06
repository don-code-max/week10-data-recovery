from src.readers import read_records
from src.validation import validate_records, remove_exact_duplicates, check_conflicting_keys
from src.compare import compare_tables

def run_section3_stage(config: dict, run_logger):
    """The main integration for the pipeline."""
    tables = {}
    all_quarantine = []
    all_duplicates = []
    
    for entry in config.get("inputs", []):
        path = entry["path"] # adjust based on your config structure
        settings = entry["settings"]
        
        # 1. Read
        raw_df = read_records(path, settings)
        
        # 2. Validate
        res = validate_records(raw_df, path)
        all_quarantine.extend(res.quarantine_records)
        
        # 3. Deduplicate
        deduped_df, dup_logs = remove_exact_duplicates(res.valid_df, path)
        all_duplicates.extend(dup_logs)
        
        # 4. Check for conflicts
        check_conflicting_keys(deduped_df)
        
        tables[path] = deduped_df
        
        # (Optional) Log to your run_logger based on team structure
        # run_logger.add_check(f"Read {path}", res.counts)
        
    # 5. Compare
    differences = compare_tables(tables)
    if differences:
        raise ValueError(f"Tables do not reconcile: {differences}")
        
    # 6. Save logs (implement file writes to staging folder as needed)
    return tables