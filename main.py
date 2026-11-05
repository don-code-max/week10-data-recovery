"""Command-line entry point: python3 main.py --config config.json"""
import argparse
import sys
from pathlib import Path

from src.config import ConfigError, load_config
from src.pipeline import run_pipeline


def main(argv=None) -> int:
    """Parse arguments, load the config and run the pipeline."""
    parser = argparse.ArgumentParser(description="Four-format data recovery and validation")
    parser.add_argument("--config", required=True, help="Path to config.json")
    args = parser.parse_args(argv)
    try:
        cfg = load_config(Path(args.config))
    except ConfigError as exc:
        print(f"Configuration error: {exc}")
        return 2
    return run_pipeline(cfg)


if __name__ == "__main__":
    sys.exit(main())
