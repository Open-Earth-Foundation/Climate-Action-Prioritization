"""
This script benchmarks the quantitative (linear) and qualitative ranking system against the expert labeled data.

Run this script as a module to make sure sub imports are properly resolved.
>> python -m prioritizer.utils.benchmarks
"""

import pandas as pd
from pathlib import Path
import json
import concurrent.futures
from prioritizer.prioritizer import quantitative_score, qualitative_score
from prioritizer.utils.reading_writing_data import read_city_inventory, read_actions
from prioritizer.utils.ml_comparator import ml_compare
from prioritizer.utils.majority_vote_comparator import majority_vote_compare


def load_data_from_folder(folder_path):
    """
    Reads all JSON files in the specified folder and returns a combined pandas DataFrame.
    Assumes each JSON file contains a list of comparison dictionaries.
    """
    all_data = []
    json_files = list(folder_path.glob("*.json"))
    if not json_files:
        print(f"No JSON files found in {folder_path}. Please check the folder path.")
        return pd.DataFrame()

    for file in json_files:
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
                # If the JSON file contains a list of dictionaries, extend the list.
                if isinstance(data, list):
                    all_data.extend(data)
                else:
                    print(f"Unrecognized data format in file: {file}")
        except Exception as e:
            print(f"Error reading {file}: {e}")

    df = pd.DataFrame(all_data)
    return df


def remove_irrelevant_rows(df, remove_unsure: bool) -> pd.DataFrame:
    """
    Removes rows where the 'PreferredAction' is 'Irrelevant'.
    If remove_unsure is True, also removes rows where the 'PreferredAction' is 'Unsure'.
    """

    df_cleaned = df[df["PreferredAction"] != "Irrelevant"]
    if remove_unsure:
        df_cleaned = df_cleaned[df_cleaned["PreferredAction"] != "Unsure"]

    return df_cleaned


def get_action_by_id(actions, target_action_id):
    """
    Returns the action dictionary with the specified ActionID from the list of actions.
    """

    for action in actions:
        if action.get("ActionID") == target_action_id:
            return action
    return None


def get_accuracy_expert_vs_quanti(df: pd.DataFrame, actions: list) -> float:

    skipped = []
    score = 0
    valid_comparisons = 0

    for _, row in df.iterrows():

        # Read the city data for the comparison
        city_data = read_city_inventory(row["CityLocode"])
        actionA = row["ActionA"]
        actionB = row["ActionB"]

        # Get the actual actions object from the actionsID (filling in the context)
        actionA_with_context = get_action_by_id(actions, actionA)
        actionB_with_context = get_action_by_id(actions, actionB)

        # Check if both actions were found
        if actionA_with_context and actionB_with_context:
            try:

                # Calculate the scoring based on the linear ranking system
                score_A = quantitative_score(city_data, actionA_with_context)
                score_B = quantitative_score(city_data, actionB_with_context)

                # Skip if scores are equal
                if score_A == score_B:
                    print(
                        f"Skipping comparison: Scores are equal for {actionA} and {actionB}."
                    )
                    skipped.append((actionA, actionB))
                    continue

                predicted_label = actionA if score_A > score_B else actionB

                # Count this as a valid comparison
                valid_comparisons += 1

                # If prediction is correct, add 1 to the score
                if predicted_label == row["PreferredAction"]:
                    score += 1
            except ValueError as e:
                print(f"Skipping comparison due to error: {e}")
                skipped.append((actionA, actionB))
        else:
            # Add the missing action to the skipped list to keep track of them
            if actionA_with_context is None:
                skipped.append(actionA)
            elif actionB_with_context is None:
                skipped.append(actionB)
            else:
                skipped.append(actionA)
                skipped.append(actionB)

            # print("Action not found. Probably removed from the action data.")
            # print("Skipping this comparison")
            continue

    print(f"\nSkipped {len(skipped)} comparisons due to missing actions.")
    print(f"Skipped actions: {set(skipped)}")
    print(f"Valid comparisons: {valid_comparisons}")

    # Calculate accuracy
    accuracy = score / valid_comparisons
    return accuracy


