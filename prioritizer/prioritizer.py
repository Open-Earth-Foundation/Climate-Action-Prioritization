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
    read_actions,
    write_output,
)
from prioritizer.utils.additional_scoring_functions import (
    count_matching_hazards,
    find_highest_emission,
)
from prioritizer.utils.prompt import return_prompt
from prioritizer.utils.ml_comparator import ml_compare

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

scale_scores = {
    "Very High": 1.0,
    "High": 0.75,
    "Medium": 0.5,
    "Low": 0.25,
    "Very Low": 0.0,
}
scale_adaptation_effectiveness = {"low": 0.33, "medium": 0.66, "high": 0.99}

# Define the mapping for timeline options
timeline_mapping = {"<5 years": 1.0, "5-10 years": 0.5, ">10 years": 0}
ghgi_potential_mapping = {
    "0-19": 0.20,
    "20-39": 0.4,
    "40-59": 0.6,
    "60-79": 0.8,
    "80-100": 1.0,
}


def calculate_emissions_reduction(city, action):
    # Define the mapping for percentage ranges
    reduction_mapping = {
        "0-19": 0.1,
        "20-39": 0.3,
        "40-59": 0.5,
        "60-79": 0.7,
        "80-100": 0.9,
    }
    # Initialize total emissions reduction
    total_reduction = 0

    # Get the GHGReductionPotential from the action
    ghg_potential = action.get("GHGReductionPotential", {})
    if not ghg_potential:
        # print("There was no GHGReductionPotential")
        return 0

    # Define the sectors and corresponding city emissions keys
    sectors = {
        "stationary_energy": "stationaryEnergyEmissions",
        "transportation": "transportationEmissions",
        "waste": "wasteEmissions",
        "ippu": "industrialProcessEmissions",
        "afolu": "landUseEmissions",
    }

    # Iterate over the sectors
    for sector, city_emission_key in sectors.items():
        reduction_str = ghg_potential.get(sector) if ghg_potential else None
        if reduction_str is None:
            continue
        elif reduction_str and reduction_str in reduction_mapping:
            # print("Reduction string:", reduction_str)
            # print("Reduction mapping:", reduction_mapping[reduction_str])
            reduction_percentage = reduction_mapping[reduction_str]
            city_emission = city.get(city_emission_key, 0)
            # print("City emission: " + str(city_emission) + " for " + city_emission_key)
            reduction_amount = city_emission * reduction_percentage
            total_reduction += reduction_amount

    return total_reduction


