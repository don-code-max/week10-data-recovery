# Week 10: Four-Format Data Recovery and Validation

DSA4153 group project. Recovers one clean dataset from CSV, Excel, JSON and Parquet files, validates it, runs pandas/NumPy analysis, and verifies exports.

## Members, responsibilities and Git identities

| Member | Name | GitHub username | Git identity (name <email>) | Responsibility |
|---|---|---|---|---|
| 1 | Don Derek Magpantay | don-code-max | don-code-max <donderek06@gmail.com> | CSV and Excel readers, format configuration, reader checks |
| 2 | Carlos Aaron Lopez | carlosaaronlopez | carlosaaronlopez <carlosaaron.lopez@ust.edu.ph> | Nested JSON and Parquet readers, column mapping, normalization checks |
| 3 | Daniel Nico Del Mundo | nico-ust | nico-ust <danielnico.delmundo@ust.edu.ph> | Row validation, quarantine, duplicates/conflicts, rejection checks |
| 4 | Robert Gabriel Roldan | RobertRoldan1109 | Robert <robert@example.com> | pandas analysis, NumPy matrix operations, calculation checks |
| 5 | Luis Nikolai Cruzado | lucycruzado | Luis <luisnikolai.cruzado@ust.edu.ph> | Export/reload comparison, staging, CLI/audit integration, failure checks |

## Setup

Requires Python 3.10 or newer.

1. Clone the repository and open the folder:

       git clone https://github.com/don-code-max/week10-data-recovery.git
       cd week10-data-recovery

2. Create and activate a virtual environment:

       python -m venv venv
       source venv/bin/activate          # Mac/Linux
       venv\Scripts\activate             # Windows (PowerShell)

3. Install the packages:

       pip install pandas numpy openpyxl pyarrow

4. Run the tests:

       python -m unittest

Run every command from the repository root (the folder that holds `main.py` and `config.json`).

## Run

    python main.py --config config.json
