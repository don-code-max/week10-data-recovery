import math
from dataclasses import dataclass
import pandas as pd
from src.common import ConflictingKeyError

VALID_CONTINENTS = {"Africa", "Americas", "Asia", "Europe", "Oceania"}
VALID_YEARS = set(range(1952, 2012, 5))

@dataclass
class ValidationResult:
    """Holds the valid records, quarantined records, and their aggregate counts."""
    valid_df: pd.DataFrame
    quarantine_records: list[dict]
    counts: dict

def _check_whole_number(val_str: str) -> bool:
    try:
        f = float(val_str)
        return math.isfinite(f) and f.is_integer()
    except (ValueError, TypeError):
        return False

def validate_records(raw_df: pd.DataFrame, source_file: str, rules: dict = None) -> ValidationResult:
    """
    Validates records against domain rules and routes rejects to quarantine.
    """
    rules = rules or {}
    valid_rows = []
    quarantine = []
    
    for _, row in raw_df.iterrows():
        orig_country = str(row.get('country', ''))
        orig_continent = str(row.get('continent', ''))
        orig_year = str(row.get('year', ''))
        orig_lifeExp = str(row.get('lifeExp', ''))
        orig_pop = str(row.get('pop', ''))
        orig_gdpPercap = str(row.get('gdpPercap', ''))
        
        country = orig_country.strip()
        continent = orig_continent.strip()
        year_str = orig_year.strip()
        lifeExp_str = orig_lifeExp.strip()
        pop_str = orig_pop.strip()
        gdpPercap_str = orig_gdpPercap.strip()
        
        reason = None
        
        if not country:
            reason = "Country cannot be empty"
        elif continent not in VALID_CONTINENTS:
            reason = f"Continent '{continent}' is not in the allowed list"
        elif not _check_whole_number(year_str) or int(float(year_str)) not in VALID_YEARS:
            reason = f"Year '{year_str}' is not a valid 5-year interval integer"
        else:
            try:
                life_exp = float(lifeExp_str)
                if not (math.isfinite(life_exp) and 0 < life_exp <= 120):
                    reason = f"lifeExp {life_exp} must be finite and between 0 and 120"
            except ValueError:
                reason = f"lifeExp '{lifeExp_str}' cannot be parsed as a float"
                
            if not reason:
                try:
                    pop_val = float(pop_str)
                    if not (math.isfinite(pop_val) and pop_val.is_integer() and pop_val > 0):
                        reason = f"pop '{pop_val}' must be a finite positive integer"
                except ValueError:
                    reason = f"pop '{pop_str}' cannot be parsed as a number"
                    
            if not reason:
                try:
                    gdp = float(gdpPercap_str)
                    if not (math.isfinite(gdp) and gdp > 0):
                        reason = f"gdpPercap '{gdp}' must be finite and positive"
                except ValueError:
                    reason = f"gdpPercap '{gdpPercap_str}' cannot be parsed as a float"

        if reason:
            quarantine.append({
                "source_file": source_file,
                "source_record": row.get("source_record"),
                "reason": reason,
                "country": orig_country,
                "continent": orig_continent,
                "year": orig_year,
                "lifeExp": orig_lifeExp,
                "pop": orig_pop,
                "gdpPercap": orig_gdpPercap
            })
        else:
            valid_rows.append({
                "source_record": row.get("source_record"),
                "country": country,
                "continent": continent,
                "year": int(float(year_str)),
                "lifeExp": float(lifeExp_str),
                "pop": int(float(pop_str)),
                "gdpPercap": float(gdpPercap_str)
            })

    valid_df = pd.DataFrame(valid_rows)
    return ValidationResult(
        valid_df=valid_df,
        quarantine_records=quarantine,
        counts={"valid": len(valid_rows), "rejected": len(quarantine)}
    )

def remove_exact_duplicates(valid_df: pd.DataFrame, source_file: str) -> tuple[pd.DataFrame, list[dict]]:
    """Removes exact 6-field duplicates and logs every dropped copy."""
    data_cols = ['country', 'continent', 'year', 'lifeExp', 'pop', 'gdpPercap']
    seen = {}
    deduped_rows = []
    duplicate_logs = []
    
    if valid_df.empty:
        return valid_df, duplicate_logs

    for _, row in valid_df.iterrows():
        key = tuple(row[col] for col in data_cols)
        if key in seen:
            duplicate_logs.append({
                "source_file": source_file,
                "source_record": row["source_record"],
                "country": row["country"],
                "year": row["year"],
                "duplicate_of_source_record": seen[key]
            })
        else:
            seen[key] = row["source_record"]
            deduped_rows.append(row)
            
    deduped_df = pd.DataFrame(deduped_rows)
    return deduped_df, duplicate_logs

def check_conflicting_keys(valid_df: pd.DataFrame) -> None:
    """Raises ConflictingKeyError if the same (country, year) has differing metrics."""
    if valid_df.empty:
        return
    six = ["country", "continent", "year", "lifeExp", "pop", "gdpPercap"]
    distinct = valid_df.drop_duplicates(subset=six)
    
    if distinct.duplicated(subset=["country", "year"]).any():
        raise ConflictingKeyError("Conflicting measurement values found for the same country and year.")