def quantitative_score(city, action):
    """
    Calculates a quantitative score for a given action in a city based on several criteria.
    The score is calculated as follows:
    1. Emissions reduction score: Based on the GHG reduction potential of the action.
    2. Adaptation effectiveness score: Based on the adaptation effectiveness of the action.
    3. Time in years score: Based on the timeline for implementation of the action.
    4. Cost score: Based on the budget of the city.
    Args:
        city (dict): A dictionary containing information about the city, including its budget.
        action (dict): A dictionary containing information about the action, including GHG reduction potential, adaptation effectiveness, and timeline for implementation.
    Returns:
        float: The calculated quantitative score for the action.
    """

    def load_weights():
        # Get the directory of the current script (prioritizer.py)
        script_dir = Path(__file__).resolve().parent

        # Construct the full path to the weights.json file
        weights_path = script_dir / "CAP_data" / "weights.json"

        # weights_path = "CAP_data/weights.json"
        with open(weights_path, "r", encoding="utf-8") as f:
            weights = json.load(f)
        return weights

    weights = load_weights()
    score = 0
    # Hazard calculation -  agreed adding the hazard into the city data and filtering it from them to see how many match
    # there should be weights adjusted for the hazards based on CCRA data listing the most important ones for the city
    matching_hazards_count = count_matching_hazards(city, action)
    if matching_hazards_count > 0:
        hazards_weight = weights.get("Hazard", 1)
        # check if it's not 0
        score += matching_hazards_count * hazards_weight
    # print("Score after hazard:", score)

    # Dependencies - caculate the number of dependencies and give a minus score based on that very low impact
    dependencies = action.get("Dependencies", [])
    dependencies_weights = weights.get("Dependencies", 1)
    if isinstance(dependencies, list):
        score -= round(len(dependencies) * dependencies_weights, 3)
    # print("Score after dependencies:", score)
    # ActionName - pass
    # AdaptationCategory - pass this time
    # Subsector - skip for now maybe more data needed as now we are covering per sector
    # PrimaryPurpose - use only for LLM

    # Sector - if it matches the most emmissions intensive sectors gets bonus points
    total_emission_reduction_all_sectors = calculate_emissions_reduction(city, action)
    # print(
    #     "Total emissions reduction for all sectors:",
    #     total_emission_reduction_all_sectors,
    # )
    weights_emissions = weights.get("GHGReductionPotential", 1)
    if total_emission_reduction_all_sectors > 0:
        total_emissions = city.get("totalEmissions", 1)  # Avoid division by zero
        # print("Total emissions of a city:", total_emissions)
        reduction_percentage = total_emission_reduction_all_sectors / total_emissions
        # print("Reduction percentage:", reduction_percentage)
        score += round(reduction_percentage * weights_emissions, 3)
    # print("Score after emissions reduction:", score)

    # Calculate for every sector
    weights_emissions = weights.get("GHGReductionPotential", 1)
    most_emissions, percentage_emissions_value = find_highest_emission(city)
    if action.get("Sector") == most_emissions:
        score += (percentage_emissions_value / 100) * weights_emissions
    # print("Score after sector emission reduction:", score)
    # InterventionType - skip for now
    # Description - use only for LLM
    # BehavioralChangeTargeted - skip for now

    # Adaptation effectiveness score - skip adding score if value is null or zero
    adaptation_effectiveness = action.get("AdaptationEffectiveness")
    if adaptation_effectiveness in scale_adaptation_effectiveness:
        effective_value = scale_adaptation_effectiveness[adaptation_effectiveness]
        if effective_value:  # Only add score if effective_value is non-zero (non-falsy)
            adaptation_weight = weights.get("AdaptationEffectiveness", 1)
            score += effective_value * adaptation_weight
    # print("Score after adaptation effectiveness:", score)

    # Time in years score
    timeline_str = action.get("TimelineForImplementation", "")
    if timeline_str is None:
        pass
    elif timeline_str in timeline_mapping:
        time_score_weight = weights.get("TimelineForImplementation", 1)
        time_score = timeline_mapping[timeline_str]
        score += time_score * time_score_weight
    else:
        print("Invalid timeline:", timeline_str)

    # print("Score after time in years:", score)

    # Cost score
    if "CostInvestmentNeeded" in action:
        cost_investment_needed = action["CostInvestmentNeeded"]
        cost_score_weight = weights.get("CostInvestmentNeeded", 1)
        cost_score = scale_adaptation_effectiveness.get(cost_investment_needed, 0)
        score += cost_score * cost_score_weight

    # print("Score after cost:", score)
    # print("-------------")
    return score


class Action(BaseModel):
    action_id: str
    action_name: str
    actionPriority: int
    explanation: str
    city_name: str


class PrioritizedActions(BaseModel):
    actions: List[Action]


def send_to_llm2(prompt):

    response = client.beta.chat.completions.parse(
        model="gpt-4o-2024-08-06",
        messages=[
            {"role": "user", "content": prompt},
        ],
        response_format=PrioritizedActions,
        temperature=0.0,
    )
    return response.choices[0].message.parsed


def send_to_llm(prompt: str) -> PrioritizedActions:
    # Using the o3-mini reasoning model and no max_tokens parameter.
    response = client.beta.chat.completions.parse(
        model="o3-mini",  # Changed from gpt-4o to o3-mini.
        messages=[
            {"role": "user", "content": prompt},
        ],
        # Specify structured output using the Pydantic class.
        response_format=PrioritizedActions,
    )
    # Return the parsed structured output.
    return response.choices[0].message.parsed  # type: ignore


def qualitative_score(city, action):
    prompt = return_prompt(action, city)
    llm_response = send_to_llm(prompt)
    return llm_response


