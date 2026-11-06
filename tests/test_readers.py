"""Tests for the CSV and Excel readers (Member 1)."""
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.common import FileLevelError
from src.config import input_path, load_config
from src.readers import read_csv_records, read_excel_records

ROOT = Path(__file__).resolve().parent.parent
CANONICAL = ["country", "continent", "year", "lifeExp", "pop", "gdpPercap"]
MAPPING = {"CountryName": "country", "ContinentName": "continent", "ObservationYear": "year",
           "LifeYears": "lifeExp", "PopulationPersons": "pop", "GDPPerPerson": "gdpPercap"}


def entry(name):
    cfg = load_config(ROOT / "config.json")
    item = next(e for e in cfg["inputs"] if e["name"] == name)
    return str(input_path(cfg, item)), item


class TestCsvReaderRealFile(unittest.TestCase):
    def setUp(self):
        self.path, self.settings = entry("csv")
        self.df = read_csv_records(self.path, self.settings)

    def test_row_count_and_columns(self):
        self.assertEqual(len(self.df), 1712)
        self.assertEqual(list(self.df.columns), ["source_record"] + CANONICAL)

    def test_source_records_start_at_one(self):
        self.assertEqual(list(self.df["source_record"][:3]), [1, 2, 3])

    def test_values_are_original_text(self):
        for col in CANONICAL:
            self.assertTrue(self.df[col].map(lambda v: isinstance(v, str)).all(), col)

    def test_export_note_dropped(self):
        self.assertNotIn("export_note", self.df.columns)


class TestExcelReaderRealFile(unittest.TestCase):
    def setUp(self):
        self.path, self.settings = entry("xlsx")
        self.df = read_excel_records(self.path, self.settings)

    def test_row_count_and_columns(self):
        self.assertEqual(len(self.df), 1712)
        self.assertEqual(list(self.df.columns), ["source_record"] + CANONICAL)

    def test_values_are_original_text(self):
        for col in CANONICAL:
            self.assertTrue(self.df[col].map(lambda v: isinstance(v, str)).all(), col)

    def test_readme_sheet_ignored(self):
        with pd.ExcelFile(self.path) as workbook:
              names = workbook.sheet_names
        self.assertIn("observations", names)
        self.assertTrue(set(self.df["country"]) - {"", "Readme"})

    def test_same_countries_as_csv(self):
        path, settings = entry("csv")
        csv = read_csv_records(path, settings)
        # The files list the rows in different orders, so compare sorted values.
        key = ["country", "year"]
        left = self.df.sort_values(key)[CANONICAL].reset_index(drop=True)
        right = csv.sort_values(key)[CANONICAL].reset_index(drop=True)
        self.assertEqual(len(left), len(right))
        self.assertEqual(left["country"].tolist(), right["country"].tolist())


class TestCsvReaderFailures(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.settings = {"encoding": "cp1252", "sep": ";", "comment": "#",
                         "source_to_canonical": MAPPING}

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, text, name="t.csv", raw=None):
        path = self.dir / name
        path.write_bytes(raw if raw is not None else text.encode("cp1252"))
        return str(path)

    GOOD = ("# comment one\n# comment two\n"
            "CountryName;ContinentName;ObservationYear;LifeYears;PopulationPersons;GDPPerPerson;export_note\n"
            "Peru;Americas;2007;71.4;28674757;7408.9;x\n")

    def test_good_file_with_comments(self):
        df = read_csv_records(self.write(self.GOOD), self.settings)
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["country"], "Peru")
        self.assertEqual(df.iloc[0]["pop"], "28674757")

    def test_separator_comes_from_settings(self):
        text = self.GOOD.replace(";", ",")
        df = read_csv_records(self.write(text), {**self.settings, "sep": ","})
        self.assertEqual(len(df), 1)

    def test_wrong_separator_is_file_level_error(self):
        with self.assertRaises(FileLevelError):
            read_csv_records(self.write(self.GOOD), {**self.settings, "sep": ","})

    def test_missing_file(self):
        with self.assertRaises(FileLevelError):
            read_csv_records(str(self.dir / "none.csv"), self.settings)

    def test_empty_file(self):
        with self.assertRaises(FileLevelError):
            read_csv_records(self.write(""), self.settings)

    def test_undecodable_bytes(self):
        with self.assertRaises(FileLevelError) as ctx:
            read_csv_records(self.write("", raw=b"a;b\n\x81;2\n"), self.settings)
        self.assertIn("decoded", str(ctx.exception))

    def test_missing_column_named_in_message(self):
        text = self.GOOD.replace("PopulationPersons", "Pop")
        with self.assertRaises(FileLevelError) as ctx:
            read_csv_records(self.write(text), self.settings)
        self.assertIn("PopulationPersons", str(ctx.exception))

    def test_blank_cell_kept_as_empty_text(self):
        text = self.GOOD.replace("Peru;", ";")
        df = read_csv_records(self.write(text), self.settings)
        self.assertEqual(df.iloc[0]["country"], "")

    def test_na_text_not_converted(self):
        text = self.GOOD.replace("Peru", "NA")
        df = read_csv_records(self.write(text), self.settings)
        self.assertEqual(df.iloc[0]["country"], "NA")


class TestExcelReaderFailures(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.mapping = {"country_name": "country", "continent_name": "continent",
                        "observation_year": "year", "life_expectancy": "lifeExp",
                        "population": "pop", "gdp_per_capita": "gdpPercap"}

    def tearDown(self):
        self.tmp.cleanup()

    def workbook(self, sheet="observations", columns=None):
        columns = columns or list(self.mapping)
        path = self.dir / "t.xlsx"
        pd.DataFrame([["Peru", "Americas", "2007", "71.4", "28674757", "7408.9"]],
                     columns=columns).to_excel(path, sheet_name=sheet, index=False)
        return str(path)

    def test_good_workbook(self):
        df = read_excel_records(self.workbook(), {"source_to_canonical": self.mapping})
        self.assertEqual(df.iloc[0]["pop"], "28674757")

    def test_wrong_sheet_is_file_level_error(self):
        with self.assertRaises(FileLevelError) as ctx:
            read_excel_records(self.workbook(sheet="other"), {"source_to_canonical": self.mapping})
        self.assertIn("observations", str(ctx.exception))

    def test_sheet_name_from_settings(self):
        df = read_excel_records(self.workbook(sheet="other"),
                                {"sheet_name": "other", "source_to_canonical": self.mapping})
        self.assertEqual(len(df), 1)

    def test_not_a_workbook(self):
        path = self.dir / "fake.xlsx"
        path.write_text("not a workbook")
        with self.assertRaises(FileLevelError):
            read_excel_records(str(path), {"source_to_canonical": self.mapping})

    def test_missing_column_named_in_message(self):
        cols = list(self.mapping)
        cols[4] = "pop_x"
        with self.assertRaises(FileLevelError) as ctx:
            read_excel_records(self.workbook(columns=cols), {"source_to_canonical": self.mapping})
        self.assertIn("population", str(ctx.exception))

    def test_missing_file(self):
        with self.assertRaises(FileLevelError):
            read_excel_records(str(self.dir / "none.xlsx"), {"source_to_canonical": self.mapping})


if __name__ == "__main__":
    unittest.main()