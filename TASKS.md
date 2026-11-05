# Task Ownership

- Member 1: CSV and Excel readers, format configuration, reader checks (src/readers.py)
- Member 2: Nested JSON and Parquet readers, column mapping, normalization checks
- Member 3: Row validation, quarantine, duplicates/conflicts, rejection checks (src/validation.py)
- Member 4: pandas analysis, NumPy matrix operations, calculation checks (src/analysis.py)
- Member 5: Export/reload comparison, staging, CLI/audit integration, failure checks (src/exports.py, main.py)

Review cycle: 1 reviews 2, 2 reviews 3, 3 reviews 4, 4 reviews 5, 5 reviews 1.