def quantitative_prioritizer(cities, actions):
    all_scores = []

    for action in actions:
        quant_score = quantitative_score(cities, action)
        all_scores.append(
            {
                "city": cities.get("name", "Unknown City"),
                "action_id": action[
                    "ActionID"
                ],  # Use ActionID for unique identification
                "action_type": (
                    action["ActionType"][0] if action["ActionType"] else "Unknown"
                ),
                "action_name": action["ActionName"],
                "quantitative_score": quant_score,
            }
        )

    sorted_scores = sorted(
        all_scores, key=lambda x: x["quantitative_score"], reverse=True
    )

    # Filter Adaptation and Mitigation actions
    adaptation_actions = [
        score for score in sorted_scores if score["action_type"] == "adaptation"
    ]
    mitigation_actions = [
        score for score in sorted_scores if score["action_type"] == "mitigation"
    ]

    # Return top 15 for each category
    return adaptation_actions[:20], mitigation_actions[:20]


def qualitative_prioritizer(top_quantitative, actions, city):
    print("Qualitative prioritization started...")
    qualitative_scores = []
    city_name = city.get("name", "Unknown City")
    city_locode = city.get("locode", "Unknown")
    city_region = city.get("region", "Unknown")
    city_regionName = city.get("regionName", "Unknown")
    llm_output = qualitative_score(city, top_quantitative)

    if llm_output:

        for action in llm_output.actions:
            qualitative_scores.append(
                {
                    "locode": city_locode,
                    "cityName": city_name,
                    "region": city_region,
                    "regionName": city_regionName,
                    "actionId": action.action_id,
                    "actionName": action.action_name,
                    "actionPriority": action.actionPriority,
                    "explanation": action.explanation,
                }
            )
        print("Qualitative prioritization completed.")
        return qualitative_scores
    else:
        print("No qualitative prioritization data.")
        return []


def filter_actions_by_biome(actions, city):
    """
    Filter actions based on city's biome only if both city and action have biomes defined.
    Actions without a biome field are included in the output.
    If city has no biome, return all actions unfiltered.
    """
    city_biome = city.get("biome")
    if not city_biome:
        return actions

    # Keep actions that either:
    # 1. Don't have a biome field, or
    # 2. Have a biome that matches the city's biome
    return [action for action in actions if 
            "Biome" not in action or action["Biome"] == city_biome]


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

    print(f"\n--- Starting bracket with {len(actions)} actions ---")
    
    # Shuffle to randomize the pairs
    random.shuffle(actions)

    # If odd number of actions, pick one as wildcard (auto-advance)
    wildcard = None
    if len(actions) % 2 == 1:
        wildcard = actions.pop()
        print(f"  Odd number of actions, wildcard: {wildcard.get('ActionID', 'Unknown')}")

    winners = []
    losers = []

    # Pair up
    for i in range(0, len(actions), 2):
        if i + 1 < len(actions):  # Make sure we have a pair
            actionA = actions[i]
            actionB = actions[i + 1]
            
            
            # Use your ML model to compare
            result = ML_compare(actionA, actionB, city)
            if result == 1:
                winners.append(actionA)
                losers.append(actionB)
            else:
                winners.append(actionB)
                losers.append(actionA)

    # If there was a wildcard, it automatically advances
    if wildcard:
        winners.append(wildcard)
        print(f"  Wildcard {wildcard.get('ActionID', 'Unknown')} automatically advances")

    print(f"  Round complete. {len(winners)} winners advancing to next round")
    
    # If exactly one winner, we found the bracket winner
    if len(winners) == 1:
        print(f"  Final winner of bracket: {winners[0].get('ActionID', 'Unknown')}")
        return winners[0], losers
    else:
        # Otherwise, recursively determine a single winner
        print(f"  Moving to next round with {len(winners)} actions")
        #Recursive call to fihishn round
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
    print(f"\n=== Starting final bracket for complete ranking with {len(actions)} actions ===")
    participants = actions[:]
    ranking = []
    rank = 1

    while participants:
        print(f"\n--- Finding #{rank} ranked action from {len(participants)} remaining ---")
        winner, losers = single_elimination_bracket(participants, city)
        if not winner:
            print("  No winner found, breaking")
            break  # no more participants
        
        print(f"  Rank #{rank}: {winner.get('ActionID', 'Unknown')}")
        ranking.append(winner)
        participants = losers
        rank += 1

    print(f"=== Final bracket complete. Ranked {len(ranking)} actions ===")
    return ranking

