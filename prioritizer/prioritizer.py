"""
This file is the main file for the prioritizer.
It is used to prioritize climate actions for a given city.

It uses the following files:
- reading_writing_data.py: for reading and writing data to files
- additional_scoring_functions.py: for additional scoring functions
- prompt.py: for the prompt
- ml_comparator.py: for the ML comparator
- get_actions.py: for getting the actions from the API

Usage:
python prioritizer.py --locode <locode>

Example:
Run it from the root level of the project with the following command:

python -m prioritizer.prioritizer --locode "BR CXL"
"""

import argparse
import sys
import os
import random
from dotenv import load_dotenv
from openai import OpenAI
import json
from pydantic import BaseModel
from typing import List
from pathlib import Path
from prioritizer.utils.reading_writing_data import (
    read_city_inventory,
    write_output,
)
from prioritizer.utils.ml_comparator import ml_compare
from scripts.get_actions import get_actions
import logging

logger = logging.getLogger(__name__)

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
#client = OpenAI(api_key=api_key)

def filter_actions_by_biome(actions: list[dict], city: dict) -> list[dict]:
    """
    Filter actions based on city's biome only if both city and action have biomes defined.
    Actions without a biome field are included in the output.
    If city has no biome, return all actions unfiltered.
    """
    city_biome = city.get("biome")

    actions_final = []
    skipped_actions = 0
    if not city_biome:
        return actions
    else:
        logging.debug(f"City biome: {city_biome}")

        for action in actions:
            action_biome = action.get("biome")
            logging.debug(f"Action biome: {action_biome}")
            if action_biome:
                # If the action biome matches the city biome, add the action to the list
                if action_biome == city_biome:
                    actions_final.append(action)
                else:
                    # If the action biome does not match the city biome, skip the action
                    # and increment the counter
                    skipped_actions += 1
                    continue
            else:
                # If there is no biome, add the action to the list
                actions_final.append(action)

    logging.debug(f"actions skipped: {skipped_actions}")
    return actions_final


def ML_compare(actionA, actionB, city):
    """
    Uses the ML model to compare two actions in a given city context.
    Returns:
       1 if actionA is better
      -1 if actionB is better
    """
    result = ml_compare(city, actionA, actionB)
    return result


def single_elimination_bracket(actions, city):
    """
    Performs a single-elimination bracket on the given list of actions,
    with a wildcard if there's an odd number of participants.

    Returns:
      winner  - the single best from this bracket
      losers  - all other participants (who lost at some stage)
    """
    if not actions:
        return None, []

    # print(f"\n--- Starting bracket with {len(actions)} actions ---")

    # Shuffle to randomize the pairs
    random.shuffle(actions)

    # If odd number of actions, pick one as wildcard (auto-advance)
    wildcard = None
    if len(actions) % 2 == 1:
        wildcard = actions.pop()
        # print(
        #     f"  Odd number of actions, wildcard: {wildcard.get('ActionID', 'Unknown')}"
        # )

    winners = []
    losers = []

    # Pair up
    for i in range(0, len(actions), 2):
        if i + 1 < len(actions):  # Make sure we have a pair
            actionA = actions[i]
            actionB = actions[i + 1]

            try:
                # Use your ML model to compare
                result = ML_compare(actionA, actionB, city)
                if result == 1:
                    winners.append(actionA)
                    losers.append(actionB)
                else:
                    winners.append(actionB)
                    losers.append(actionA)
            except Exception as e:
                logging.error(f"Error comparing actions: {e}")
                # If there's an error, continue to the next pair
                # This way we ignore pairs with one or both actions containing missing values
                # Since actions get shuffled, over time we will have enough pairings without missing values
                # Valid actions that were initially paired with actions containing missing values will be paired later again
                # This way no valid actions are excluded from the tournament
                continue

    # If there was a wildcard, it automatically advances
    if wildcard:
        winners.append(wildcard)
        # print(
        #     f"  Wildcard {wildcard.get('ActionID', 'Unknown')} automatically advances"
        # )

    # print(f"  Round complete. {len(winners)} winners advancing to next round")

    # If exactly one winner, we found the bracket winner
    if len(winners) == 1:
        # print(f"  Final winner of bracket: {winners[0].get('ActionID', 'Unknown')}")
        return winners[0], losers
    else:
        # Otherwise, recursively determine a single winner
        # print(f"  Moving to next round with {len(winners)} actions")
        # Recursive call to fihishn round
        final_winner, final_losers = single_elimination_bracket(winners, city)
        return final_winner, losers + final_losers


def final_bracket_for_ranking(actions, city):
    """
    When we have fewer than 40 participants left, we do a final bracket
    that fully orders them from best to worst.

    This simply calls single_elimination_bracket repeatedly until no
    participants remain, collecting winners in order.

    Returns:
      ranking (list): from best to worst among the given actions.
    """
    # print(
    #     f"\n=== Starting final bracket for complete ranking with {len(actions)} actions ==="
    # )
    participants = actions[:]
    ranking = []
    rank = 1

    while participants:
        # print(
        #     f"\n--- Finding #{rank} ranked action from {len(participants)} remaining ---"
        # )
        winner, losers = single_elimination_bracket(participants, city)
        if not winner:
            logging.debug("  No winner found, breaking")
            break  # no more participants

        logging.debug(f"  Rank #{rank}: {winner.get('ActionID', 'Unknown')}")
        ranking.append(winner)
        participants = losers
        rank += 1

    logging.debug(f"=== Final bracket complete. Ranked {len(ranking)} actions ===")
    return ranking


