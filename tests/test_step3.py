import unittest
import pandas as pd
import tempfile
import os
from src.readers import read_records, FileLevelError
from src.validation import validate_records, remove_exact_duplicates, check_conflicting_keys, ConflictingKeyError
from src.compare import compare_tables

class TestStep3(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        
    def tearDown(self):
        self.temp_dir.cleanup()

    def test_missing_file(self):
        """missing file"""
        with self.assertRaises(FileLevelError):
            read_records("nonexistent.csv", {})

    def test_unsupported_format(self):
        """unsupported format (data/unsupported.txt)"""
        with self.assertRaises(FileLevelError):
            read_records("data/unsupported.txt", {})

    def test_missing_column(self):
        """missing column"""
        df = pd.DataFrame([{"country": "A", "continent": "Asia", "year": "1952", "lifeExp": "50", "gdpPercap": "100"}])
        with self.assertRaises(FileLevelError):
            from src.readers import _enforce_canonical_format
            _enforce_canonical_format(df, {})

    def test_validation_rules(self):
        """missing key, unparseable number, fractional year, non-finite/out-of-range"""
        raw_data = pd.DataFrame([
            {"country": "", "continent": "Asia", "year": "1952", "lifeExp": "50", "pop": "100", "gdpPercap": "100", "source_record": 1}, # empty country
            {"country": "A", "continent": "Asia", "year": "1952.5", "lifeExp": "50", "pop": "100", "gdpPercap": "100", "source_record": 2}, # fractional year
            {"country": "B", "continent": "Asia", "year": "1952", "lifeExp": "130", "pop": "100", "gdpPercap": "100", "source_record": 3}, # out of range lifeExp
            {"country": "C", "continent": "Asia", "year": "1952", "lifeExp": "50", "pop": "abc", "gdpPercap": "100", "source_record": 4}, # unparseable number
            {"country": "D", "continent": "Asia", "year": "1952", "lifeExp": "50", "pop": "100", "gdpPercap": "100", "source_record": 5}, # valid
        ])
        
        result = validate_records(raw_data, "test.csv")
        self.assertEqual(len(result.valid_df), 1)
        self.assertEqual(len(result.quarantine_records), 4)

    def test_exact_duplicates(self):
        """exact duplicates"""
        valid_df = pd.DataFrame([
            {"country": "A", "continent": "Asia", "year": 1952, "lifeExp": 50.0, "pop": 100, "gdpPercap": 100.0, "source_record": 1},
            {"country": "A", "continent": "Asia", "year": 1952, "lifeExp": 50.0, "pop": 100, "gdpPercap": 100.0, "source_record": 2},
        ])
        unique_df, logs = remove_exact_duplicates(valid_df, "test.csv")
        self.assertEqual(len(unique_df), 1)
        self.assertEqual(len(logs), 1)

    def test_conflicting_keys(self):
        """conflicting keys"""
        valid_df = pd.DataFrame([
            {"country": "A", "continent": "Asia", "year": 1952, "lifeExp": 50.0, "pop": 100, "gdpPercap": 100.0},
            {"country": "A", "continent": "Asia", "year": 1952, "lifeExp": 60.0, "pop": 100, "gdpPercap": 100.0},
        ])
        with self.assertRaises(ConflictingKeyError):
            check_conflicting_keys(valid_df)

    def test_reordered_records_comparison(self):
        """reordered records (same data in a different order still agrees)"""
        df1 = pd.DataFrame([
            {"country": "A", "continent": "Asia", "year": 1952, "lifeExp": 50.0, "pop": 100, "gdpPercap": 100.0},
            {"country": "B", "continent": "Asia", "year": 1952, "lifeExp": 60.0, "pop": 200, "gdpPercap": 200.0}
        ])
        df2 = pd.DataFrame([
            {"country": "B", "continent": "Asia", "year": 1952, "lifeExp": 60.0, "pop": 200, "gdpPercap": 200.0},
            {"country": "A", "continent": "Asia", "year": 1952, "lifeExp": 50.000000001, "pop": 100, "gdpPercap": 100.0}
        ])
        
        errors = compare_tables({"t1": df1, "t2": df2})
        self.assertEqual(len(errors), 0)

if __name__ == '__main__':
    unittest.main()