def tournament_ranking(actions, city):
    """
    Repeatedly runs single elimination brackets, where losers compete in subsequent brackets
    to determine the next ranks. Continues until we have top 20 ranked actions.

    Returns:
      A list of (action, rank_index).
    """
    print(f"\n\n========== STARTING TOURNAMENT RANKING WITH {len(actions)} ACTIONS ==========")
    remaining = actions[:]
    full_ranking = []
    current_rank = 1

    while remaining and current_rank <= 20:
        print(f"\n--- Running bracket for rank #{current_rank} with {len(remaining)} actions ---")
        winner, losers = single_elimination_bracket(remaining, city)
        
        if not winner:
            #TODO is there a normal thing that this can happen ?or should this be error 
            print("No winner found, breaking")
            break

        # Add the winner with their rank
        print(f"Rank #{current_rank}: {winner.get('ActionID', 'Unknown')}")
        full_ranking.append((winner, current_rank))
        current_rank += 1

        # Losers compete in the next bracket
        remaining = losers
        print(f"{len(remaining)} actions will compete for rank #{current_rank}")

    print(f"\n========== TOURNAMENT RANKING COMPLETE. RANKED {len(full_ranking)} ACTIONS ==========")
    
    # Print final ranking summary
    print("\nFinal Ranking Summary:")
    for action, rank in full_ranking:
        print(f"  #{rank}: {action.get('ActionID', 'Unknown')}")
    
    return full_ranking


def main(locode: str):
    try:
        city = read_city_inventory(locode)
        actions = read_actions()
    except Exception as e:
        print("Error reading data:", e)
        sys.exit(1)

    # Filter actions by biome if applicable
    filtered_actions = filter_actions_by_biome(actions, city)
    print(f"After biome filtering: {len(filtered_actions)} actions remain")

    # Separate adaptation and mitigation actions
    adaptation_actions = [
        action for action in filtered_actions 
        if action.get("ActionType") and "adaptation" in action.get("ActionType")
    ]
    mitigation_actions = [
        action for action in filtered_actions 
        if action.get("ActionType") and "mitigation" in action.get("ActionType")
    ]
    
    print(f"Found {len(adaptation_actions)} adaptation actions and {len(mitigation_actions)} mitigation actions")

    # Apply tournament ranking for adaptation actions
    print("Starting tournament ranking for adaptation actions...")
    adaptation_ranking = tournament_ranking(adaptation_actions, city)
    
    # Format adaptation results
    top_ml_adaptation = []
    for action, rank in adaptation_ranking:
        top_ml_adaptation.append({
            "locode": city.get("locode", "Unknown"),
            "cityName": city.get("name", "Unknown City"),
            "region": city.get("region", "Unknown"),
            "regionName": city.get("regionName", "Unknown"),
            "actionId": action.get("ActionID", "Unknown"),
            "actionName": action.get("ActionName", "Unknown"),
            "actionPriority": rank,
            "explanation": f"Ranked #{rank} by tournament ranking algorithm"
        })
    
    # Apply tournament ranking for mitigation actions
    print("Starting tournament ranking for mitigation actions...")
    mitigation_ranking = tournament_ranking(mitigation_actions, city)
    
    # Format mitigation results
    top_ml_mitigation = []
    for action, rank in mitigation_ranking:
        top_ml_mitigation.append({
            "locode": city.get("locode", "Unknown"),
            "cityName": city.get("name", "Unknown City"),
            "region": city.get("region", "Unknown"),
            "regionName": city.get("regionName", "Unknown"),
            "actionId": action.get("ActionID", "Unknown"),
            "actionName": action.get("ActionName", "Unknown"),
            "actionPriority": rank        
            })

    # Save outputs to separate files
    write_output(top_ml_adaptation, f"output_{locode}_adaptation.json")
    write_output(top_ml_mitigation, f"output_{locode}_mitigation.json")
    print("Prioritization complete!")


if __name__ == "__main__":
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
