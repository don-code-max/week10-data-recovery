import pandas as pd

def compare_tables(tables: dict[str, pd.DataFrame], atol: float = 1e-8) -> list[str]:
    """Compares multiple tables sorting by country and year. Returns a list of mismatch errors."""
    if len(tables) <= 1:
        return []

    errors = []
    canonical_cols = ["country", "continent", "year", "lifeExp", "pop", "gdpPercap"]
    
    reference_name = list(tables.keys())[0]
    reference_df = tables[reference_name].sort_values(["country", "year"]).reset_index(drop=True)
    
    for name, df in list(tables.items())[1:]:
        compare_df = df.sort_values(["country", "year"]).reset_index(drop=True)
        
        if len(reference_df) != len(compare_df):
            errors.append(f"Row count mismatch between {reference_name} and {name}.")
            continue
            
        try:
            pd.testing.assert_frame_equal(
                reference_df[canonical_cols], 
                compare_df[canonical_cols],
                check_exact=False,
                atol=atol,
                rtol=0.0
            )
        except AssertionError as e:
            errors.append(f"Data mismatch between {reference_name} and {name}: {str(e)}")
            
    return errors