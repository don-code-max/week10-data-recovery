import numpy as np
import pandas as pd

def compare_tables(tables: dict[str, pd.DataFrame], atol: float = 1e-8) -> list[str]:
    """
    Sorts tables by (country, year) and verifies identical values across all files.
    Returns a list of error strings, or an empty list if all tables agree.
    """
    if len(tables) <= 1:
        return []
        
    differences = []
    sorted_tables = {}
    
    for name, df in tables.items():
        clean_df = df.copy()
        clean_df = clean_df.sort_values(by=['country', 'year']).reset_index(drop=True)
        sorted_tables[name] = clean_df
        
    base_name = list(sorted_tables.keys())[0]
    base_df = sorted_tables[base_name]
    
    for target_name, target_df in list(sorted_tables.items())[1:]:
        if len(base_df) != len(target_df):
            differences.append(f"Row count mismatch: {base_name} ({len(base_df)}) vs {target_name} ({len(target_df)})")
            continue
            
        # Check string / integer exact matches
        for col in ['country', 'continent', 'year', 'pop']:
            if not base_df[col].equals(target_df[col]):
                differences.append(f"Column '{col}' mismatch between {base_name} and {target_name}")
                
        # Check float matches with atol 1e-8
        for col in ['lifeExp', 'gdpPercap']:
            if not np.allclose(base_df[col], target_df[col], atol=atol, rtol=0.0):
                differences.append(f"Float column '{col}' exceeds tolerance between {base_name} and {target_name}")
                
    return differences
