"""Step 4 stage: pandas analysis tables and the NumPy population index."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.run import PipelineError, ProcessingRun

ATOL = 1e-8
INDEX_COUNTRIES = ["Philippines", "Indonesia", "Thailand"]
INDEX_YEARS = [1982, 1987, 1992, 1997, 2002, 2007]
EXPECTED_ASIA_2007_POP = 3_811_953_827
EXPECTED_PH_2007_POP = 91_077_287

def build_asia_selected_year(df: pd.DataFrame, year: int) -> pd.DataFrame:
    """Asia rows for one year (selected with .loc), with millions and life-expectancy rank."""
    asia = df.loc[(df["continent"] == "Asia") & (df["year"] == year)].copy()
    asia["pop_millions"] = asia["pop"] / 1_000_000
    asia["lifeExp_rank"] = asia["lifeExp"].rank(method="min", ascending=False).astype(int)
    return asia.sort_values(["lifeExp_rank", "country"]).reset_index(drop=True)

def build_country_history(df: pd.DataFrame, country: str = "Philippines") -> pd.DataFrame:
    """All observations for one country by year, with millions and change since first year."""
    hist = df.loc[df["country"] == country].sort_values("year").copy()
    hist["pop_millions"] = hist["pop"] / 1_000_000
    hist["lifeExp_change"] = hist["lifeExp"] - hist["lifeExp"].iloc[0]
    return hist.reset_index(drop=True)

def population_matrix(df: pd.DataFrame) -> np.ndarray:
    """3 x 6 float matrix: rows INDEX_COUNTRIES, columns INDEX_YEARS."""
    wide = (df.loc[df["country"].isin(INDEX_COUNTRIES) & df["year"].isin(INDEX_YEARS)]
            .pivot(index="country", columns="year", values="pop")
            .reindex(index=INDEX_COUNTRIES, columns=INDEX_YEARS))
    if wide.isna().any().any():
        raise PipelineError("Population matrix has missing country/year values.")
    return wide.to_numpy(dtype=float)

def index_by_broadcast(matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return (baseline column, index matrix) where each row's first year = 100."""
    baseline = matrix[:, [0]] # shape (3, 1)
    return baseline, matrix / baseline * 100.0 # (3, 6) / (3, 1) -> (3, 6)

def index_by_loop(matrix: np.ndarray) -> np.ndarray:
    """Independent loop calculation of the same index, used to verify the broadcast."""
    result = np.zeros(matrix.shape)
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            result[i, j] = matrix[i, j] / matrix[i, 0] * 100.0
    return result

def stage_analysis(run: ProcessingRun) -> None:
    """Build the three analysis tables, write them to staging, and record checks."""
    df = run.canonical
    if df is None:
        raise PipelineError("No canonical table: the recovery stage must run first.")
    
    year = int(run.cfg["reporting_year"])

    # pandas: Asia in the configured year
    asia = build_asia_selected_year(df, year)
    asia.to_csv(run.staging_dir / "asia_selected_year.csv", index=False)
    run.log_step("canonical", "select Asia and reporting year (.loc), rank, sort",
                 f"continent == Asia, year == {year}, rank method min, descending lifeExp",
                 len(df), len(asia))
    
    # Independent total: NumPy Boolean selection on raw arrays, not the pandas table.
    pops = df["pop"].to_numpy(dtype=np.int64)
    in_selection = (df["continent"].to_numpy() == "Asia") & (df["year"].to_numpy() == year)
    numpy_total = int(pops[in_selection].sum())

    run.add_check("asia selected-year population: pandas table vs NumPy Boolean selection",
                  int(asia["pop"].sum()), numpy_total)
    run.add_check("asia selected-year ranks start at 1", 1, int(asia["lifeExp_rank"].min()))

    if year == 2007:
        run.add_check("asia 2007 row count", 33, len(asia))
        run.add_check("asia 2007 population", EXPECTED_ASIA_2007_POP, numpy_total)

    # pandas: Philippines history
    history = build_country_history(df, "Philippines")
    history.to_csv(run.staging_dir / "country_history.csv", index=False)
    run.log_step("canonical", "select Philippines history, add millions and change",
                 "country == Philippines, sorted by year", len(df), len(history))
    run.add_check("philippines history rows", 12, len(history))
    run.add_check("philippines first life-expectancy change is 0", 0.0,
                  float(history["lifeExp_change"].iloc[0]), ATOL)

    ph_2007 = df.loc[(df["country"] == "Philippines") & (df["year"] == 2007), "pop"]
    run.add_check("philippines 2007 population", EXPECTED_PH_2007_POP, int(ph_2007.iloc[0]))

    # NumPy: 3x6 population index
    matrix = population_matrix(df)
    baseline, index = index_by_broadcast(matrix)
    run.log_step("canonical", "build 3x6 population matrix",
                 f"matrix shape {matrix.shape}", len(df), matrix.shape[0])
    run.log_step("population matrix", "broadcast baseline",
                 f"shapes: matrix {matrix.shape} / baseline {baseline.shape} -> index {index.shape}",
                 matrix.shape[0], index.shape[0])
    run.add_check("population matrix shape", (3, 6), tuple(matrix.shape))
    run.add_check("baseline shape before broadcasting", (3, 1), tuple(baseline.shape))
    run.add_check("index shape after broadcasting", (3, 6), tuple(index.shape))
    run.add_check("1982 baseline column equals 100", True,
                  bool(np.allclose(index[:, 0], 100.0, atol=ATOL, rtol=0.0)))
    run.add_check("broadcast index equals independent loop", True,
                  bool(np.allclose(index, index_by_loop(matrix), atol=ATOL, rtol=0.0)))

    grew = index[:, -1] > 100.0
    # Boolean selection: countries that grew
    run.add_check("Boolean selection: countries with 2007 index above 100", 3, int(grew.sum()))
    run.add_check("Boolean aggregation: mean 2007 index of those countries is above 100",
                  True, bool(index[grew, -1].mean() > 100.0))

    table = pd.DataFrame(index, columns=[str(y) for y in INDEX_YEARS])
    table.insert(0, "country", INDEX_COUNTRIES)
    table.to_csv(run.staging_dir / "population_index.csv", index=False)

    run.analysis = {"asia_selected_year": asia, "country_history": history,
                    "population_matrix": matrix, "population_index": table}