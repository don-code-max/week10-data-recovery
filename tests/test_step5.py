"""Step 5: failure-handling checks. Each test breaks ONE thing in a temp copy of data/."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class FailureHandlingTests(unittest.TestCase):
    def setUp(self):
        """Make a temp folder with a fresh copy of data/ and a config pointing at it."""
        self.tmp = Path(tempfile.mkdtemp(prefix="step5_"))
        shutil.copytree(ROOT / "data", self.tmp / "data")
        self.cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
        self.cfg["data_dir"] = str(self.tmp / "data")
        self.cfg["output_dir"] = str(self.tmp / "outputs")
        self.cfg["staging_dir"] = str(self.tmp / "outputs" / "staging")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_main(self):
        """Write the (possibly broken) config and run main.py like a user would."""
        cfg_path = self.tmp / "config.json"
        cfg_path.write_text(json.dumps(self.cfg), encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(ROOT / "main.py"), "--config", str(cfg_path)],
            capture_output=True, text=True, cwd=ROOT,
        )

    def assert_run_stopped(self, result):
        """A stopped run exits 1, says FAILED, and publishes no final outputs."""
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("FAILED", result.stderr)
        self.assertFalse((self.tmp / "outputs" / "canonical.csv").exists())

    def test_01_normal_four_format_recovery(self):
        result = self.run_main()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.tmp / "outputs" / "canonical.csv").exists())

    def test_02_missing_file(self):
        (self.tmp / "data" / "country_records.csv").unlink()
        self.assert_run_stopped(self.run_main())

    def test_03_unsupported_format(self):
        self.cfg["inputs"][0] = {
            "name": "txt", "format": "txt",
            "path": "unsupported.txt", "file": "unsupported.txt",
        }
        result = self.run_main()
        # Rejected at config load: nonzero exit, clear message, nothing published.
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unsupported format", result.stdout + result.stderr)
        self.assertFalse((self.tmp / "outputs" / "canonical.csv").exists())


if __name__ == "__main__":
    unittest.main()
