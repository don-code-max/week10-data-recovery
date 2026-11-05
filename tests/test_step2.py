"""Automated checks for the config loader and the ProcessingRun class."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.config import ConfigError, load_config
from src.pipeline import run_pipeline
from src.run import PipelineError, ProcessingRun


def write_config(folder: Path, drop: tuple = (), **overrides) -> Path:
    """Write a small config file into a temp folder and return its path."""
    cfg = {"inputs": [{"name": "csv", "path": "x.csv", "format": "csv"}], "output_dir": "out"}
    cfg.update(overrides)
    for key in drop:
        cfg.pop(key)
    path = folder / "config.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    return path


class ConfigTests(unittest.TestCase):
    def test_default_reporting_year_is_2007(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(load_config(write_config(Path(tmp)))["reporting_year"], 2007)

    def test_reporting_year_can_be_changed_in_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(load_config(write_config(Path(tmp), reporting_year=1997))["reporting_year"], 1997)

    def test_missing_required_key_stops(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ConfigError):
                load_config(write_config(Path(tmp), drop=("output_dir",)))

    def test_unsupported_format_stops(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = [{"name": "t", "path": "unsupported.txt", "format": "txt"}]
            with self.assertRaises(ConfigError):
                load_config(write_config(Path(tmp), inputs=bad))

    def test_missing_config_file_stops(self):
        with self.assertRaises(ConfigError):
            load_config("no_such_config.json")


class ProcessingRunTests(unittest.TestCase):
    def make_run(self, tmp: str) -> ProcessingRun:
        run = ProcessingRun(load_config(write_config(Path(tmp))))
        run.prepare_staging()
        return run

    def test_check_uses_tolerance_for_floats(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = self.make_run(tmp)
            self.assertTrue(run.add_check("close", 1.0, 1.0 + 1e-9, tolerance=1e-8))
            self.assertFalse(run.add_check("far", 1.0, 1.1, tolerance=1e-8))

    def test_publish_moves_staged_files_when_all_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = self.make_run(tmp)
            (run.staging_dir / "a.csv").write_text("x")
            run.add_check("ok", 1, 1)
            run.publish()
            self.assertTrue((run.output_dir / "a.csv").exists())
            self.assertFalse(run.staging_dir.exists())

    def test_publish_refused_after_failed_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = self.make_run(tmp)
            (run.staging_dir / "a.csv").write_text("x")
            run.add_check("bad", 1, 2)
            with self.assertRaises(PipelineError):
                run.publish()
            self.assertFalse((run.output_dir / "a.csv").exists())

    def test_failed_run_returns_1_and_keeps_old_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = load_config(write_config(Path(tmp)))
            out = Path(tmp) / "out"
            out.mkdir()
            (out / "canonical.csv").write_text("old")

            def failing_stage(run: ProcessingRun) -> None:
                raise PipelineError("simulated conflict")

            with patch("src.pipeline.default_stages", return_value=[failing_stage]):
                self.assertEqual(run_pipeline(cfg), 1)
            self.assertEqual((out / "canonical.csv").read_text(), "old")
            self.assertTrue((out / "failed_validation_report.csv").exists())


if __name__ == "__main__":
    unittest.main()
