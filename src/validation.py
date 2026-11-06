import math
from dataclasses import dataclass
import pandas as pd
from src.common import ConflictingKeyError

VALID_CONTINENTS = {"Africa", "Americas", "Asia", "Europe", "Oceania"}
VALID_YEARS = set(range(1952, 2012, 5))

@dataclass
class ValidationResult:
    valid_df: pd.DataFrame
    quarantine_records: list[dict]
    valid_count: int
    rejected_count: int

def _check_whole_number(val_str: str) -> bool:
    """Return True if the text is a finite number with no fractional part."""
    try:
        f = float(val_str)
        return math.isfinite(f) and f.is_integer()
    except (ValueError, TypeError):
        return False

def validate_records(raw_df: pd.DataFrame, source_file: str, rules: dict = None) -> ValidationResult:
    """Validates records against domain rules and routes rejects to quarantine."""
    rules = rules or {}
    valid_years = set(rules.get("allowed_years", VALID_YEARS))
    valid_continents = set(rules.get("allowed_continents", VALID_CONTINENTS))
    
    valid_rows = []
    quarantine = []
    
    for _, row in raw_df.iterrows():
        orig_country = str(row['country'])
        orig_continent = str(row['continent'])
        orig_year = str(row['year'])
        orig_lifeExp = str(row['lifeExp'])
        orig_pop = str(row['pop'])
        orig_gdpPercap = str(row['gdpPercap'])
        
        country = orig_country.strip()
        continent = orig_continent.strip()
        year_str = orig_year.strip()
        lifeExp_str = orig_lifeExp.strip()
        pop_str = orig_pop.strip()
        gdpPercap_str = orig_gdpPercap.strip()
        
        reason = None
        if not country:
            reason = "Country is empty"
        elif continent not in valid_continents:
            reason = f"Continent '{continent}' invalid"
        elif not _check_whole_number(year_str) or int(float(year_str)) not in valid_years:
            reason = f"Year '{year_str}' is invalid or not in expected intervals"
        else:
            try:
                life_exp = float(lifeExp_str)
                if not (math.isfinite(life_exp) and 0 < life_exp <= 120):
                    reason = f"lifeExp {life_exp} is out of realistic range (0-120]"
            except ValueError:
                reason = f"lifeExp '{lifeExp_str}' cannot be parsed as a float"
                
            if not reason:
                try:
                    pop_val = float(pop_str)
                    if not (math.isfinite(pop_val) and pop_val.is_integer() and pop_val > 0):
                        reason = f"pop {pop_val} must be a positive integer"
                except ValueError:
                    reason = f"pop '{pop_str}' cannot be parsed as an integer"
                    
            if not reason:
                try:
                    gdp = float(gdpPercap_str)
                    if not (math.isfinite(gdp) and gdp > 0):
                        reason = f"gdpPercap {gdp} must be a positive number"
                except ValueError:
                    reason = f"gdpPercap '{gdpPercap_str}' cannot be parsed as a float"

        if reason:
            quarantine.append({
                "source_file": source_file, 
                "source_record": row["source_record"], 
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
                "source_record": row["source_record"], 
                "country": country, 
                "continent": continent,
                "year": int(float(year_str)), 
                "lifeExp": float(lifeExp_str),
                "pop": int(float(pop_str)), 
                "gdpPercap": float(gdpPercap_str)
            })

    return ValidationResult(pd.DataFrame(valid_rows), quarantine, len(valid_rows), len(quarantine))

def remove_exact_duplicates(valid_df: pd.DataFrame, source_file: str) -> tuple[pd.DataFrame, list[dict]]:
    data_cols = ['country', 'continent', 'year', 'lifeExp', 'pop', 'gdpPercap']
    seen = {}
    deduped_rows = []
    duplicate_logs = []
    
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
            
    return pd.DataFrame(deduped_rows) if deduped_rows else pd.DataFrame(columns=valid_df.columns), duplicate_logs

def check_conflicting_keys(valid_df: pd.DataFrame) -> None:
    seen_keys = {}
    for _, row in valid_df.iterrows():
        key = (row["country"], row["year"])
        metrics = (row["continent"], row["lifeExp"], row["pop"], row["gdpPercap"])
        if key in seen_keys and seen_keys[key] != metrics:
            raise ConflictingKeyError(f"Conflicting values for {key}")
        seen_keys[key] = metrics
