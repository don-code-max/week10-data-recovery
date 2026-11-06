"""Run configuration."""
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
    """Invalid configuration."""


def load_config(path: Path | str) -> dict:
    """Load and validate a config file."""
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
    """Raise ConfigError if cfg is invalid."""
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
    allowed_years = cfg.get("allowed_years")
    if allowed_years and year not in set(allowed_years):
        raise ConfigError(f"'reporting_year' {year} is not in allowed_years.")
    output = resolve_path(cfg, cfg["output_dir"]).resolve()
    staging = resolve_path(
        cfg, cfg.get("staging_dir") or f"{cfg['output_dir']}_staging"
    ).resolve()
    if staging == output or staging in output.parents:
        raise ConfigError("'staging_dir' must be a separate folder from 'output_dir'.")


def resolve_path(cfg: dict, relative: str) -> Path:
    """Resolve a path against the config folder."""
    candidate = Path(relative)
    return candidate if candidate.is_absolute() else Path(cfg["base_dir"]) / candidate


def input_path(cfg: dict, entry: dict) -> Path:
    """Full path of an input file."""
    return resolve_path(cfg, str(Path(cfg.get("data_dir", "")) / entry["path"]))