"""Step 4/5 stage: export the canonical table in four formats, reload, and compare."""
from __future__ import annotations
import pandas as pd
from src.compare import compare_tables
from src.run import PipelineError, ProcessingRun

COLUMNS = ["country", "continent", "year", "lifeExp", "pop", "gdpPercap"]
KINDS = {"country": "text", "continent": "text", "year": "int",
         "lifeExp": "float", "pop": "int", "gdpPercap": "float"}
FILES = {"csv": "canonical.csv", "xlsx": "canonical.xlsx",
         "json": "canonical.json", "parquet": "canonical.parquet"}

def _kind_ok(series: pd.Series, kind: str) -> bool:
    if kind == "text":
        return pd.api.types.is_string_dtype(series) or series.dtype == object
    if kind == "int":
        return pd.api.types.is_integer_dtype(series)
    return pd.api.types.is_float_dtype(series)

def types_ok(df: pd.DataFrame) -> bool:
    """True when every column has the declared type."""
    return list(df.columns) == COLUMNS and all(_kind_ok(df[c], KINDS[c]) for c in COLUMNS)

def apply_schema(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Apply the declared schema: return (table, notes on conversions that were needed).
    Whole-number columns are only converted when every value is a whole number,
    so a value such as 1.9 raises an error instead of being silently truncated."""
    out = pd.DataFrame(index=df.index)
    notes = []
    for col in COLUMNS:
        before = str(df[col].dtype)
        if KINDS[col] == "text":
            out[col] = df[col].astype(str)
        elif KINDS[col] == "int":
            numbers = pd.to_numeric(df[col], errors="raise")
            if not (numbers == numbers.round()).all():
                raise PipelineError(f"Column {col} has non-whole values: cannot convert to int.")
            out[col] = numbers.astype("int64")
        else:
            out[col] = pd.to_numeric(df[col], errors="raise").astype("float64")
        after = str(out[col].dtype)
        if before != after:
            notes.append(f"{col}: {before} -> {after}")
    return out, notes

def write_exports(df: pd.DataFrame, folder) -> None:
    """Write the four canonical exports: six fields only, no row index."""
    df.to_csv(folder / FILES["csv"], index=False)
    df.to_excel(folder / FILES["xlsx"], sheet_name="observations", index=False)
    df.to_json(folder / FILES["json"], orient="records", force_ascii=False, indent=2)
    df.to_parquet(folder / FILES["parquet"], index=False)

def read_exports(folder) -> dict[str, pd.DataFrame]:
    """Reload the four exports exactly as written (no automatic NA conversion of text)."""
    return {
        "csv": pd.read_csv(folder / FILES["csv"], keep_default_na=False),
        "xlsx": pd.read_excel(folder / FILES["xlsx"], sheet_name="observations", keep_default_na=False),
        "json": pd.read_json(folder / FILES["json"], orient="records", convert_dates=False),
        "parquet": pd.read_parquet(folder / FILES["parquet"])
    }

def stage_exports(run: ProcessingRun) -> None:
    """Export canonical data, reload every format, reapply the schema, and compare."""
    original = run.canonical
    if original is None:
        raise PipelineError("No canonical table: the recovery stage must run first.")
    
    original = original[COLUMNS]
    run.add_check("canonical table has declared types before export", True, types_ok(original))
    run.add_check("canonical row count", 1704, len(original))
    
    write_exports(original, run.staging_dir)
    run.log_step("canonical", "export", "csv, xlsx (sheet observations), json (records), parquet: six fields, no index", len(original), len(original))
    
    for fmt, reloaded in read_exports(run.staging_dir).items():
        raw_types = ", ".join(f"{c}={reloaded[c].dtype}" for c in COLUMNS if c in reloaded)
        run.add_check(f"{fmt}: reloaded columns are the six canonical fields", COLUMNS, list(reloaded.columns))
        
        normalized, notes = apply_schema(reloaded[COLUMNS])
        conversion = "; ".join(notes) if notes else "none needed"
        
        run.log_step(f"canonical.{fmt}", "reload and apply schema",
                     f"reloaded types: {raw_types}. Conversions: {conversion}",
                     len(reloaded), len(normalized))
        run.add_check(f"{fmt}: types correct after normalization", True, types_ok(normalized))
        run.add_check(f"{fmt}: row count matches canonical", len(original), len(normalized))
        differences = compare_tables({"canonical": original, fmt: normalized})
        run.add_check(f"{fmt}: reloaded data matches canonical", 0, len(differences))