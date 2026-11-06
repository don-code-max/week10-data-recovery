import unittest
import tempfile
import os
import pandas as pd
from src.common import FileLevelError, ConflictingKeyError
from src.readers import read_csv_records, read_records
from src.validation import validate_records, remove_exact_duplicates, check_conflicting_keys
from src.compare import compare_tables

class TestSection3Recovery(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.canonical_mapping = {
            "source_to_canonical": {
                "c_name": "country", "cont": "continent", "yr": "year",
                "le": "lifeExp", "population": "pop", "gdp": "gdpPercap"
            }
        }

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
        # Missing pop column mapping
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

    def test_validation_rules_and_quarantine(self):
        raw_data = pd.DataFrame([
            {"source_record": 1, "country": "Philippines", "continent": "Asia", "year": "2007", "lifeExp": "71.2", "pop": "91077287", "gdpPercap": "3190.4"},
            {"source_record": 2, "country": " ", "continent": "Asia", "year": "2007", "lifeExp": "70.0", "pop": "100", "gdpPercap": "200"}, # empty country
            {"source_record": 3, "country": "Atlantis", "continent": "Unknown", "year": "2007", "lifeExp": "70.0", "pop": "100", "gdpPercap": "200"}, # bad continent
            {"source_record": 4, "country": "Japan", "continent": "Asia", "year": "2006", "lifeExp": "80.0", "pop": "100", "gdpPercap": "200"}, # bad year interval
            {"source_record": 5, "country": "Canada", "continent": "Americas", "year": "2007", "lifeExp": "150.0", "pop": "100", "gdpPercap": "200"}, # lifeExp > 120
            {"source_record": 6, "country": "Norway", "continent": "Europe", "year": "2007", "lifeExp": "81.0", "pop": "-500", "gdpPercap": "200"}, # negative pop
            {"source_record": 7, "country": "France", "continent": "Europe", "year": "2007", "lifeExp": "81.0", "pop": "1000.5", "gdpPercap": "200"} # non-integer pop
        ])
        res = validate_records(raw_data, "test.csv")
        self.assertEqual(res.valid_count, 1)
        self.assertEqual(res.rejected_count, 6)

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
            {"country": "PH", "continent": "Asia", "year": 2007, "lifeExp": 70.0, "pop": 1000, "gdpPercap": 500.0},
            {"country": "PH", "continent": "Asia", "year": 2007, "lifeExp": 72.0, "pop": 1000, "gdpPercap": 500.0}
        ])
        with self.assertRaises(ConflictingKeyError):
            check_conflicting_keys(valid_df)

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

if __name__ == '__main__':
    unittest.main()
