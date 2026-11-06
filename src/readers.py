import os
import json
import pandas as pd
import openpyxl
from src.common import FileLevelError

CANONICAL_COLUMNS = ['country', 'continent', 'year', 'lifeExp', 'pop', 'gdpPercap']

def _map_and_normalize(df_raw: pd.DataFrame, source_to_canonical: dict) -> pd.DataFrame:
    # 1. Check required canonical columns in mapping
    mapped_sources = {s_col: c_col for s_col, c_col in source_to_canonical.items()}
    missing = [col for col in CANONICAL_COLUMNS if col not in mapped_sources.values()]
    if missing:
        raise FileLevelError(f"Missing required canonical column mappings: {missing}")

    # 2. Rename columns
    df = df_raw.rename(columns=source_to_canonical)
    
    # 3. Verify all canonical columns exist in the DataFrame
    for col in CANONICAL_COLUMNS:
        if col not in df.columns:
            raise FileLevelError(f"Missing required column in file: {col}")

    # 4. Retain canonical order and add source_record (1-based index)
    res = df[CANONICAL_COLUMNS].copy()
    res.insert(0, 'source_record', range(1, len(res) + 1))
    
    # 5. Keep all canonical data values as original strings without trimming
    for col in CANONICAL_COLUMNS:
        res[col] = res[col].apply(lambda v: "" if pd.isna(v) or v is None else str(v))
    return res

def read_csv_records(path: str, settings: dict) -> pd.DataFrame:
    """Reads CSV with encoding, comment character, and extra columns stripped."""
    if not os.path.exists(path):
        raise FileLevelError(f"File not found: {path}")
    
    encoding = settings.get("encoding", "cp1252")
    comment_char = settings.get("comment", "#")
    sep = settings.get("separator", ",")
    
    # Read keeping original string values, preserving blanks
    df = pd.read_csv(
        path,
        encoding=encoding,
        comment=comment_char,
        sep=sep,
        dtype=str,
        keep_default_na=False
    )
    if "export_note" in df.columns:
        df = df.drop(columns=["export_note"])
        
    return _map_and_normalize(df, settings.get("source_to_canonical", {}))

def read_excel_records(path: str, settings: dict) -> pd.DataFrame:
    """Reads Excel records from the target sheet, bypassing notes and readmes."""
    if not os.path.exists(path):
        raise FileLevelError(f"File not found: {path}")
        
    sheet_name = settings.get("sheet", "observations")
    engine = settings.get("engine", "openpyxl")
    
    df = pd.read_excel(
        path,
        sheet_name=sheet_name,
        engine=engine,
        dtype=str,
        keep_default_na=False
    )
    return _map_and_normalize(df, settings.get("source_to_canonical", {}))

def read_json_records(path: str, settings: dict) -> pd.DataFrame:
    """Flattens nested identity and measures fields from JSON records safely."""
    if not os.path.exists(path):
        raise FileLevelError(f"File not found: {path}")
        
    encoding = settings.get("encoding", "utf-8")
    with open(path, "r", encoding=encoding) as f:
        data = json.load(f)
        
    records = data.get("records", [])
    flat_records = []
    for item in records:
        row = {}
        identity = item.get("identity", {})
        measures = item.get("measures", {})
        
        # Flatten identity.* and measures.*
        for k, v in identity.items():
            row[f"identity.{k}"] = "" if v is None else str(v)
        for k, v in measures.items():
            row[f"measures.{k}"] = "" if v is None else str(v)
        for k, v in item.items():
            if k not in ["identity", "measures"]:
                row[k] = "" if v is None else str(v)
        flat_records.append(row)
        
    df = pd.DataFrame(flat_records)
    return _map_and_normalize(df, settings.get("source_to_canonical", {}))

def read_parquet_records(path: str, settings: dict) -> pd.DataFrame:
    """Reads pyarrow Parquet tables ensuring records remain strings."""
    if not os.path.exists(path):
        raise FileLevelError(f"File not found: {path}")
        
    df = pd.read_parquet(path, engine=settings.get("engine", "pyarrow"))
    for c in df.columns:
        df[c] = df[c].apply(lambda v: "" if pd.isna(v) or v is None else str(v))
    return _map_and_normalize(df, settings.get("source_to_canonical", {}))

def read_records(path: str, settings: dict) -> pd.DataFrame:
    """Selects reader by format; raises FileLevelError if format is unsupported."""
    fmt = settings.get("format", "").lower()
    readers = {
        "csv": read_csv_records,
        "excel": read_excel_records,
        "json": read_json_records,
        "parquet": read_parquet_records
    }
    if fmt not in readers:
        raise FileLevelError(f"Unsupported format: {fmt}")
    return readers[fmt](path, settings)
