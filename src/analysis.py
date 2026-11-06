from __future__ import annotations

import pandas as pd
import numpy as np

from src.run import ProcessingRun


def stage_analysis(run: ProcessingRun) -> None:
    """Step 4: Perform pandas aggregations and NumPy matrix math."""
    
    df = run.canonical
    initial_rows = len(df)
    
    
    summary_df = df.groupby("continent").agg(
        total_population=("pop", "sum"),
        avg_life_expectancy=("lifeExp", "mean"),
        avg_gdp_per_capita=("gdpPercap", "mean")
    ).reset_index()
    
    
    pop_array = df["pop"].to_numpy(dtype=float)
    gdp_array = df["gdpPercap"].to_numpy(dtype=float)
    total_global_gdp = np.dot(pop_array, gdp_array)
    
    
    expected_pop = df["pop"].sum()
    actual_pop = summary_df["total_population"].sum()
    
    run.add_check(
        check="analysis_population_sum_matches",
        expected=expected_pop,
        actual=actual_pop,
        tolerance=run.cfg.get("tolerance_abs", 1e-8)
    )
    
    
    run.log_step(
        source_file="canonical_data",
        operation="pandas_aggregation_and_numpy_math",
        rule="grouped by continent, calculated global gdp dot product",
        rows_before=initial_rows,
        rows_after=len(summary_df)
    )
    
    
    output_path = run.staging_dir / "analysis_summary.csv"
    summary_df.to_csv(output_path, index=False)
    
    print(f"[Task 4] Analysis complete. Total Global GDP tracked: ${total_global_gdp:,.2f}")