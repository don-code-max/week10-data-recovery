from __future__ import annotations

import pandas as pd

from src.run import ProcessingRun
from src.compare import compare_tables

def stage_exports(run: ProcessingRun) -> None:
    """Step 4/5: Reload canonical exports, reapply schema, and compare."""
    original_df = run.canonical
    
    schema = {
        "country": str,
        "continent": str,
        "year": int,
        "lifeExp": float,
        "pop": int,
        "gdpPercap": float
    }
    

    reloaded_dfs = {
        "csv": pd.read_csv(run.staging_dir / "canonical.csv"),
        "xlsx": pd.read_excel(run.staging_dir / "canonical.xlsx"),
        "json": pd.read_json(run.staging_dir / "canonical.json"),
        "parquet": pd.read_parquet(run.staging_dir / "canonical.parquet")
    }
    
  
    for fmt, reloaded_df in reloaded_dfs.items():
        
        normalized_df = reloaded_df.astype(schema)
        
        
        differences = compare_tables({"original": original_df, fmt: normalized_df})
        
  
        run.add_check(
            check=f"reloaded_{fmt}_matches_original", 
            expected=0, 
            actual=len(differences)
        )
        
    
    run.log_step(
        source_file="canonical_exports",
        operation="reload_and_compare",
        rule="reapply schema and compare four formats",
        rows_before=len(original_df),
        rows_after=len(original_df)
    )