"""Validation, quarantine, de-duplication and conflict checks for recovered records."""
from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from src.common import ConflictingKeyError

VALID_CONTINENTS = {"Africa", "Americas", "Asia", "Europe", "Oceania"}
VALID_YEARS = set(range(1952, 2008, 5))
SIX_FIELDS = ["country", "continent", "year", "lifeExp", "pop", "gdpPercap"]


@dataclass
class ValidationResult:
    """Holds valid rows, quarantine records, and a counts dict."""
    valid_df: pd.DataFrame
    quarantine_records: list[dict]
    counts: dict


def _check_whole_number(val_str: str) -> bool:
    """Return True for a finite value with no fractional part."""
    try:
        number = float(val_str)
        return math.isfinite(number) and number.is_integer()
    except (ValueError, TypeError):
        return False


def _reject_reason(country, continent, year_s, life_s, pop_s, gdp_s,
                   allowed_continents, allowed_years):
    """Return the first rule a record breaks, or None when the record is valid."""
    if not country:
        return "Country cannot be empty"
    if continent not in allowed_continents:
        return f"Continent '{continent}' is not in the allowed list"
    if not _check_whole_number(year_s) or int(float(year_s)) not in allowed_years:
        return f"Year '{year_s}' is not a whole number in the allowed years"
    try:
        life = float(life_s)
    except ValueError:
        return f"lifeExp '{life_s}' cannot be parsed as a number"
    if not (math.isfinite(life) and 0 < life <= 120):
        return f"lifeExp '{life_s}' must be finite and between 0 and 120"
    if not _check_whole_number(pop_s) or float(pop_s) <= 0:
        return f"pop '{pop_s}' must be a finite positive whole number"
    try:
        gdp = float(gdp_s)
    except ValueError:
        return f"gdpPercap '{gdp_s}' cannot be parsed as a number"
    if not (math.isfinite(gdp) and gdp > 0):
        return f"gdpPercap '{gdp_s}' must be finite and positive"
    return None


def validate_records(raw_df: pd.DataFrame, source_file: str,
                     rules: dict | None = None) -> ValidationResult:
    """Validate string records; convert valid ones; send the rest to quarantine.

    rules may hold 'allowed_continents' and 'allowed_years' (the config keys).
    Missing keys fall back to the built-in defaults.
    """
    rules = rules or {}
    allowed_continents = set(rules.get("allowed_continents", VALID_CONTINENTS))
    allowed_years = set(rules.get("allowed_years", VALID_YEARS))
    valid_rows, quarantine = [], []
    for _, row in raw_df.iterrows():
        original = {col: str(row.get(col, "")) for col in SIX_FIELDS}
        cleaned = {col: value.strip() for col, value in original.items()}
        reason = _reject_reason(cleaned["country"], cleaned["continent"], cleaned["year"],
                                cleaned["lifeExp"], cleaned["pop"], cleaned["gdpPercap"],
                                allowed_continents, allowed_years)
        if reason:
            quarantine.append({"source_file": source_file,
                               "source_record": row.get("source_record"),
                               "reason": reason, **original})
        else:
            valid_rows.append({"source_record": row.get("source_record"),
                               "country": cleaned["country"],
                               "continent": cleaned["continent"],
                               "year": int(float(cleaned["year"])),
                               "lifeExp": float(cleaned["lifeExp"]),
                               "pop": int(float(cleaned["pop"])),
                               "gdpPercap": float(cleaned["gdpPercap"])})
    valid_df = pd.DataFrame(valid_rows, columns=["source_record"] + SIX_FIELDS)
    return ValidationResult(valid_df, quarantine,
                            {"valid": len(valid_rows), "rejected": len(quarantine)})


def remove_exact_duplicates(valid_df: pd.DataFrame, source_file: str):
    """Remove exact 6-field duplicates; log every dropped copy. Returns (df, log)."""
    seen: dict = {}
    kept, log = [], []
    for _, row in valid_df.iterrows():
        key = tuple(row[col] for col in SIX_FIELDS)
        if key in seen:
            log.append({"source_file": source_file,
                        "source_record": row["source_record"],
                        "country": row["country"], "year": row["year"],
                        "duplicate_of_source_record": seen[key]})
        else:
            seen[key] = row["source_record"]
            kept.append(row)
    deduped = pd.DataFrame(kept, columns=valid_df.columns).reset_index(drop=True)
    for col in valid_df.columns:
        deduped[col] = deduped[col].astype(valid_df[col].dtype)
    return deduped, log


def check_conflicting_keys(valid_df: pd.DataFrame) -> None:
    """Raise ConflictingKeyError if one (country, year) has different values."""
    if valid_df.empty:
        return
    distinct = valid_df.drop_duplicates(subset=SIX_FIELDS)
    if distinct.duplicated(subset=["country", "year"]).any():
        raise ConflictingKeyError(
            "Conflicting values found for the same country and year.")