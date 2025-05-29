"""
translate_explanations.py
-------------------------

This script translates the explanations in enriched climate action JSON files from English to Spanish and Portuguese using the chosen OpenRouter model.

How it works:
- For each enriched file in 'data/frontend/', it:
  1. Finds English enriched files matching the city locode pattern.
  2. Loads the JSON data containing climate actions with explanations.
  3. Extracts all explanation texts from the actions.
  4. Translates each explanation individually to both Spanish and Portuguese.
  5. Creates new localized files (ES and PT) alongside the original English versions.

How to run (from project root):

    # Single city
    python scripts/translate_explanations.py --locode "BR VDS"

    # All cities (bulk)
    python scripts/translate_explanations.py

The script processes enriched files in the data/frontend directory and creates translated versions.
"""

import os
import json
import argparse
import time
from pathlib import Path
from openai import OpenAI
from pydantic import BaseModel
import sys

# Debug: Print execution context to verify the script is running
import os as _os
print(f"[script start] __name__={__name__}, file={__file__}, cwd={_os.getcwd()}")

sys.stdout.write("=== DEBUG LOG: translate_explanations.py loaded ===\n")
sys.stdout.flush()

print("DEBUG: translate_explanations starting...")
import dotenv
dotenv.load_dotenv()


# Initialize OpenAI client
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
client = OpenAI(api_key=OPENROUTER_API_KEY, base_url="https://openrouter.ai/api/v1")
MODEL_NAME = "google/gemini-2.5-flash-preview-05-20"

# Determine project root and data directory
SCRIPT_DIR = Path(__file__).parent
ROOT_DIR = SCRIPT_DIR.parent
DATA_DIR = ROOT_DIR / 'data' / 'frontend'

# Pydantic models for structured translation response
class SingleTranslation(BaseModel):
    spanish: str
    portuguese: str

def translate_single_explanation(explanation: str) -> SingleTranslation:
    """Translate a single explanation to both Spanish and Portuguese"""
    print(f"[translate_single_explanation] Translating: {explanation[:50]}...")
    
    prompt = f"""
    Translate the following explanation to both Spanish and Portuguese:
    
    "{explanation}"
    
    Provide both translations.
    """
    
    try:
        # Use Pydantic structured parsing for single translation
        response = client.beta.chat.completions.parse(
            model=MODEL_NAME,
            messages=[
                {
                    'role': 'system', 
                    'content': 'You are an expert translator. You must return a JSON object with "spanish" and "portuguese" fields containing the translations.'
                },
                {'role': 'user', 'content': prompt}
            ],
            temperature=0,
            response_format=SingleTranslation
        )
        
        # The response is already parsed and validated by Pydantic
        parsed_response = response.choices[0].message.parsed
        if parsed_response is None:
            print("[translate_single_explanation] Error: No parsed response")
            return SingleTranslation(spanish="", portuguese="")
        
        print(f"[translate_single_explanation] Success: ES='{parsed_response.spanish[:30]}...', PT='{parsed_response.portuguese[:30]}...'")
        return parsed_response
        
    except Exception as e:
        print(f"[translate_single_explanation] Error during translation: {e}")
        return SingleTranslation(spanish="", portuguese="")

