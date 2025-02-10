from prioritizer.prioritizer import quantitative_score
from reading_writing_data import read_city_inventory, read_actions
import pandas as pd
import glob
import os
import glob
from pathlib import Path
import json
import sys

folder_path = Path(__file__).parent.parent.parent / "data" / "expert_labeled_actions"

# Get the absolute path to the project root (two levels up from this file)
project_root = str(Path(__file__).resolve().parent.parent.parent)

# Add the project root to the Python path
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def load_data_from_folder(folder_path):
    """
    Reads all JSON files in the specified folder and returns a combined pandas DataFrame.
    Assumes each JSON file contains a list of comparison dictionaries.
    """
    all_data = []
    json_files = glob.glob(os.path.join(folder_path, "*.json"))
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


def get_action_by_id(actions, target_action_id):

    for action in actions:
        if action.get("ActionID") == target_action_id:
            return action
    return None


# Load all comparison data from the folder
df_all_comparisons = load_data_from_folder(folder_path)

print(df_all_comparisons.head())

print(len(df_all_comparisons))

# Delete the irrelevant and unsure comparisons
df_all_comparisons_cleaned = df_all_comparisons[
    df_all_comparisons["PreferredAction"] != "Irrelevant"
]
df_all_comparisons_cleaned = df_all_comparisons[
    df_all_comparisons["PreferredAction"] != "Unsure"
]

print(df_all_comparisons_cleaned.head())
print(len(df_all_comparisons_cleaned))

actions = read_actions()

score = 0

for index, row in df_all_comparisons_cleaned.iterrows():

    # print("\n\n\n")
    # print(f"Processing row {index}")
    # print("City locode: ", row["CityLocode"])
    # print("ActionID A: ", row["ActionA"])
    # print("ActionID B: ", row["ActionB"])
    # print("Expert label: ", row["PreferredAction"])

    # Read the city data for the comparison
    city_data = read_city_inventory(row["CityLocode"])
    actionA = row["ActionA"]
    actionB = row["ActionB"]

    # Get the actual actions object from the actionsID
    actionA_with_context = get_action_by_id(actions, actionA)
    actionB_with_context = get_action_by_id(actions, actionB)

    # Calculate the scoring based on the linear ranking system
    score_A = quantitative_score(city_data, actionA_with_context)
    score_B = quantitative_score(city_data, actionB_with_context)

    # print(f"Score for A is {score_A}")
    # print(f"Score for B is {score_B}")

    if score_A > score_B:
        predicted_label = actionA
    else:
        predicted_label = actionB

    # If prediction is correct, add 1 to the score
    if predicted_label == row["PreferredAction"]:
        score += 1

    # print("Prediction:")
    # print(f"Predicted label is {predicted_label}")
    # print(f"Actual label is {row["PreferredAction"]}")
    # print(f"Score is {score}")

    # print(df_all_comparisons["PreferredAction"])

# Calculate accuracy
accuracy = score / len(df_all_comparisons)

print(f"Accuracy is {accuracy}")