def get_accuracy_expert_vs_ml(df: pd.DataFrame, actions: list) -> float:

    skipped = []
    score = 0
    valid_comparisons = 0
    for _, row in df.iterrows():

        # Read the city data for the comparison
        city_data = read_city_inventory(row["CityLocode"])
        actionA = row["ActionA"]
        actionB = row["ActionB"]
        preferred_action = row["PreferredAction"]

        # Determine if ActionA or ActionB is preferred
        if preferred_action == actionA:
            preferred_action = 1
        elif preferred_action == actionB:
            preferred_action = -1
        else:
            # Throw error if the preferred action is not found in the comparison
            # This should never happen and is an actual error, therefore we throw an error and stop execution
            raise ValueError("Preferred action not found in the comparison.")

        # Get the actual actions object from the actionsID (filling in the context)
        actionA_with_context = get_action_by_id(actions, actionA)
        actionB_with_context = get_action_by_id(actions, actionB)

        # Check if both actions were found
        if actionA_with_context and actionB_with_context:

            # Calculate the scoring based on the ML model
            predicted_action = ml_compare(
                city_data, actionA_with_context, actionB_with_context
            )

            # Count this as a valid comparison
            valid_comparisons += 1

            # If prediction is correct, add 1 to the score
            if predicted_action == preferred_action:
                score += 1

            # input("Press Enter to continue 2")
        else:
            # Add the missing action to the skipped list to keep track of them
            if actionA_with_context is None:
                skipped.append(actionA)
            elif actionB_with_context is None:
                skipped.append(actionB)
            else:
                skipped.append(actionA)
                skipped.append(actionB)

            # print("Action not found. Probably removed from the action data.")
            # print("Skipping this comparison")
            continue

    print(f"\nSkipped {len(skipped)} comparisons due to missing actions.")
    print(f"Skipped actions: {set(skipped)}")
    print(f"Valid comparisons: {valid_comparisons}")

    # Calculate accuracy
    accuracy = score / valid_comparisons
    return accuracy


def get_accuracy_expert_vs_majority_vote(df: pd.DataFrame, actions: list) -> float:
    skipped = []
    score = 0
    valid_comparisons = 0

    for _, row in df.iterrows():
        # Read city data for the comparison
        city_data = read_city_inventory(row["CityLocode"])
        actionA = row["ActionA"]
        actionB = row["ActionB"]
        preferred_action = row["PreferredAction"]

        # print(f"\nCity: {row['CityLocode']}")
        # print(f"Action A: {actionA}")
        # print(f"Action B: {actionB}")
        # print(f"Preferred action: {preferred_action}")

        # Determine if ActionA or ActionB is preferred
        if preferred_action == actionA:
            preferred_action = 1
        elif preferred_action == actionB:
            preferred_action = -1
        else:
            raise ValueError("Preferred action not found in the comparison.")

        # Get the actual action objects from the action IDs
        actionA_with_context = get_action_by_id(actions, actionA)
        actionB_with_context = get_action_by_id(actions, actionB)

        # Ensure both actions exist before proceeding
        if actionA_with_context and actionB_with_context:
            try:
                # Use the majority vote method for comparison
                predicted_action = majority_vote_compare(
                    city_data, actionA_with_context, actionB_with_context
                )

                # Count this as a valid comparison
                valid_comparisons += 1

                # If the prediction matches the preferred action, increase score
                if predicted_action == preferred_action:
                    score += 1

            except ValueError as e:
                print(f"Skipping comparison due to error: {e}")
                skipped.append((actionA, actionB))

        else:
            # Track missing actions
            if actionA_with_context is None:
                skipped.append(actionA)
            if actionB_with_context is None:
                skipped.append(actionB)

            # print("Action not found. Skipping this comparison.")
            continue

    print(f"\nSkipped {len(skipped)} comparisons due to missing actions or errors.")
    print(f"Skipped actions: {set(skipped)}")
    print(f"Valid comparisons: {valid_comparisons}")

    # Compute accuracy (avoid division by zero)
    accuracy = score / valid_comparisons
    return accuracy


