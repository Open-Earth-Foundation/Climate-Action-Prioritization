#!/usr/bin/env python3
import pandas as pd
from pathlib import Path
import numpy as np

def filter_empty_adaptation_effectiveness(df):
    """Filter out adaptation actions that have no AdaptationEffectiveness value"""
    # Identify adaptation actions (where 'adaptation' is in the ActionType list)
    is_adaptation = df['ActionType'].apply(lambda x: 'adaptation' in x if isinstance(x, list) else False)
    empty_hazard = df['Hazard'].isna()
    empty_adaptation = df['AdaptationEffectiveness'].isna()
    
    # Actions to delete are adaptation actions without AdaptationEffectiveness
    deleted_actions = df[is_adaptation & empty_hazard & empty_adaptation]
    
    # Keep all other actions
    updated_actions = df[~(is_adaptation & empty_hazard & empty_adaptation)]
    
    return updated_actions, deleted_actions

def filter_empty_mitigation_ghg(df):
    """Filter out mitigation actions that have no GHG reduction potential"""
    # Identify mitigation actions (where 'mitigation' is in the ActionType list)
    is_mitigation = df['ActionType'].apply(lambda x: 'mitigation' in x if isinstance(x, list) else False)
    
    # Check for empty GHG reduction potential
    # First check if GHGReductionPotential is null
    null_ghg = df['GHGReductionPotential'].isna()
    
    # For non-null values, check if any sector has a value
    has_ghg_value = df['GHGReductionPotential'].apply(
        lambda x: any(x.get(sector) is not None 
                     for sector in ['stationary_energy', 'transportation', 'waste', 'ippu', 'afolu'])
        if isinstance(x, dict) else False
    )
    
    # Actions to delete are mitigation actions with null GHG or no sector values
    deleted_actions = df[is_mitigation & (null_ghg | ~has_ghg_value)]
    
    # Keep all other actions
    updated_actions = df[~(is_mitigation & (null_ghg | ~has_ghg_value))]
    
    return updated_actions, deleted_actions

def main():
    # ======== Configuration =========
    # Set paths using pathlib
    script_dir = Path(__file__).parent
    base_dir = script_dir.parent / 'data/climate_actions/output'
    output_dir = script_dir / 'script_outputs'

    # Create scripts_outputs directory if it doesn't exist
    output_dir.mkdir(exist_ok=True)

    # Set input and output file paths
    file_path = base_dir / 'merged.json'
    updated_file_path = output_dir / 'updated_merged.json'
    deleted_file_path = output_dir / 'deleted_actions.json'

    # ======== Load Data =========
    df = pd.read_json(file_path)

    # Choose which filter to use (uncomment one)
    # updated_actions, deleted_actions = filter_empty_adaptation_effectiveness(df)
    updated_actions, deleted_actions = filter_empty_mitigation_ghg(df)

    # ======== Output and Save Results =========
    print("List of Deleted Actions:")
    print(deleted_actions)
    print(f"\nNumber of deleted actions: {len(deleted_actions)}")
    print(f"Number of remaining actions: {len(updated_actions)}")

    # Save the updated actions list to a new JSON file.
    updated_actions.to_json(updated_file_path, orient='records', lines=True)
    print(f"\nUpdated actions list saved to: {updated_file_path}")

    # Save the deleted actions list to its own JSON file.
    deleted_actions.to_json(deleted_file_path, orient='records', lines=True)
    print(f"Deleted actions list saved to: {deleted_file_path}")

if __name__ == "__main__":
    main()