
import unittest
import math
import pandas as pd
from src.common import ConflictingKeyError
from src.validation import validate_records, check_conflicting_keys, remove_exact_duplicates

class TestSection3Bugs(unittest.TestCase):

    def test_bug1_non_finite_gdp(self):
        """Ensures inf and nan are rejected in numeric fields."""
        raw_data = pd.DataFrame([
            {"source_record": 1, "country": "PH", "continent": "Asia", "year": "2007", "lifeExp": "70", "pop": "1000", "gdpPercap": "inf"},
            {"source_record": 2, "country": "PH", "continent": "Asia", "year": "2002", "lifeExp": "70", "pop": "1000", "gdpPercap": "nan"}
        ])
        res = validate_records(raw_data, "test.csv")
        self.assertEqual(res.counts["valid"], 0)
        self.assertEqual(res.counts["rejected"], 2)
        self.assertTrue("finite" in res.quarantine_records[0]["reason"].lower())

    def test_bug3_exact_duplicates_bypass_conflict(self):
        """Ensures exact duplicates do not falsely trigger ConflictingKeyError."""
        valid_df = pd.DataFrame([
            {"source_record": 1, "country": "Japan", "continent": "Asia", "year": 2007, "lifeExp": 80.0, "pop": 100, "gdpPercap": 500.0},
            {"source_record": 2, "country": "Japan", "continent": "Asia", "year": 2007, "lifeExp": 80.0, "pop": 100, "gdpPercap": 500.0}
        ])
        
        # Bug 3 fix: Calling check_conflicting_keys before remove_exact_duplicates should no longer raise an error
        try:
            check_conflicting_keys(valid_df)
        except ConflictingKeyError:
            self.fail("check_conflicting_keys raised ConflictingKeyError on exact duplicates!")

    def test_genuine_conflict_caught(self):
        """Ensures differing values for the same key still raise the error."""
        valid_df = pd.DataFrame([
            {"source_record": 1, "country": "Japan", "continent": "Asia", "year": 2007, "lifeExp": 80.0, "pop": 100, "gdpPercap": 500.0},
            {"source_record": 2, "country": "Japan", "continent": "Asia", "year": 2007, "lifeExp": 82.0, "pop": 100, "gdpPercap": 500.0} # differing lifeExp
        ])
        with self.assertRaises(ConflictingKeyError):
            check_conflicting_keys(valid_df)

    def test_validation_result_structure(self):
        """Tests that the new ValidationResult structure (.counts) works correctly."""
        raw_data = pd.DataFrame([
            {"source_record": 1, "country": "PH", "continent": "Asia", "year": "2007", "lifeExp": "70", "pop": "1000", "gdpPercap": "500"},
            {"source_record": 2, "country": " ", "continent": "Asia", "year": "2007", "lifeExp": "70", "pop": "100", "gdpPercap": "200"}
        ])
        res = validate_records(raw_data, "test.csv")
        self.assertEqual(res.counts["valid"], 1)
        self.assertEqual(res.counts["rejected"], 1)
        self.assertIn("Country cannot be empty", res.quarantine_records[0]["reason"])

if __name__ == '__main__':
    unittest.main()