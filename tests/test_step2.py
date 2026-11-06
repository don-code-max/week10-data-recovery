"""Tests for config and run."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.config import ConfigError, input_path, load_config
from src.pipeline import run_pipeline
from src.run import PipelineError, ProcessingRun


def write_config(folder: Path, drop: tuple = (), **overrides) -> Path:
    """Write a test config and return its path."""
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

    def test_year_outside_allowed_years_stops(self):
        years = [1997, 2007]
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ConfigError):
                load_config(write_config(Path(tmp), reporting_year=2008, allowed_years=years))
            cfg = load_config(write_config(Path(tmp), reporting_year=1997, allowed_years=years))
            self.assertEqual(cfg["reporting_year"], 1997)

    def test_staging_must_be_separate_from_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ConfigError):
                load_config(write_config(Path(tmp), staging_dir="out"))
            with self.assertRaises(ConfigError):
                load_config(write_config(Path(tmp), output_dir="out/final", staging_dir="out"))
            cfg = load_config(write_config(Path(tmp), staging_dir="out/staging"))
            self.assertEqual(cfg["staging_dir"], "out/staging")

    def test_input_path_uses_data_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = load_config(write_config(Path(tmp), data_dir="data"))
            expected = Path(cfg["base_dir"]) / "data" / "x.csv"
            self.assertEqual(input_path(cfg, cfg["inputs"][0]), expected)


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

    def test_run_with_no_checks_does_not_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = self.make_run(tmp)
            self.assertFalse(run.all_passed)
            with self.assertRaises(PipelineError):
                run.publish()

    def test_publish_removes_old_failure_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = self.make_run(tmp)
            run.output_dir.mkdir(parents=True, exist_ok=True)
            (run.output_dir / "failed_validation_report.csv").write_text("old failure")
            (run.staging_dir / "a.csv").write_text("x")
            run.add_check("ok", 1, 1)
            run.publish()
            self.assertFalse((run.output_dir / "failed_validation_report.csv").exists())

    def test_empty_run_exits_1_and_publishes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = load_config(write_config(Path(tmp)))
            self.assertEqual(run_pipeline(cfg), 1)
            self.assertFalse((Path(tmp) / "out" / "audit_log.csv").exists())
            self.assertTrue((Path(tmp) / "out" / "failed_validation_report.csv").exists())

    def test_passing_stage_publishes_and_exits_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = load_config(write_config(Path(tmp)))

            def passing_stage(run: ProcessingRun) -> None:
                run.add_check("ok", 1, 1)

            with patch("src.pipeline.default_stages", return_value=[passing_stage]):
                self.assertEqual(run_pipeline(cfg), 0)
            self.assertTrue((Path(tmp) / "out" / "validation.csv").exists())

    def test_setup_error_in_staging_exits_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = load_config(write_config(Path(tmp)))
            with patch.object(ProcessingRun, "prepare_staging", side_effect=OSError("disk full")):
                self.assertEqual(run_pipeline(cfg), 1)

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