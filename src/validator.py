import numpy as np
import pandas as pd
from typing import Tuple, List, Dict, Any, Set

class ValidationManager:
    """Handles field validation prior to integer conversion, deduplication, and conflict checks."""

    CANONICAL_COLS = ["country", "continent", "year", "lifeExp", "pop", "gdpPercap"]

    def __init__(self, allowed_years: Set[int] = None, allowed_continents: Set[str] = None) -> None:
        self.allowed_years = allowed_years or set(range(1952, 2008, 5))
        self.allowed_continents = allowed_continents

    def validate_dataset(
        self, df: pd.DataFrame, source_file: str
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        quarantine: List[Dict[str, Any]] = []
        valid: List[Dict[str, Any]] = []

        for idx, row in df.iterrows():
            src_rec = int(row.get("source_record", idx + 1))
            
            c_str = str(row.get("country", "") if pd.notna(row.get("country")) else "").strip()
            cont_str = str(row.get("continent", "") if pd.notna(row.get("continent")) else "").strip()
            y_str = str(row.get("year", "") if pd.notna(row.get("year")) else "").strip()
            l_str = str(row.get("lifeExp", "") if pd.notna(row.get("lifeExp")) else "").strip()
            p_str = str(row.get("pop", "") if pd.notna(row.get("pop")) else "").strip()
            g_str = str(row.get("gdpPercap", "") if pd.notna(row.get("gdpPercap")) else "").strip()

            reasons = []

            if not c_str or c_str.lower() == "nan":
                reasons.append("Missing country identifier")
            if not cont_str or cont_str.lower() == "nan":
                reasons.append("Missing continent identifier")

            year_val = None
            try:
                y_flt = float(y_str)
                if not y_flt.is_integer():
                    reasons.append("Fractional year value")
                else:
                    year_val = int(y_flt)
                    if self.allowed_years and year_val not in self.allowed_years:
                        reasons.append("Year out of declared range")
            except (ValueError, TypeError):
                reasons.append("Non-numeric year")

            life_val = None
            try:
                life_val = float(l_str)
                if not np.isfinite(life_val) or life_val < 0:
                    reasons.append("Non-finite or negative lifeExp")
            except (ValueError, TypeError):
                reasons.append("Non-numeric lifeExp")

            pop_val = None
            try:
                p_flt = float(p_str)
                if not p_flt.is_integer() or p_flt < 0:
                    reasons.append("Fractional or negative population")
                else:
                    pop_val = int(p_flt)
            except (ValueError, TypeError):
                reasons.append("Non-numeric population")

            gdp_val = None
            try:
                gdp_val = float(g_str)
                if not np.isfinite(gdp_val) or gdp_val < 0:
                    reasons.append("Non-finite or negative gdpPercap")
            except (ValueError, TypeError):
                reasons.append("Non-numeric gdpPercap")

            if reasons:
                quarantine.append({
                    "source_file": source_file,
                    "source_record": src_rec,
                    "reason": "; ".join(reasons),
                    "country": c_str,
                    "continent": cont_str,
                    "year": y_str,
                    "lifeExp": l_str,
                    "pop": p_str,
                    "gdpPercap": g_str
                })
            else:
                valid.append({
                    "country": c_str,
                    "continent": cont_str,
                    "year": year_val,
                    "lifeExp": life_val,
                    "pop": pop_val,
                    "gdpPercap": gdp_val
                })

        valid_df = pd.DataFrame(valid, columns=self.CANONICAL_COLS)
        quarantine_df = pd.DataFrame(quarantine)

        duplicates: List[Dict[str, Any]] = []
        if not valid_df.empty:
            grouped = valid_df.groupby(["country", "year"])
            for (c, y), group in grouped:
                if len(group.drop_duplicates(subset=self.CANONICAL_COLS)) > 1:
                    raise ValueError(f"Conflicting key found in {source_file} for ({c}, {y})!")

            dup_mask = valid_df.duplicated(subset=self.CANONICAL_COLS, keep="first")
            for _, d_row in valid_df[dup_mask].iterrows():
                duplicates.append({
                    "source_file": source_file,
                    "country": d_row["country"],
                    "year": d_row["year"],
                    "reason": "Exact duplicate valid record"
                })
            valid_df = valid_df.drop_duplicates(subset=self.CANONICAL_COLS, keep="first").reset_index(drop=True)

        return valid_df, quarantine_df, pd.DataFrame(duplicates)
