"""
This script translates the climate actions into the specified language.

It translates all text values while maintaining consistency for enum values.
Numeric values are not translated.

Execute the script with the following command:
python scripts/translate_actions.py --language <language_code>

Example:
python scripts/translate_actions.py --language es
"""

import argparse
import json
import os
import logging
from openai import OpenAI
from pathlib import Path
from typing import Dict, Any, List, Union
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(filename)s:%(lineno)d - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Define enum values that need consistent translation
ENUM_VALUES = {
    "ActionType": ["mitigation", "adaptation"],
    "Hazard": [
        "droughts",
        "heatwaves",
        "floods",
        "sea-level-rise",
        "landslides",
        "storms",
        "wildfires",
        "diseases",
    ],
    "Sector": [
        "stationary_energy",
        "transportation",
        "waste",
        "ippu",
        "afolu",
        "water_resources",
        "food_security",
        "energy_security",
        "biodiversity",
        "public_health",
        "railway_infrastructure",
        "road_infrastructure",
        "port_infrastructure",
        "geo-hydrological_disasters",
    ],
    "Subsector": [
        "residential_buildings",
        "commercial_and_institutional_buildings_and_facilities",
        "manufacturing_industries_and_construction",
        "energy_industries",
        "energy_generation_supplied_to_the_grid",
        "agriculture_forestry_and_fishing_activities",
        "non-specified_sources",
        "fugitive_emissions_from_mining_processing_storage_and_transportation_of_coal",
        "fugitive_emissions_from_oil_and_natural_gas_systems",
        "on-road",
        "railways",
        "waterborne_navigation",
        "aviation",
        "off-road",
        "disposal_of_solid_waste_generated_in_the_city",
        "disposal_of_solid_waste_generated_outside_the_city",
        "biological_treatment_of_waste_generated_in_the_city",
        "biological_treatment_of_waste_generated_outside_the_city",
        "incineration_and_open_burning_of_waste_generated_in_the_city",
        "incineration_and_open_burning_of_waste_generated_outside_the_city",
        "wastewater_generated_in_the_city",
        "wastewater_generated_outside_the_city",
        "industrial_processes",
        "product_use",
        "livestock",
        "land",
        "aggregate_sources_and_non-co2_emission_sources_on_land",
        "all",
    ],
    "PrimaryPurpose": ["ghg_reduction", "climate_resilience"],
    "CoBenefits": [
        "air_quality",
        "water_quality",
        "habitat",
        "cost_of_living",
        "housing",
        "mobility",
        "stakeholder_engagement",
    ],
    "GHGReductionPotential": [
        "stationary_energy",
        "transportation",
        "waste",
        "ippu",
        "afolu",
    ],
    "GHGReductionPotentialValues": ["0-19", "20-39", "40-59", "60-79", "80-100"],
    "EffectivenessValues": ["high", "medium", "low"],
    "TimelineValues": ["<5 years", "5-10 years", ">10 years"],
    "BiomeValues": [
        "none",
        "tropical_rainforest",
        "temperate_forest",
        "desert",
        "grassland_savanna",
        "tundra",
        "wetlands",
        "mountains",
        "boreal_forest_taiga",
        "coastal_marine",
    ],
}


def translate_enum_values(target_language: str) -> Dict[str, Dict[str, str]]:
    """
    Create a translation mapping for enum values to ensure consistency
    """
    translation_map = {}

    system_prompt = f"""
<role>
You are a translator specializing in climate action implementation plans.
</role>

<task>
Your task is to translate the given climate action terms into a specified target language. 
These are specific terms that need to be translated consistently throughout the document.
Try to keep the same tone and style as the original text.
If you cannot translate a specific word or phrase e.g. because it is a proper noun or a scientific term, leave it in English.

The terms are provided in a specific order. You MUST maintain this exact order in your response.
Each term should be translated individually, maintaining the same order as the input.

Do not translate the following terms:
- ippu
- afolu

The terms are separated by " ||| ". Please maintain this separator in your response.
</task>

<important>
Do not add any additional text or formatting to the output like ```json```, ```html```, ```markdown```, etc.
You return only the plain translated text with the same separators.
The number of terms in your response must exactly match the number of terms in the input.
</important>
"""

    try:
        # Translate each category separately to maintain order
        for category, values in ENUM_VALUES.items():
            separator = " ||| "
            combined_values = separator.join(values)

            user_prompt = f"""
The target language is: 
{target_language}

These are the climate action terms for category '{category}': 
{combined_values}

Please translate each term in the exact same order as provided.
"""

            response = client.chat.completions.create(
                model="gpt-4.1",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,
                seed=42,
            )

            translated_values = response.choices[0].message.content
            if translated_values:
                translated_list = translated_values.split(separator)

                # Validate that we got the same number of translations
                if len(translated_list) != len(values):
                    raise ValueError(
                        f"Number of translations ({len(translated_list)}) does not match number of values ({len(values)}) for category {category}"
                    )

                # Create mapping for this category
                translation_map[category] = dict(zip(values, translated_list))

                # # Log the translations for verification
                # logger.info(f"Translations for {category}:")
                # for orig, trans in translation_map[category].items():
                #     logger.info(f"  {orig} -> {trans}")

    except Exception as e:
        logger.error(f"Error translating enum values: {e}")
        raise

    return translation_map


