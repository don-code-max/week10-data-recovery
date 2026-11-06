"""Compare the recovered tables by key."""
from __future__ import annotations

import numpy as np
import pandas as pd

KEY = ["country", "year"]
EXACT = ["continent", "pop"]
FLOATS = ["lifeExp", "gdpPercap"]


def compare_tables(tables: dict[str, pd.DataFrame], atol: float = 1e-8) -> list[str]:
    """Return a list of differences (empty list = all tables agree).

    Tables are matched by (country, year). Text and integer columns must be
    exactly equal; floats use atol with rtol=0.
    """
    names = list(tables)
    if len(names) < 2:
        return []
    ordered = {n: tables[n].sort_values(KEY).reset_index(drop=True) for n in names}
    base_name = names[0]
    base = ordered[base_name]
    problems: list[str] = []
    for name in names[1:]:
        other = ordered[name]
        if len(base) != len(other):
            problems.append(f"Row count differs: {base_name}={len(base)}, {name}={len(other)}")
            continue
        for col in KEY + EXACT:
            if not (base[col].to_numpy() == other[col].to_numpy()).all():
                problems.append(f"Column '{col}' differs between {base_name} and {name}")
        for col in FLOATS:
            if not np.allclose(base[col].astype(float), other[col].astype(float),
                               atol=atol, rtol=0.0):
                problems.append(f"Column '{col}' differs beyond atol={atol} "
                                f"between {base_name} and {name}")
    return problems