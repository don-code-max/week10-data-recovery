import json
import os

import pandas as pd

from src.common import FileLevelError

CANONICAL_COLUMNS = ['country', 'continent', 'year', 'lifeExp', 'pop', 'gdpPercap']


def _map_and_normalize(df_raw: pd.DataFrame, source_to_canonical: dict) -> pd.DataFrame:
    """Rename source columns to canonical names; keep every value as original text."""
    missing = [c for c in CANONICAL_COLUMNS if c not in source_to_canonical.values()]
    if missing:
        raise FileLevelError(f"Missing required canonical column mappings: {missing}")
    df = df_raw.rename(columns=source_to_canonical)
    for col in CANONICAL_COLUMNS:
        if col not in df.columns:
            raise FileLevelError(f"Missing required column in file: {col}")
    res = df[CANONICAL_COLUMNS].copy()
    res.insert(0, 'source_record', range(1, len(res) + 1))
    for col in CANONICAL_COLUMNS:
        res[col] = res[col].apply(lambda v: "" if v is None or pd.isna(v) else str(v))
    return res


def read_csv_records(path: str, settings: dict) -> pd.DataFrame:
    """Read the CSV (cp1252, ';' separator, '#' comment lines) as text; drop export_note."""
    if not os.path.exists(path):
        raise FileLevelError(f"File not found: {path}")
    df = pd.read_csv(
        path,
        encoding=settings.get("encoding", "cp1252"),
        comment=settings.get("comment", "#"),
        sep=settings.get("sep", settings.get("separator", ",")),
        dtype=str,
        keep_default_na=False,
    )
    if "export_note" in df.columns:
        df = df.drop(columns=["export_note"])
    return _map_and_normalize(df, settings.get("source_to_canonical", {}))


def read_excel_records(path: str, settings: dict) -> pd.DataFrame:
    """Read only the observations sheet, every cell as text."""
    if not os.path.exists(path):
        raise FileLevelError(f"File not found: {path}")
    df = pd.read_excel(
        path,
        sheet_name=settings.get("sheet_name", settings.get("sheet", "observations")),
        engine=settings.get("engine", "openpyxl"),
        dtype=str,
        keep_default_na=False,
    )
    return _map_and_normalize(df, settings.get("source_to_canonical", {}))


def read_json_records(path: str, settings: dict) -> pd.DataFrame:
    """Read the nested JSON, flattening identity.* and measures.*; ignore outer metadata."""
    if not os.path.exists(path):
        raise FileLevelError(f"File not found: {path}")
    with open(path, "r", encoding=settings.get("encoding", "utf-8")) as f:
        data = json.load(f)
    flat_records = []
    for item in data.get("records", []):
        row = {}
        for k, v in item.get("identity", {}).items():
            row[f"identity.{k}"] = v
        for k, v in item.get("measures", {}).items():
            row[f"measures.{k}"] = v
        for k, v in item.items():
            if k not in ("identity", "measures"):
                row[k] = v
        flat_records.append(row)
    return _map_and_normalize(pd.DataFrame(flat_records), settings.get("source_to_canonical", {}))


def read_parquet_records(path: str, settings: dict) -> pd.DataFrame:
    """Read the Parquet file with pyarrow."""
    if not os.path.exists(path):
        raise FileLevelError(f"File not found: {path}")
    df = pd.read_parquet(path, engine=settings.get("engine", "pyarrow"))
    return _map_and_normalize(df, settings.get("source_to_canonical", {}))


def read_records(path: str, settings: dict) -> pd.DataFrame:
    """Pick a reader by settings['format']; raise FileLevelError for unknown formats."""
    fmt = str(settings.get("format", "")).lower()
    readers = {
        "csv": read_csv_records,
        "excel": read_excel_records,
        "xlsx": read_excel_records,
        "json": read_json_records,
        "parquet": read_parquet_records,
    }
    if fmt not in readers:
        raise FileLevelError(f"Unsupported format: {fmt}")
    return readers[fmt](path, settings)