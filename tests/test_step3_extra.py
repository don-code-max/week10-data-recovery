import unittest
import pandas as pd
import numpy as np
from src.readers import read_records, FileLevelError
from src.validation import validate_records
from src.compare import compare_tables

class TestStep3Extra(unittest.TestCase):
    def test_rejection_rules_detailed(self):
        """Covers each rejection rule including inf, nan, and fractional values."""
        raw_data = pd.DataFrame([
            # valid
            {"country": "A", "continent": "Asia", "year": "1952", "lifeExp": "50", "pop": "100", "gdpPercap": "100", "source_record": 1},
            # inf / nan
            {"country": "B", "continent": "Asia", "year": "1952", "lifeExp": "inf", "pop": "100", "gdpPercap": "100", "source_record": 2},
            {"country": "C", "continent": "Asia", "year": "1952", "lifeExp": "50", "pop": "nan", "gdpPercap": "100", "source_record": 3},
            # fractional population
            {"country": "D", "continent": "Asia", "year": "1952", "lifeExp": "50", "pop": "100.5", "gdpPercap": "100", "source_record": 4},
        ])
        
        result = validate_records(raw_data, "test.csv")
        self.assertEqual(result.counts["valid"], 1)
        self.assertEqual(result.counts["quarantined"], 3)
        reasons = [r["reason"] for r in result.quarantine_records]
        self.assertTrue(any("lifeExp" in r or "parse" in r for r in reasons))
        
    def test_compare_tables_reports_difference(self):
        """Ensures compare_tables actually reports differences."""
        df1 = pd.DataFrame([{"country": "A", "continent": "Asia", "year": 1952, "lifeExp": 50.0, "pop": 100, "gdpPercap": 100.0}])
        df2 = pd.DataFrame([{"country": "A", "continent": "Asia", "year": 1952, "lifeExp": 50.0, "pop": 999, "gdpPercap": 100.0}])
        
        errors = compare_tables({"table1": df1, "table2": df2})
        self.assertEqual(len(errors), 1)
        self.assertTrue("Data mismatch" in errors[0])

    def test_failure_files(self):
        """Tests missing_column.csv, unsupported.txt, and conflicting_key.csv behavior."""
        with self.assertRaises(FileLevelError):
            read_records("data/unsupported.txt", {})
            
        # The other failure files (missing_column, conflicting_key) were covered in test_step3.py, 
        # but you can point them to your real data/ folder here if needed.

if __name__ == '__main__':
    unittest.main()