def translate_action(
    action: Dict[str, Any],
    target_language: str,
    translation_map: Dict[str, Dict[str, str]],
) -> Dict[str, Any]:
    """
    Translate an action while maintaining consistency for enum values
    """
    # Convert action to JSON string for translation
    action_str = json.dumps(action, ensure_ascii=False, indent=2)

    # Create a string representation of the translation map
    translation_map_str = json.dumps(translation_map, ensure_ascii=False, indent=2)

    system_prompt = f"""
<role>
You are a translator specializing in climate action implementation plans.
</role>

<task>
Your task is to translate the given climate action into a specified target language. 
The action is provided as a JSON object.

IMPORTANT: You must use the from the user provided translations for specific terms.

These translations must be used consistently throughout the document.
For all other text, translate normally while maintaining the same tone and style.
If you cannot translate a specific word or phrase e.g. because it is a proper noun or a scientific term, leave it in English.

IMPORTANT FOR KEYS WITH UNDERSCORES:
- Any key that contains underscores in the original English must maintain underscores in the translation
- Example: "air_quality" should be translated to "calidad_del_aire" for Spanish (not "calidad del aire")
- Example: "stationary_energy" should be translated to "energia_estacionaria" for Spanish (not "energía estacionaria")
- This applies to ALL keys that originally contained underscores, not just nested ones
- The underscores should be used to separate words in the translation, just like in the original

The output must be a valid JSON object with the same structure as the input.
Do not modify numeric values or the structure of the JSON.
</task>

<important>
Do not add any additional text or formatting to the output like ```json```, ```html```, ```markdown```, etc.
You return only the translated JSON object.
</important>
"""

    user_prompt = f"""
The target language is: 
{target_language}

This is the climate action: 
{action_str}

The translations for specific terms are:
{translation_map_str}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
            seed=42,
        )
        translated_str = response.choices[0].message.content
        if translated_str:
            return json.loads(translated_str)
    except Exception as e:
        logger.error(
            f"Error translating action {action.get('ActionID', 'Unknown ID')}: {e}"
        )
        raise

    return action


def main():
    parser = argparse.ArgumentParser(
        description="Translate climate actions to specified language"
    )
    parser.add_argument(
        "--language",
        type=str,
        required=True,
        help="Target language code (e.g., es, fr, de)",
    )
    args = parser.parse_args()

    # Input and output paths
    input_path = Path(BASE_DIR / "data/climate_actions/output/merged.json")
    output_dir = Path(BASE_DIR / "data/climate_actions/output/translations")
    output_path = output_dir / f"merged_{args.language}.json"

    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Read input file
        logger.info(f"Reading actions from {input_path}")
        with open(input_path, "r", encoding="utf-8") as f:
            actions = json.load(f)

        # For testing, only do the first 10 actions
        actions = actions[:2]

        # Create translation map for enum values
        logger.info(f"Creating translation map for enum values in {args.language}")
        translation_map = translate_enum_values(args.language)

        # Translate actions one by one
        logger.info(f"Translating {len(actions)} actions to {args.language}")
        translated_actions = []
        for i, action in enumerate(actions, 1):
            logger.info(
                f"Translating action {i}/{len(actions)}: {action.get('ActionID', 'Unknown ID')}"
            )
            translated_action = translate_action(action, args.language, translation_map)
            translated_actions.append(translated_action)

        # Write output file
        logger.info(f"Writing translated actions to {output_path}")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(translated_actions, f, ensure_ascii=False, indent=2)

        logger.info("Translation completed successfully!")
    except Exception as e:
        logger.error(f"Error during translation process: {e}")
        raise


if __name__ == "__main__":
    main()
