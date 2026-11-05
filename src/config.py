"""Load, default, and validate the JSON run configuration."""
from __future__ import annotations

import json
from pathlib import Path

REQUIRED_KEYS: set[str] = {"inputs", "output_dir"}
REQUIRED_INPUT_KEYS: set[str] = {"name", "path", "format"}
SUPPORTED_FORMATS: set[str] = {"csv", "xlsx", "json", "parquet"}
DEFAULTS: dict = {
    "reporting_year": 2007,
    "tolerance_abs": 1e-8,
    "tolerance_rel": 0.0,
}


class ConfigError(ValueError):
    """Raised when the configuration is missing, malformed, or incomplete."""


def load_config(path: Path | str) -> dict:
    """Read a JSON config file, apply defaults, validate it, and return a dict."""
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"Config file not found: {path}")
    try:
        with path.open(encoding="utf-8") as stream:
            raw = json.load(stream)
    except json.JSONDecodeError as error:
        raise ConfigError(f"Config is not valid JSON: {error}") from error
    if not isinstance(raw, dict):
        raise ConfigError("Config must be a JSON object.")
    cfg = {**DEFAULTS, **raw}
    cfg["base_dir"] = str(path.resolve().parent)
    validate_config(cfg)
    return cfg


def validate_config(cfg: dict) -> None:
    """Check required keys, input entries, formats, and the reporting year."""
    missing = REQUIRED_KEYS - set(cfg)
    if missing:
        raise ConfigError(f"Missing config keys: {sorted(missing)}")
    if not isinstance(cfg["inputs"], list) or not cfg["inputs"]:
        raise ConfigError("'inputs' must be a non-empty list.")
    seen_names: set[str] = set()
    for entry in cfg["inputs"]:
        if not isinstance(entry, dict):
            raise ConfigError("Each input must be an object.")
        absent = REQUIRED_INPUT_KEYS - set(entry)
        if absent:
            raise ConfigError(f"Input missing keys: {sorted(absent)}")
        if entry["format"] not in SUPPORTED_FORMATS:
            raise ConfigError(f"Unsupported format '{entry['format']}' for {entry['name']}.")
        if entry["name"] in seen_names:
            raise ConfigError(f"Duplicate input name: {entry['name']}")
        seen_names.add(entry["name"])
    year = cfg["reporting_year"]
    if isinstance(year, bool) or not isinstance(year, int):
        raise ConfigError("'reporting_year' must be a whole number.")


def resolve_path(cfg: dict, relative: str) -> Path:
    """Resolve a config path against the folder that holds the config file."""
    candidate = Path(relative)
    return candidate if candidate.is_absolute() else Path(cfg["base_dir"]) / candidate
