import pandas as pd
from typing import Tuple, List, Dict
from src.common import ConflictingKeyError

class ValidationResult:
    def __init__(self, valid_df: pd.DataFrame, quarantine_records: List[Dict]):
        self.valid_df = valid_df
        self.quarantine_records = quarantine_records
        self.counts = {
            "valid": len(valid_df),
            "quarantined": len(quarantine_records)
        }

def validate_records(raw_df: pd.DataFrame, source_file: str, rules: dict = None):
    rules = rules or {}
    """Trims whitespace and validates records before type conversion."""
    valid_rows = []
    quarantine = []
    
    canonical_cols = ["country", "continent", "year", "lifeExp", "pop", "gdpPercap"]
    valid_years = set(rules.get("allowed_years", set(range(1952, 2008, 5))))
    valid_continents = set(rules.get("allowed_continents", {"Africa", "Americas", "Asia", "Europe", "Oceania"}))
    
    for _, row in raw_df.iterrows():
        # Trim surrounding whitespace first
        clean_row = {col: str(row[col]).strip() for col in canonical_cols}
        
        reason = None
        try:
            # 1. Check empty/missing
            if not clean_row["country"]:
                reason = "country is empty"
            elif clean_row["continent"] not in valid_continents:
                reason = "invalid continent"
                
            # 2. Check year
            if not reason:
                y = float(clean_row["year"])
                if not y.is_integer() or int(y) not in valid_years:
                    reason = "invalid year"
                    
            # 3. Check lifeExp
            if not reason:
                le = float(clean_row["lifeExp"])
                if not (0 < le <= 120):
                    reason = "lifeExp out of range"
                    
            # 4. Check pop
            if not reason:
                p = float(clean_row["pop"])
                if not p.is_integer() or p <= 0:
                    reason = "invalid pop"
                    
            # 5. Check gdpPercap
            if not reason:
                gdp = float(clean_row["gdpPercap"])
                if gdp <= 0:
                    reason = "invalid gdpPercap"
                    
        except ValueError:
            reason = "unparseable number or missing required value"
            
        if reason:
            q_row = {
                "source_file": source_file,
                "source_record": row["source_record"],
                "reason": reason
            }
            # Add original untrimmed values to quarantine
            for col in canonical_cols:
                q_row[col] = row[col]
            quarantine.append(q_row)
        else:
            # Type cast passed valid records
            typed_row = {
                "country": clean_row["country"],
                "continent": clean_row["continent"],
                "year": int(float(clean_row["year"])),
                "lifeExp": float(clean_row["lifeExp"]),
                "pop": int(float(clean_row["pop"])),
                "gdpPercap": float(clean_row["gdpPercap"]),
                "source_record": row["source_record"],
                "source_file": source_file
            }
            valid_rows.append(typed_row)
            
    return ValidationResult(pd.DataFrame(valid_rows), quarantine)

def remove_exact_duplicates(valid_df: pd.DataFrame, source_file: str) -> Tuple[pd.DataFrame, List[Dict]]:
    """Removes exact duplicates across all 6 fields and logs them."""
    if valid_df.empty:
        return valid_df, []
        
    subset_cols = ["country", "continent", "year", "lifeExp", "pop", "gdpPercap"]
    duplicates_mask = valid_df.duplicated(subset=subset_cols, keep='first')
    
    unique_df = valid_df[~duplicates_mask].copy()
    duplicate_rows = valid_df[duplicates_mask]
    
    log = []
    # Find original source_record to map duplicate_of_source_record
    for _, dup_row in duplicate_rows.iterrows():
        # Find the kept record
        kept = unique_df[
            (unique_df["country"] == dup_row["country"]) & 
            (unique_df["year"] == dup_row["year"])
        ].iloc[0]
        
        log.append({
            "source_file": source_file,
            "source_record": dup_row["source_record"],
            "country": dup_row["country"],
            "year": dup_row["year"],
            "duplicate_of_source_record": kept["source_record"]
        })
        
    return unique_df, log

def check_conflicting_keys(valid_df: pd.DataFrame) -> None:
    """Raises ConflictingKeyError if the same key has different values."""
    if valid_df.empty:
        return
        
    key_counts = valid_df.groupby(["country", "year"]).size()
    if any(key_counts > 1):
        raise ConflictingKeyError("Found identical (country, year) keys with differing values.")