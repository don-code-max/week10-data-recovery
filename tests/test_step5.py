"""Step 5: failure-handling checks. Each test breaks ONE thing in a temp copy of data/."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from src.validation import validate_records
from tests.test_step3 import raw
from src.exports import read_exports
from src.compare import compare_tables

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
    # ---------- helpers ----------
    def csv_entry(self, filename):
        """Copy the CSV input settings but point at a different file."""
        entry = dict(self.cfg["inputs"][0])
        entry["path"] = filename
        entry["file"] = filename
        return entry

    def csv_path(self):
        return self.tmp / "data" / "country_records.csv"

    def make_row(self, country="Testland", continent="Asia", year="2007",
                 life="70.5", pop="1000000", gdp="1000.5"):
        return ";".join([country, continent, year, life, pop, gdp, "test fixture"])

    def append_row(self, line):
        path = self.csv_path()
        raw = path.read_bytes()
        if not raw.endswith(b"\n"):
            raw += b"\n"
        path.write_bytes(raw + (line + "\n").encode("cp1252"))

    def quarantine_text(self):
        path = self.tmp / "outputs" / "quarantine.csv"
        return path.read_text(encoding="utf-8", errors="replace")

    def count_lines(self, name):
        path = self.tmp / "outputs" / name
        return len(path.read_text(encoding="utf-8", errors="replace").splitlines())

    def run_and_expect_quarantined(self, *markers):
        result = self.run_main()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        text = self.quarantine_text()
        for marker in markers:
            self.assertIn(marker, text)

    # ---------- tests 4 to 11 ----------
    def test_04_missing_column(self):
        self.cfg["inputs"][0] = self.csv_entry("missing_column.csv")
        self.assert_run_stopped(self.run_main())

    def test_05_missing_key(self):
        res = validate_records(raw(country=" "), "t.csv")
        self.assertEqual(res.counts["rejected"], 1)
        self.assertIn("Country cannot be empty", res.quarantine_records[0]["reason"])

    def test_06_unparseable_number(self):
        res = validate_records(raw(pop="abc"), "t.csv")
        self.assertEqual(res.counts["rejected"], 1)
        self.assertEqual(res.counts["valid"], 0)

    def test_07_fractional_year_and_population(self):
        for field, bad in (("year", "2007.5"), ("pop", "100.5")):
            with self.subTest(field=field):
                res = validate_records(raw(**{field: bad}), "t.csv")
                self.assertEqual(res.counts["rejected"], 1)

    def test_08_non_finite_and_out_of_range(self):
        cases = (("gdpPercap", "inf"), ("gdpPercap", "nan"), ("lifeExp", "-5"),
                 ("year", "1800"), ("continent", "Atlantis"))
        for field, bad in cases:
            with self.subTest(field=field, value=bad):
                res = validate_records(raw(**{field: bad}), "t.csv")
                self.assertEqual(res.counts["rejected"], 1)

    def test_09_exact_duplicates(self):
        result = self.run_main()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        # 2 duplicate copies per input x 4 inputs = 8, plus the header line.
        self.assertEqual(self.count_lines("duplicate_log.csv"), 9)

    def test_10_conflicting_keys(self):
        self.cfg["inputs"][0] = self.csv_entry("conflicting_key.csv")
        self.assert_run_stopped(self.run_main())

    def test_11_reordered_records(self):
        self.assertEqual(self.run_main().returncode, 0)
        canonical = self.tmp / "outputs" / "canonical.csv"
        baseline = canonical.read_bytes()
        raw = self.csv_path().read_bytes()
        if not raw.endswith(b"\n"):
            raw += b"\n"
        lines = raw.splitlines(keepends=True)
        self.csv_path().write_bytes(b"".join(lines[:3] + lines[3:][::-1]))
        result = self.run_main()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(canonical.read_bytes(), baseline)

        
    def test_12_corrupted_export_fails_comparison(self):
        self.assertEqual(self.run_main().returncode, 0)
        out = self.tmp / "outputs"
        # Baseline: untouched exports agree with each other.
        self.assertEqual(compare_tables(read_exports(out)), [])
        # Corrupt one population value in canonical.json (records orientation).
        json_path = out / "canonical.json"
        records = json.loads(json_path.read_text(encoding="utf-8"))
        records[0]["pop"] = int(records[0]["pop"]) + 1
        json_path.write_text(json.dumps(records), encoding="utf-8")
        problems = compare_tables(read_exports(out))
        self.assertTrue(problems, "altered export should fail comparison")


if __name__ == "__main__":
    unittest.main()