def tournament_ranking(actions, city):
    """
    Repeatedly runs single elimination brackets, where losers compete in subsequent brackets
    to determine the next ranks. Continues until we have top 20 ranked actions.

    Returns:
      A list of (action, rank_index).
    """
    logging.info(
        f"\n\n========== STARTING TOURNAMENT RANKING WITH {len(actions)} ACTIONS =========="
    )
    remaining = actions[:]
    full_ranking = []
    current_rank = 1

    while remaining and current_rank <= 20:
        # print(
        #     f"\n--- Running bracket for rank #{current_rank} with {len(remaining)} actions ---"
        # )
        winner, losers = single_elimination_bracket(remaining, city)

        if not winner:
            # TODO is there a normal thing that this can happen ?or should this be error
            logging.debug("No winner found, breaking")
            break

        # Add the winner with their rank
        logging.debug(f"Rank #{current_rank}: {winner.get('ActionID', 'Unknown')}")
        full_ranking.append((winner, current_rank))
        current_rank += 1

        # Losers compete in the next bracket
        remaining = losers
        # print(f"{len(remaining)} actions will compete for rank #{current_rank}")

    logging.info(
        f"\n========== TOURNAMENT RANKING COMPLETE. RANKED {len(full_ranking)} ACTIONS =========="
    )

    # Print final ranking summary
    logging.info("\nFinal Ranking Summary:")
    for action, rank in full_ranking:
        logging.info(f"  #{rank}: {action.get('ActionID', 'Unknown')}")

    return full_ranking


def main(locode: str):
    try:
        city = read_city_inventory(locode)

        # Create function here that gets all the city data from the APIs and stores it in 'city' object
        # This will substitute the city_data.json file

        # Use the API to get the actions
        actions = get_actions()
        logging.debug(json.dumps(actions, indent=2))

    except Exception as e:
        logging.error("Error reading data:", e)
        sys.exit(1)

    if not actions:
        logging.error("No actions data found from API.")
        sys.exit(1)

    if not city:
        logging.error("No city data found")
        sys.exit(1)

    # Filter actions by biome if applicable
    filtered_actions = filter_actions_by_biome(actions, city)
    logging.info(f"After biome filtering: {len(filtered_actions)} actions remain")

    # Separate adaptation and mitigation actions
    adaptation_actions = [
        action
        for action in filtered_actions
        if action.get("ActionType") is not None
        and isinstance(action["ActionType"], list)
        and "adaptation" in action["ActionType"]
    ]
    mitigation_actions = [
        action
        for action in filtered_actions
        if action.get("ActionType") is not None
        and isinstance(action["ActionType"], list)
        and "mitigation" in action["ActionType"]
    ]

    logging.info(
        f"Found {len(adaptation_actions)} adaptation actions and {len(mitigation_actions)} mitigation actions"
    )

    # Apply tournament ranking for adaptation actions
    logging.info("Starting tournament ranking for adaptation actions...")
    adaptation_ranking = tournament_ranking(adaptation_actions, city)

    # Format adaptation results
    top_ml_adaptation = []
    for action, rank in adaptation_ranking:
        top_ml_adaptation.append(
            {
                "locode": city.get("locode", "Unknown"),
                "cityName": city.get("name", "Unknown City"),
                "region": city.get("region", "Unknown"),
                "regionName": city.get("regionName", "Unknown"),
                "actionId": action.get("ActionID", "Unknown"),
                "actionName": action.get("ActionName", "Unknown"),
                "actionPriority": rank,
                "explanation": f"Ranked #{rank} by tournament ranking algorithm",
            }
        )

    # Apply tournament ranking for mitigation actions
    logging.debug("Starting tournament ranking for mitigation actions...")
    mitigation_ranking = tournament_ranking(mitigation_actions, city)

    # Format mitigation results
    top_ml_mitigation = []
    for action, rank in mitigation_ranking:
        top_ml_mitigation.append(
            {
                "locode": city.get("locode", "Unknown"),
                "cityName": city.get("name", "Unknown City"),
                "region": city.get("region", "Unknown"),
                "regionName": city.get("regionName", "Unknown"),
                "actionId": action.get("ActionID", "Unknown"),
                "actionName": action.get("ActionName", "Unknown"),
                "actionPriority": rank,
                "explanation": f"Ranked #{rank} by tournament ranking algorithm",
            }
        )

    # Save outputs to separate files
    write_output(top_ml_adaptation, f"output_{locode}_adaptation.json")
    write_output(top_ml_mitigation, f"output_{locode}_mitigation.json")
    logging.debug("Prioritization complete!")


if __name__ == "__main__":
    from logger_config import setup_logger

    setup_logger(level=logging.INFO)

    parser = argparse.ArgumentParser(
        description="Prioritize climate actions for a given city."
    )
    parser.add_argument(
        "--locode",
        type=str,
        required=True,
        help="The UN/LOCODE of the city for which to prioritize actions.",
    )
    args = parser.parse_args()

    main(locode=args.locode)
