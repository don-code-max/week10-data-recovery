import unittest
import tempfile
import os
import json
import pandas as pd
from src.common import FileLevelError, ConflictingKeyError
from src.readers import read_csv_records, read_records
from src.validation import validate_records, remove_exact_duplicates, check_conflicting_keys
from src.compare import compare_tables

def _mock_input_path(cfg, entry):
    """Helper to safely build paths without relying on external util modules."""
    input_dir = cfg.get("input_dir", "data")
    filename = entry.get("path", entry.get("file", ""))
    return os.path.join(input_dir, filename)

class TestSection3Recovery(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_missing_file(self):
        settings = {"format": "csv", "source_to_canonical": {}}
        with self.assertRaises(FileLevelError):
            read_records("non_existent_file.csv", settings)

    def test_unsupported_format(self):
        settings = {"format": "txt"}
        with self.assertRaises(FileLevelError):
            read_records("sample.txt", settings)

    def test_missing_column(self):
        settings = {
            "source_to_canonical": {
                "country": "country", "continent": "continent",
                "year": "year", "lifeExp": "lifeExp", "gdpPercap": "gdpPercap"
            }
        }
        test_csv = os.path.join(self.tmp_dir.name, "missing.csv")
        pd.DataFrame([{"country": "PH", "continent": "Asia", "year": "2007", "lifeExp": "70", "gdpPercap": "1000"}]).to_csv(test_csv, index=False)
        with self.assertRaises(FileLevelError):
            read_csv_records(test_csv, settings)

    def test_exact_duplicates(self):
        valid_df = pd.DataFrame([
            {"source_record": 1, "country": "PH", "continent": "Asia", "year": 2007, "lifeExp": 70.0, "pop": 1000, "gdpPercap": 500.0},
            {"source_record": 2, "country": "PH", "continent": "Asia", "year": 2007, "lifeExp": 70.0, "pop": 1000, "gdpPercap": 500.0}
        ])
        deduped, log = remove_exact_duplicates(valid_df, "test.csv")
        self.assertEqual(len(deduped), 1)
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]["duplicate_of_source_record"], 1)

    def test_conflicting_keys(self):
        valid_df = pd.DataFrame([
            {"source_record": 1, "country": "PH", "continent": "Asia", "year": 2007, "lifeExp": 70.0, "pop": 1000, "gdpPercap": 500.0},
            {"source_record": 2, "country": "PH", "continent": "Asia", "year": 2007, "lifeExp": 72.0, "pop": 1000, "gdpPercap": 500.0}
        ])
        with self.assertRaises(ConflictingKeyError):
            check_conflicting_keys(valid_df)
            
    def test_bug1_non_finite_gdp(self):
        raw_data = pd.DataFrame([
            {"source_record": 1, "country": "PH", "continent": "Asia", "year": "2007", "lifeExp": "70", "pop": "1000", "gdpPercap": "inf"},
            {"source_record": 2, "country": "PH", "continent": "Asia", "year": "2002", "lifeExp": "70", "pop": "1000", "gdpPercap": "nan"}
        ])
        res = validate_records(raw_data, "test.csv")
        self.assertEqual(res.counts["valid"], 0)
        self.assertEqual(res.counts["rejected"], 2)
        self.assertTrue("finite" in res.quarantine_records[0]["reason"].lower())

    def test_bug3_exact_duplicates_bypass_conflict(self):
        valid_df = pd.DataFrame([
            {"source_record": 1, "country": "Japan", "continent": "Asia", "year": 2007, "lifeExp": 80.0, "pop": 100, "gdpPercap": 500.0},
            {"source_record": 2, "country": "Japan", "continent": "Asia", "year": 2007, "lifeExp": 80.0, "pop": 100, "gdpPercap": 500.0}
        ])
        try:
            check_conflicting_keys(valid_df)
        except ConflictingKeyError:
            self.fail("check_conflicting_keys raised ConflictingKeyError on exact duplicates!")

    def test_compare_tables_reordered(self):
        t1 = pd.DataFrame([
            {"country": "A", "continent": "Asia", "year": 2002, "lifeExp": 60.0, "pop": 10, "gdpPercap": 100.0},
            {"country": "B", "continent": "Europe", "year": 2007, "lifeExp": 70.0, "pop": 20, "gdpPercap": 200.0}
        ])
        t2 = pd.DataFrame([
            {"country": "B", "continent": "Europe", "year": 2007, "lifeExp": 70.000000001, "pop": 20, "gdpPercap": 200.0},
            {"country": "A", "continent": "Asia", "year": 2002, "lifeExp": 60.0, "pop": 10, "gdpPercap": 100.0}
        ])
        diffs = compare_tables({"table1": t1, "table2": t2})
        self.assertEqual(len(diffs), 0)

    def test_real_config_reads_all_four(self):
        if not os.path.exists("config.json"):
            self.skipTest("config.json not found in working directory.")
            
        with open("config.json", "r") as f:
            cfg = json.load(f)
            
        for entry in cfg.get("inputs", []):
            path = _mock_input_path(cfg, entry)
            if not os.path.exists(path):
                self.skipTest(f"Data file {path} not found. Ensure data/ folder exists.")
                
            # FIX: The entry itself is the settings dict
            df = read_records(path, entry) 
            self.assertEqual(len(df), 1712, f"Failed reading 1712 rows from {path}")

    def test_rules_are_respected(self):
        raw_data = pd.DataFrame([
            {"source_record": 1, "country": "PH", "continent": "Asia", "year": "2007", "lifeExp": "70", "pop": "1000", "gdpPercap": "500"}
        ])
        res = validate_records(raw_data, "test.csv", rules={"years": [1997]})
        self.assertEqual(res.counts["valid"], 0)
        self.assertEqual(res.counts["rejected"], 1)

if __name__ == '__main__':
    unittest.main()