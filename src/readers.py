import pandas as pd
import json
import os
from src.common import FileLevelError

def _enforce_canonical_format(df: pd.DataFrame, settings: dict) -> pd.DataFrame:
    """Maps columns to canonical names, checks requirements, and enforces string types."""
    mapping = settings.get("source_to_canonical", {})
    df = df.rename(columns=mapping)
    
    canonical_cols = ["country", "continent", "year", "lifeExp", "pop", "gdpPercap"]
    for col in canonical_cols:
        if col not in df.columns:
            raise FileLevelError(f"Missing required column: {col}")
            
    for col in canonical_cols:
        # Convert to string safely, don't let None become "None", nulls become ""
        df[col] = df[col].apply(lambda x: "" if pd.isna(x) or x is None else str(x))
        df[col] = df[col].replace("None", "")
        
    return df[canonical_cols + ["source_record"]]

def read_csv_records(path: str, settings: dict) -> pd.DataFrame:
    """Parses CSV keeping original values, drops extra export_note column."""
    if not os.path.exists(path):
        raise FileLevelError(f"Missing file: {path}")
    
    encoding = settings.get("encoding", "cp1252")
    separator = settings.get("sep", settings.get("separator", ","))
    
    # Read manually to accurately count source_record ignoring comments/headers
    records = []
    with open(path, 'r', encoding=encoding) as f:
        header = None
        record_idx = 1
        for line in f:
            line = line.strip('\n')
            if not line or line.startswith("#"):
                continue
            if header is None:
                header = line.split(separator)
                continue
            
            row_data = line.split(separator)
            row_dict = dict(zip(header, row_data))
            row_dict["source_record"] = record_idx
            if "export_note" in row_dict:
                del row_dict["export_note"]
            records.append(row_dict)
            record_idx += 1
            
    df = pd.DataFrame(records)
    return _enforce_canonical_format(df, settings)

def read_excel_records(path: str, settings: dict) -> pd.DataFrame:
    """Parses Excel using openpyxl, reading only the observations sheet."""
    if not os.path.exists(path):
        raise FileLevelError(f"Missing file: {path}")
        
    engine = settings.get("engine", "openpyxl")
    sheet = settings.get("sheet_name", settings.get("sheet", "observations"))
    
    df = pd.read_excel(path, engine=engine, sheet_name=sheet)
    df["source_record"] = range(1, len(df) + 1)
    return _enforce_canonical_format(df, settings)

def read_json_records(path: str, settings: dict) -> pd.DataFrame:
    """Parses JSON flattening identity and measures, ignoring outer metadata."""
    if not os.path.exists(path):
        raise FileLevelError(f"Missing file: {path}")
        
    with open(path, 'r', encoding=settings.get("encoding", "utf-8")) as f:
        data = json.load(f)
        
    raw_records = data.get("records", [])
    flat_records = []
    for i, rec in enumerate(raw_records, start=1):
        flat = {"source_record": i}
        if "identity" in rec:
            flat.update(rec["identity"])
        if "measures" in rec:
            flat.update(rec["measures"])
        flat_records.append(flat)
        
    df = pd.DataFrame(flat_records)
    return _enforce_canonical_format(df, settings)

def read_parquet_records(path: str, settings: dict) -> pd.DataFrame:
    """Parses Parquet using pyarrow."""
    if not os.path.exists(path):
        raise FileLevelError(f"Missing file: {path}")
        
    engine = settings.get("engine", "pyarrow")
    df = pd.read_parquet(path, engine=engine)
    df["source_record"] = range(1, len(df) + 1)
    return _enforce_canonical_format(df, settings)

def read_records(path: str, settings: dict) -> pd.DataFrame:
    """Picks a reader by format; raises FileLevelError for unsupported formats."""
    ext = os.path.splitext(path)[1].lower()
    if ext == '.csv':
        return read_csv_records(path, settings)
    elif ext in ['.xls', '.xlsx', '.excel']:
        return read_excel_records(path, settings)
    elif ext == '.json':
        return read_json_records(path, settings)
    elif ext == '.parquet':
        return read_parquet_records(path, settings)
    else:
        raise FileLevelError(f"Unsupported format: {ext}")
