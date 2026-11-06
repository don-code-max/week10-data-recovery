"""Section 3 tests: readers, validation, duplicates, conflicts, compare, stage."""
import os
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.common import ConflictingKeyError, FileLevelError
from src.compare import compare_tables
from src.config import input_path, load_config
from src.readers import read_csv_records, read_records
from src.recover import stage_recover_inputs
from src.run import ProcessingRun
from src.validation import (check_conflicting_keys, remove_exact_duplicates,
                            validate_records)

CONFIG = Path(__file__).resolve().parent.parent / "config.json"


def row(n, country="PH", year=2007, life=70.0, pop=1000, gdp=500.0, continent="Asia"):
    return {"source_record": n, "country": country, "continent": continent,
            "year": year, "lifeExp": life, "pop": pop, "gdpPercap": gdp}


def raw(**changes):
    base = {"source_record": 1, "country": "PH", "continent": "Asia", "year": "2007",
            "lifeExp": "70", "pop": "1000", "gdpPercap": "500"}
    base.update(changes)
    return pd.DataFrame([base])


class TestReaders(unittest.TestCase):
    def test_missing_file(self):
        with self.assertRaises(FileLevelError):
            read_records("no_such_file.csv", {"format": "csv", "source_to_canonical": {}})

    def test_unsupported_format(self):
        with self.assertRaises(FileLevelError):
            read_records("x.txt", {"format": "txt"})

    def test_missing_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "missing.csv")
            pd.DataFrame([{"country": "PH", "continent": "Asia", "year": "2007",
                           "lifeExp": "70", "gdpPercap": "1000"}]).to_csv(path, index=False)
            settings = {"source_to_canonical": {c: c for c in
                        ["country", "continent", "year", "lifeExp", "pop", "gdpPercap"]}}
            with self.assertRaises(FileLevelError):
                read_csv_records(path, settings)

    def test_real_config_reads_all_four(self):
        cfg = load_config(CONFIG)
        for entry in cfg["inputs"]:
            df = read_records(str(input_path(cfg, entry)), entry)
            self.assertEqual(len(df), 1712, entry["name"])


class TestValidation(unittest.TestCase):
    def test_non_finite_gdp_rejected(self):
        for bad in ("inf", "nan", "-inf"):
            res = validate_records(raw(gdpPercap=bad), "t.csv")
            self.assertEqual(res.counts, {"valid": 0, "rejected": 1}, bad)
            self.assertIn("finite", res.quarantine_records[0]["reason"].lower())

    def test_blank_country_rejected(self):
        res = validate_records(raw(country=" "), "t.csv")
        self.assertEqual(res.counts["rejected"], 1)
        self.assertIn("Country cannot be empty", res.quarantine_records[0]["reason"])

    def test_fractional_pop_and_year_rejected(self):
        self.assertEqual(validate_records(raw(pop="100.5"), "t").counts["rejected"], 1)
        self.assertEqual(validate_records(raw(year="2007.5"), "t").counts["rejected"], 1)

    def test_valid_row_converted(self):
        res = validate_records(raw(pop=" 1000 "), "t")
        self.assertEqual(res.counts["valid"], 1)
        self.assertEqual(int(res.valid_df.iloc[0]["pop"]), 1000)

    def test_quarantine_keeps_original_text(self):
        res = validate_records(raw(year="not-a-year"), "t")
        self.assertEqual(res.quarantine_records[0]["year"], "not-a-year")

    def test_rules_use_config_keys(self):
        rules = {"allowed_years": [1997]}
        self.assertEqual(validate_records(raw(year="2007"), "t", rules).counts["rejected"], 1)
        self.assertEqual(validate_records(raw(year="1997"), "t", rules).counts["valid"], 1)
        rules = {"allowed_continents": ["Europe"]}
        self.assertEqual(validate_records(raw(), "t", rules).counts["rejected"], 1)


class TestDuplicatesAndConflicts(unittest.TestCase):
    def test_exact_duplicates(self):
        deduped, log = remove_exact_duplicates(pd.DataFrame([row(1), row(2)]), "t.csv")
        self.assertEqual(len(deduped), 1)
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]["duplicate_of_source_record"], 1)

    def test_conflicting_keys_raise(self):
        with self.assertRaises(ConflictingKeyError):
            check_conflicting_keys(pd.DataFrame([row(1), row(2, life=72.0)]))

    def test_exact_duplicates_are_not_a_conflict(self):
        check_conflicting_keys(pd.DataFrame([row(1), row(2)]))


class TestCompare(unittest.TestCase):
    def tables(self, life=70.000000001):
        t1 = pd.DataFrame([row(1, "A", 2002), row(2, "B", 2007)])
        t2 = pd.DataFrame([row(1, "B", 2007, life=life), row(2, "A", 2002)])
        return {"t1": t1, "t2": t2}

    def test_reordered_within_tolerance(self):
        self.assertEqual(compare_tables(self.tables()), [])

    def test_float_beyond_tolerance(self):
        self.assertTrue(compare_tables(self.tables(life=70.001)))

    def test_text_difference(self):
        t = self.tables()
        t["t2"].loc[:, "continent"] = "Europe"
        self.assertTrue(compare_tables(t))

    def test_row_count_difference(self):
        t = self.tables()
        t["t2"] = t["t2"].iloc[:1]
        self.assertTrue(compare_tables(t))


class TestStage(unittest.TestCase):
    def make_run(self, tmp):
        cfg = load_config(CONFIG)
        cfg["output_dir"] = str(Path(tmp) / "out")
        cfg["staging_dir"] = str(Path(tmp) / "out" / "staging")
        run = ProcessingRun(cfg)
        run.prepare_staging()
        return run

    def test_stage_on_real_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = self.make_run(tmp)
            stage_recover_inputs(run)
            self.assertTrue(run.all_passed)
            self.assertEqual(len(run.canonical), 1704)
            self.assertEqual(list(run.canonical.columns),
                             ["country", "continent", "year", "lifeExp", "pop", "gdpPercap"])
            q = pd.read_csv(run.staging_dir / "quarantine.csv")
            d = pd.read_csv(run.staging_dir / "duplicate_log.csv")
            self.assertEqual((len(q), len(d)), (24, 8))

    def test_stage_stops_on_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = self.make_run(tmp)
            run.cfg["data_dir"] = str(Path(tmp) / "nowhere")
            with self.assertRaises(FileLevelError):
                stage_recover_inputs(run)


if __name__ == "_main_":
    unittest.main()