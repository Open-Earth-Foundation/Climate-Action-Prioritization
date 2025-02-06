from typing import List
from pydantic import BaseModel
import openai
import os
import random
from utils.prompt import return_prompt
from dotenv import load_dotenv

load_dotenv()
# Load OpenAI API Key
api_key = os.getenv("OPENAI_API_KEY")
client = openai

# Define Pydantic Schema
class Action(BaseModel):
    Action_ID: str
    Action_Name: str
    ActionPriority: int
    Explanation: str
    City_Name: str

class PrioritizedActions(BaseModel):
    actions: List[Action]

# Function to send prompt to LLM
def send_to_llm(prompt):
    #TODO implement it as a conversation where previous part of the round is in memory 
    response = client.beta.chat.completions.parse(
        model="gpt-4o-2024-08-06",
        messages=[
            {"role": "user", "content": prompt},
        ],
        response_format=Action,
        temperature=0.0,
    )
    return response.choices[0].message.parsed

def run_round(actions, city):
    next_round = []
    random.shuffle(actions)
    for i in range(0, len(actions), 2):
        if i + 1 < len(actions):
            action1, action2 = actions[i], actions[i + 1]
            prompt = return_prompt([action1, action2], city)
            result = send_to_llm(prompt)
            winner = result
            next_round.append(winner)
        else:
            next_round.append(actions[i])
    return next_round

# Function to pair actions and rank them
def pair_and_rank(actions, city):
    """
    Pair actions and invoke the LLM to decide winners in a tournament style.

    Args:
        actions (List[dict]): List of actions to rank.
        city (dict): City data for contextual prioritization.

    Returns:
        List[dict]: Fully ranked top 5 actions.
    """

    # First round: Top 20 to Top 10
    actions = run_round(actions, city)

    # Second round: Top 10 to Top 5
    actions = run_round(actions, city)

    # Final round: Rank Top 5
    rankings = []
    while actions:
        if len(actions) == 1:
            rankings.append(actions.pop())
        else:
            action1 = actions.pop(0)
            action2 = actions.pop(0)
            prompt = return_prompt([action1, action2], city)
            result = send_to_llm(prompt)
            print ("Result llm call: \n", result)
            winner = result
            loser = next(
                action for action in [action1, action2] if action.Action_ID != result.Action_ID
            )
            rankings.append(winner)
            actions.append(loser)

    return rankings

# Main function to run tournament ranking
def tournament_rank(actions, city):
    """
    Execute a tournament-based ranking of actions.

    Args:
        actions (List[dict]): List of actions to rank.
        city (dict): City data.

    Returns:
        List[dict]: Fully ranked list of actions.
    """
    ranked_actions = pair_and_rank(actions, city)
    print("Ranked actions: ", ranked_actions)
    # Format results to comply with Pydantic schema
    final_ranked_list = []
    for idx, action in enumerate(ranked_actions):
        final_ranked_list.append(
            {
                "action_id": action.Action_ID,
                "action_name": action.Action_Name,
                "actionPriority": idx + 1,
                "explanation": action.Explanation,
                "city_name": city["name"],
            }
        )
    print("Final ranked list: ", final_ranked_list)
    return final_ranked_list
