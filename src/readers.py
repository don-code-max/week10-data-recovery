import os
import json
import pandas as pd
from src.common import FileLevelError

CANONICAL_COLUMNS = ['country', 'continent', 'year', 'lifeExp', 'pop', 'gdpPercap']

def _map_and_normalize(df_raw: pd.DataFrame, source_to_canonical: dict) -> pd.DataFrame:
    # Check if we have all necessary mappings[cite: 1]
    mapped_sources = {s_col: c_col for s_col, c_col in source_to_canonical.items()}
    missing = [col for col in CANONICAL_COLUMNS if col not in mapped_sources.values()]
    if missing:
        raise FileLevelError(f"Missing required canonical column mappings: {missing}")

    df = df_raw.rename(columns=source_to_canonical)
    
    for col in CANONICAL_COLUMNS:
        if col not in df.columns:
            raise FileLevelError(f"Missing required column in file: {col}")

    res = df[CANONICAL_COLUMNS].copy()
    # 1-based integer counting data records only[cite: 1]
    res.insert(0, 'source_record', range(1, len(res) + 1))
    
    # Keep as original strings, blanks remain empty strings[cite: 1]
    for col in CANONICAL_COLUMNS:
        res[col] = res[col].apply(lambda v: "" if pd.isna(v) or v is None else str(v))
    return res

def read_csv_records(path: str, settings: dict) -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileLevelError(f"File not found: {path}")
    
    # Fallback logic for separator[cite: 5]
    sep_char = settings.get("sep", settings.get("separator", ","))
    
    df = pd.read_csv(
        path,
        encoding=settings.get("encoding", "cp1252"),
        comment=settings.get("comment", "#"),
        sep=sep_char,
        dtype=str,
        keep_default_na=False
    )
    if "export_note" in df.columns:
        df = df.drop(columns=["export_note"])
        
    return _map_and_normalize(df, settings.get("source_to_canonical", {}))

def read_excel_records(path: str, settings: dict) -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileLevelError(f"File not found: {path}")
        
    # Fallback logic for sheet[cite: 5]
    target_sheet = settings.get("sheet_name", settings.get("sheet", "observations"))
    
    df = pd.read_excel(
        path,
        sheet_name=target_sheet,
        engine=settings.get("engine", "openpyxl"),
        dtype=str, # Keep original values[cite: 1]
        keep_default_na=False
    )
    return _map_and_normalize(df, settings.get("source_to_canonical", {}))

def read_json_records(path: str, settings: dict) -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileLevelError(f"File not found: {path}")
        
    with open(path, "r", encoding=settings.get("encoding", "utf-8")) as f:
        data = json.load(f)
        
    records = data.get("records", [])
    flat_records = []
    for item in records:
        row = {}
        # Flatten identity and measures safely[cite: 1]
        for k, v in item.get("identity", {}).items():
            row[f"identity.{k}"] = v
        for k, v in item.get("measures", {}).items():
            row[f"measures.{k}"] = v
        for k, v in item.items():
            if k not in ["identity", "measures"]:
                row[k] = v
        flat_records.append(row)
        
    df = pd.DataFrame(flat_records)
    return _map_and_normalize(df, settings.get("source_to_canonical", {}))

def read_parquet_records(path: str, settings: dict) -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileLevelError(f"File not found: {path}")
        
    df = pd.read_parquet(path, engine=settings.get("engine", "pyarrow"))
    return _map_and_normalize(df, settings.get("source_to_canonical", {}))

def read_records(path: str, settings: dict) -> pd.DataFrame:
    fmt = settings.get("format", "").lower()
    readers = {
        "csv": read_csv_records,
        "excel": read_excel_records,
        "xlsx": read_excel_records, # Fix 1: Restore xlsx fallback[cite: 5]
        "json": read_json_records,
        "parquet": read_parquet_records
    }
    if fmt not in readers:
        raise FileLevelError(f"Unsupported format: {fmt}")
    return readers[fmt](path, settings)