def process_row_quali(index, row, actions):
    """Helper function for parallelized qualitative accuracy computation."""

    print(f"Processing row {index}")
    print("City locode: ", row["CityLocode"])
    print("ActionID A: ", row["ActionA"])
    print("ActionID B: ", row["ActionB"])
    print("Expert label: ", row["PreferredAction"])

    # Read the city data for the comparison
    city_data = read_city_inventory(row["CityLocode"])
    actionA = row["ActionA"]
    actionB = row["ActionB"]

    actionA_with_context = get_action_by_id(actions, actionA)
    actionB_with_context = get_action_by_id(actions, actionB)

    if actionA_with_context and actionB_with_context:
        # Calculate the scoring based on the qualitative ranking system
        qual_score = qualitative_score(
            city_data, [actionA_with_context, actionB_with_context]
        )

        if qual_score:
            winner = qual_score.actions[0].action_id
            print(f"Winner: {winner}")

            predicted_label = winner

            return 1 if predicted_label == row["PreferredAction"] else 0
    return None  # Skip this row if any issue occurs


def get_accuracy_expert_vs_quali(df: pd.DataFrame, actions: list) -> float:
    """Parallelized accuracy calculation for qualitative ranking."""

    skipped = 0
    score = 0

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=70
    ) as executor:  # Adjust max_workers if needed
        future_to_index = {
            executor.submit(process_row_quali, index, row, actions): index
            for index, row in df.iterrows()
        }

        for future in concurrent.futures.as_completed(future_to_index):
            result = future.result()
            if result is not None:
                score += result
            else:
                skipped += 1

    print(f"\nSkipped {skipped} comparisons due to missing actions or errors.")

    # Calculate accuracy
    accuracy = score / len(df)
    return accuracy


if __name__ == "__main__":

    # Define the folder to read all the expert labeled comparison data
    folder_path = (
        Path(__file__).parent.parent.parent / "data" / "expert_labeled_actions"
    )

    # Load all comparison data from the folder
    df_all_comparisons = load_data_from_folder(folder_path)

    print(df_all_comparisons.head())
    print(len(df_all_comparisons))

    df_all_comparisons_cleaned = remove_irrelevant_rows(
        df_all_comparisons, remove_unsure=True
    )

    print(df_all_comparisons_cleaned.head())
    print(len(df_all_comparisons_cleaned))

    actions = read_actions()

    accuracy_quanti = get_accuracy_expert_vs_quanti(df_all_comparisons_cleaned, actions)
    print(f"\nAccuracy for quantitative ranking is {accuracy_quanti}\n\n")

    accuracy_ml = get_accuracy_expert_vs_ml(df_all_comparisons_cleaned, actions)
    print(f"\nAccuracy for ML ranking is {accuracy_ml}\n\n")

    # accuracy_quali = get_accuracy_expert_vs_quali(df_all_comparisons_cleaned, actions)
    # print(f"\nAccuracy for qualitative ranking is {accuracy_quali}\n\n")

    accuracy_majority_vote = get_accuracy_expert_vs_majority_vote(
        df_all_comparisons_cleaned, actions
    )
    print(f"\nAccuracy for majority vote ranking is {accuracy_majority_vote}\n\n")

    # Final print out to not get lost in all the intermediate print statements
    print("Final result:\n")
    print(f"Accuracy for quantitative ranking is {accuracy_quanti}\n")
    print(f"Accuracy for ML ranking is {accuracy_ml}\n")
    # print(f"Accuracy for qualitative ranking is {accuracy_quali}\n")
    print(f"Accuracy for majority vote ranking is {accuracy_majority_vote}\n")