def translate_explanations_for_city(locode: str) -> bool:
    """
    Translate explanations for a specific city by locode.
    Processes both mitigation and adaptation enriched files for the city.
    
    Args:
        locode (str): The city locode (e.g., "BR VDS")
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        print(f"[translate_explanations_for_city] Processing city: {locode}")
        
        # Find English enriched files for this city (both mitigation and adaptation)
        english_files = list(DATA_DIR.glob(f'output_{locode}_*_enriched_en.json'))
        
        if not english_files:
            print(f"[translate_explanations_for_city] No English enriched files found for city {locode}")
            return False
        
        print(f"[translate_explanations_for_city] Found {len(english_files)} English files: {english_files}")
        
        success_count = 0
        
        for english_file_path in english_files:
            try:
                # Extract the base filename pattern (without _en.json)
                base_name = str(english_file_path).replace('_enriched_en.json', '')
                
                # Load English data
                with open(english_file_path, 'r', encoding='utf-8') as f:
                    english_data = json.load(f)
                
                print(f"[translate_explanations_for_city] Loaded {len(english_data)} entries from {english_file_path}")
                
                # Extract all explanations
                explanations = []
                for entry in english_data:
                    explanation = entry.get('explanation', '')
                    explanations.append(explanation)
                
                # Get translations for all explanations one by one
                print(f"[translate_explanations_for_city] Translating {len(explanations)} explanations one by one...")
                all_translations = []
                for i, explanation in enumerate(explanations):
                    print(f"[translate_explanations_for_city] Processing explanation {i+1}/{len(explanations)}")
                    translation = translate_single_explanation(explanation)
                    all_translations.append(translation)
                    
                    # Small delay to avoid rate limiting
                    if i < len(explanations) - 1:  # Don't delay after the last one
                        time.sleep(0.5)
                
                print(f"[translate_explanations_for_city] Completed all {len(all_translations)} translations")
                
                if len(all_translations) != len(explanations):
                    print(f"[translate_explanations_for_city] Warning: Expected {len(explanations)} translations, got {len(all_translations)}")
                    continue
                
                # Create Spanish version
                spanish_data = []
                for i, entry in enumerate(english_data):
                    spanish_entry = entry.copy()
                    if i < len(all_translations):
                        spanish_entry['explanation'] = all_translations[i].spanish
                    spanish_data.append(spanish_entry)
                
                # Create Portuguese version
                portuguese_data = []
                for i, entry in enumerate(english_data):
                    portuguese_entry = entry.copy()
                    if i < len(all_translations):
                        portuguese_entry['explanation'] = all_translations[i].portuguese
                    portuguese_data.append(portuguese_entry)
                
                # Save Spanish file
                spanish_file_path = Path(f"{base_name}_enriched_es.json")
                try:
                    with open(spanish_file_path, 'w', encoding='utf-8') as f:
                        json.dump(spanish_data, f, ensure_ascii=False, indent=4)
                    print(f"[translate_explanations_for_city] Updated Spanish file: {spanish_file_path}")
                except Exception as e:
                    print(f"[translate_explanations_for_city] Failed to write Spanish file: {e}")
                    continue
                
                # Save Portuguese file
                portuguese_file_path = Path(f"{base_name}_enriched_pt.json")
                try:
                    with open(portuguese_file_path, 'w', encoding='utf-8') as f:
                        json.dump(portuguese_data, f, ensure_ascii=False, indent=4)
                    print(f"[translate_explanations_for_city] Updated Portuguese file: {portuguese_file_path}")
                except Exception as e:
                    print(f"[translate_explanations_for_city] Failed to write Portuguese file: {e}")
                    continue
                
                success_count += 1
                
            except Exception as e:
                print(f"[translate_explanations_for_city] Error processing file {english_file_path}: {e}")
        
        if success_count == len(english_files):
            print(f"[translate_explanations_for_city] Successfully processed all {success_count} files for city {locode}")
            return True
        else:
            print(f"[translate_explanations_for_city] Processed {success_count}/{len(english_files)} files for city {locode}")
            return success_count > 0
            
    except Exception as e:
        print(f"[translate_explanations_for_city] Error processing city {locode}: {e}")
        return False

def main(locode: str = None):
    """
    Main function that can process either a single city or all cities.
    
    Args:
        locode (str, optional): If provided, process only this city. Otherwise, process all cities.
    """
    if locode:
        # Process single city
        success = translate_explanations_for_city(locode)
        if success:
            print(f"Successfully translated explanations for {locode}")
        else:
            print(f"Failed to translate explanations for {locode}")
        return success
    else:
        # Process all cities (bulk processing)
        # Find all English enriched files
        english_files = list(DATA_DIR.glob('*_enriched_en.json'))
        
        # Extract unique locodes from filenames
        locodes = set()
        for file_path in english_files:
            filename = file_path.name
            # Extract locode from pattern: output_LOCODE_TYPE_enriched_en.json
            # Examples: 
            # - output_BR VDS_adaptation_enriched_en.json -> BR VDS
            # - output_BRSER_mitigation_enriched_en.json -> BRSER
            parts = filename.split('_')
            if len(parts) >= 4 and parts[0] == 'output':
                # Find where 'enriched' appears to know where locode ends
                try:
                    enriched_index = parts.index('enriched')
                    # The action type (adaptation/mitigation) is right before 'enriched'
                    # So locode parts are from index 1 to enriched_index-1
                    locode_parts = parts[1:enriched_index-1]
                    locode = ' '.join(locode_parts)
                    locodes.add(locode)
                except ValueError:
                    # 'enriched' not found, skip this file
                    print(f"[main] Warning: Could not parse filename {filename}")
                    continue
        
        print(f"[main] Found {len(locodes)} cities to process: {sorted(locodes)}")
        
        success_count = 0
        for city_locode in sorted(locodes):
            print(f'[main] Translating explanations for {city_locode}')
            if translate_explanations_for_city(city_locode):
                success_count += 1
        
        print(f"[main] Successfully processed {success_count}/{len(locodes)} cities")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Translate explanations in enriched climate action files")
    parser.add_argument(
        "--locode", 
        type=str, 
        help="Process only the specified city locode (e.g., 'BR VDS'). If not provided, processes all cities."
    )
    
    args = parser.parse_args()
    main(args.locode)
