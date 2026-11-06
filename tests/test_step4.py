"""Section 4 tests: analysis tables, NumPy index, exports and reload."""
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
import openpyxl

from src.analysis import (build_asia_selected_year, build_country_history,
                          index_by_broadcast, index_by_loop, population_matrix,
                          stage_analysis)
from src.config import load_config
from src.exports import apply_schema, stage_exports, types_ok
from src.recover import stage_recover_inputs
from src.run import PipelineError, ProcessingRun

CONFIG = Path(__file__).resolve().parent.parent / "config.json"

def make_run(tmp, year=None):
    cfg = load_config(CONFIG)
    cfg["output_dir"] = str(Path(tmp) / "out")
    cfg["staging_dir"] = str(Path(tmp) / "out" / "staging")
    if year is not None:
        cfg["reporting_year"] = year
    run = ProcessingRun(cfg)
    run.prepare_staging()
    stage_recover_inputs(run)
    return run

class TestAnalysisFunctions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.pipeline_run = make_run(cls.tmp.name)
        cls.df = cls.pipeline_run.canonical

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_asia_2007(self):
        asia = build_asia_selected_year(self.df, 2007)
        self.assertEqual(len(asia), 33)
        self.assertEqual(int(asia["pop"].sum()), 3_811_953_827)
        self.assertEqual(list(asia["lifeExp_rank"]), sorted(asia["lifeExp_rank"]))
        self.assertAlmostEqual(asia["pop_millions"].iloc[0] * 1e6, asia["pop"].iloc[0])

    def test_asia_rank_method_min_ties(self):
        df = pd.DataFrame([
            {"country": "B", "continent": "Asia", "year": 2007, "lifeExp": 70.0, "pop": 2, "gdpPercap": 1.0},
            {"country": "A", "continent": "Asia", "year": 2007, "lifeExp": 70.0, "pop": 1, "gdpPercap": 1.0},
            {"country": "C", "continent": "Asia", "year": 2007, "lifeExp": 60.0, "pop": 3, "gdpPercap": 1.0}
        ])
        asia = build_asia_selected_year(df, 2007)
        self.assertEqual(list(asia["country"]), ["A", "B", "C"])
        self.assertEqual(list(asia["lifeExp_rank"]), [1, 1, 3])

    def test_other_year_selected(self):
        asia = build_asia_selected_year(self.df, 1997)
        self.assertTrue((asia["year"] == 1997).all())
        self.assertNotEqual(int(asia["pop"].sum()), 3_811_953_827)

    def test_philippines_history(self):
        hist = build_country_history(self.df, "Philippines")
        self.assertEqual(len(hist), 12)
        self.assertEqual(list(hist["year"]), sorted(hist["year"]))
        self.assertEqual(hist["lifeExp_change"].iloc[0], 0.0)
        self.assertEqual(int(hist["pop"].iloc[-1]), 91_077_287)

    def test_matrix_and_broadcast(self):
        matrix = population_matrix(self.df)
        baseline, index = index_by_broadcast(matrix)
        self.assertEqual(matrix.shape, (3, 6))
        self.assertEqual(baseline.shape, (3, 1))
        self.assertEqual(index.shape, (3, 6))
        self.assertTrue(np.allclose(index[:, 0], 100.0))
        self.assertTrue(np.allclose(index, index_by_loop(matrix), atol=1e-8, rtol=0.0))


class TestAnalysisStage(unittest.TestCase):
    def test_stage_passes_and_writes_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(tmp)
            stage_analysis(run)
            self.assertTrue(run.all_passed)
            for name in ("asia_selected_year.csv", "country_history.csv", "population_index.csv"):
                self.assertTrue((run.staging_dir / name).exists())
            index = pd.read_csv(run.staging_dir / "population_index.csv")
            self.assertEqual(list(index.columns), ["country", "1982", "1987", "1992", "1997", "2002", "2007"])
            self.assertEqual(len(pd.read_csv(run.staging_dir / "asia_selected_year.csv")), 33)

    def test_reporting_year_is_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(tmp, year=1997)
            stage_analysis(run)
            asia = pd.read_csv(run.staging_dir / "asia_selected_year.csv")
            self.assertTrue((asia["year"] == 1997).all())
            self.assertTrue(run.all_passed)

    def test_requires_canonical(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(tmp)
            run.canonical = None
            with self.assertRaises(PipelineError):
                stage_analysis(run)


class TestExports(unittest.TestCase):
    def test_exports_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(tmp)
            stage_exports(run)
            self.assertTrue(run.all_passed)
            for name in ("canonical.csv", "canonical.xlsx", "canonical.json", "canonical.parquet"):
                self.assertTrue((run.staging_dir / name).exists())
            self.assertEqual(openpyxl.load_workbook(run.staging_dir / "canonical.xlsx").sheetnames, ["observations"])
            self.assertTrue((run.staging_dir / "canonical.json").read_text().lstrip().startswith("[{") or 
                            (run.staging_dir / "canonical.json").read_text().lstrip().startswith("["))
            self.assertEqual(list(pd.read_csv(run.staging_dir / "canonical.csv").columns),
                             ["country", "continent", "year", "lifeExp", "pop", "gdpPercap"])

    def test_apply_schema_refuses_fractional_year(self):
        df = pd.DataFrame([{"country": "A", "continent": "Asia", "year": 2007.5, "lifeExp": 1.0, "pop": 1, "gdpPercap": 1.0}])
        with self.assertRaises(PipelineError):
            apply_schema(df)

    def test_apply_schema_converts_floats_that_are_whole(self):
        df = pd.DataFrame([{"country": "A", "continent": "Asia", "year": 2007.0, "lifeExp": 1.0, "pop": 5.0, "gdpPercap": 1.0}])
        out, notes = apply_schema(df)
        self.assertTrue(types_ok(out))
        self.assertTrue(notes)

    def test_requires_canonical(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = make_run(tmp)
            run.canonical = None
            with self.assertRaises(PipelineError):
                stage_exports(run)

if __name__ == "__main__":
    unittest.main()