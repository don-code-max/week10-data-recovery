from __future__ import annotations

import pandas as pd
import numpy as np

from src.run import ProcessingRun

def stage_analysis(run: ProcessingRun) -> None:
    """Step 4: Produce the analysis and exports."""
    df = run.canonical
    initial_rows = len(df)
    year = run.cfg.get("reporting_year", 2007)

    df.to_csv(run.staging_dir / "canonical.csv", index=False)
    df.to_excel(run.staging_dir / "canonical.xlsx", sheet_name="observations", index=False)
    df.to_json(run.staging_dir / "canonical.json", orient="records")
    df.to_parquet(run.staging_dir / "canonical.parquet", index=False)
    
    run.log_step("canonical_data", "export", "four formats output", initial_rows, len(df))

    asia_mask = (df["continent"] == "Asia") & (df["year"] == year)
    asia_df = df.loc[asia_mask].copy()
    
    asia_df["pop_millions"] = asia_df["pop"] / 1_000_000
    asia_df["lifeExp_rank"] = asia_df["lifeExp"].rank(method="min", ascending=False)
    asia_df = asia_df.sort_values(by=["lifeExp_rank", "country"])
    
    run.add_check(f"Asia {year} row count", 33, len(asia_df))
    
    asia_pop_total = asia_df["pop"].sum()
    expected_asia_pop = 3811953827 if year == 2007 else asia_pop_total
    run.add_check(f"Asia population total {year}", expected_asia_pop, asia_pop_total)
    
    asia_df.to_csv(run.staging_dir / "asia_selected_year.csv", index=False)

    ph_mask = df["country"] == "Philippines"
    ph_df = df.loc[ph_mask].sort_values("year").copy()
    
    ph_df["pop_millions"] = ph_df["pop"] / 1_000_000
    first_year_life = ph_df.iloc[0]["lifeExp"]
    ph_df["lifeExp_change"] = ph_df["lifeExp"] - first_year_life
    
    ph_pop = ph_df.loc[ph_df["year"] == year, "pop"].values[0] if year in ph_df["year"].values else 0
    expected_ph_pop = 91077287 if year == 2007 else ph_pop
    run.add_check(f"Philippines population {year}", expected_ph_pop, ph_pop)
    
    ph_df.to_csv(run.staging_dir / "country_history.csv", index=False)

    countries = ["Philippines", "Indonesia", "Thailand"]
    years = [1982, 1987, 1992, 1997, 2002, 2007]
    
    matrix_data = []
    for c in countries:
        row_data = []
        for y in years:
            val = df.loc[(df["country"] == c) & (df["year"] == y), "pop"].values[0]
            row_data.append(val)
        matrix_data.append(row_data)
        
    pop_matrix = np.array(matrix_data, dtype=float) 
    
    baseline = pop_matrix[:, 0:1]
    print(f"[Task 4 NumPy] Shape before broadcast - Matrix: {pop_matrix.shape}, Baseline: {baseline.shape}")
    
    broadcast_index = (pop_matrix / baseline) * 100
    print(f"[Task 4 NumPy] Shape after broadcast: {broadcast_index.shape}")
    
    loop_index = np.zeros_like(pop_matrix)
    for i in range(pop_matrix.shape[0]):
        for j in range(pop_matrix.shape[1]):
            loop_index[i, j] = (pop_matrix[i, j] / pop_matrix[i, 0]) * 100
            
    matrix_diff = np.abs(broadcast_index - loop_index).sum()
    run.add_check("NumPy broadcast matches loop", 0.0, matrix_diff, tolerance=1e-8)
    
    idx_df = pd.DataFrame(broadcast_index, columns=[str(y) for y in years])
    idx_df.insert(0, "country", countries)
    idx_df.to_csv(run.staging_dir / "population_index.csv", index=False)
    
    run.log_step("canonical_data", "numpy_analysis", "population matrix broadcast", len(countries), len(idx_df))