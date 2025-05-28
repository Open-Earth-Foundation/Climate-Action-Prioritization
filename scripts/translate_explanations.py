"""
This script translates the explanations in enriched climate action JSON files.

It translates the 'explanation' field from English to Spanish and Portuguese
for enriched files created by the frontend enricher.

The script can process either:
- A single city by locode (for pipeline integration)
- All cities in the frontend directory (bulk processing)

Execute the script with the following commands:
# Single city
python scripts/translate_explanations.py --locode "BR VDS"

# All cities (bulk)
python scripts/translate_explanations.py

The script processes enriched files in the data/frontend directory.
"""

import os
import json
import glob
import argparse
from openai import OpenAI
from pydantic import BaseModel
from typing import List
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
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(ROOT_DIR, 'data', 'frontend')

# Pydantic models for structured translation response
class TranslationPair(BaseModel):
    spanish: str
    portuguese: str

class TranslationResponse(BaseModel):
    translations: List[TranslationPair]

def translate_explanations_batch(explanations: List[str]) -> TranslationResponse:
    """Translate a batch of explanations to both Spanish and Portuguese in a single API call"""
    print(f"[translate_explanations_batch] Translating {len(explanations)} explanations...")
    
    # Create the prompt with all explanations
    explanations_text = "\n".join([f"{i+1}. {exp}" for i, exp in enumerate(explanations)])
    
    prompt = f"""
    Please translate the following {len(explanations)} explanations to both Spanish and Portuguese.
    Return a JSON object with a "translations" array where each item has "spanish" and "portuguese" fields.
    
    Explanations to translate:
    {explanations_text}
    
    Return format:
    {{
        "translations": [
            {{"spanish": "Spanish translation of explanation 1", "portuguese": "Portuguese translation of explanation 1"}},
            {{"spanish": "Spanish translation of explanation 2", "portuguese": "Portuguese translation of explanation 2"}},
            ...
        ]
    }}
    """
    
    try:
        response = client.beta.chat.completions.parse(
            model=MODEL_NAME,
            messages=[
                {'role': 'system', 'content': 'You are an expert translator. Always return valid JSON in the exact format requested.'},
                {'role': 'user', 'content': prompt}
            ],
            temperature=0,
            response_format=TranslationResponse
        )
        
        response_content = response.choices[0].message.content
        if response_content is None:
            print("[translate_explanations_batch] Error: No response content")
            return TranslationResponse(translations=[])
            
        translation_data = json.loads(response_content)
        return TranslationResponse(**translation_data)
        
    except Exception as e:
        print(f"[translate_explanations_batch] Error during translation: {e}")
        return TranslationResponse(translations=[])

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
        pattern = os.path.join(DATA_DIR, f'output_{locode}_*_enriched_en.json')
        english_files = glob.glob(pattern)
        
        if not english_files:
            print(f"[translate_explanations_for_city] No English enriched files found for city {locode}")
            return False
        
        print(f"[translate_explanations_for_city] Found {len(english_files)} English files: {english_files}")
        
        success_count = 0
        
        for english_file_path in english_files:
            try:
                # Extract the base filename pattern (without _en.json)
                base_name = english_file_path.replace('_enriched_en.json', '')
                
                # Load English data
                with open(english_file_path, 'r', encoding='utf-8') as f:
                    english_data = json.load(f)
                
                print(f"[translate_explanations_for_city] Loaded {len(english_data)} entries from {english_file_path}")
                
                # Extract all explanations
                explanations = []
                for entry in english_data:
                    explanation = entry.get('explanation', '')
                    explanations.append(explanation)
                
                # Get translations for all explanations in one call
                translation_response = translate_explanations_batch(explanations)
                
                if len(translation_response.translations) != len(explanations):
                    print(f"[translate_explanations_for_city] Warning: Expected {len(explanations)} translations, got {len(translation_response.translations)}")
                    continue
                
                # Create Spanish version
                spanish_data = []
                for i, entry in enumerate(english_data):
                    spanish_entry = entry.copy()
                    if i < len(translation_response.translations):
                        spanish_entry['explanation'] = translation_response.translations[i].spanish
                    spanish_data.append(spanish_entry)
                
                # Create Portuguese version
                portuguese_data = []
                for i, entry in enumerate(english_data):
                    portuguese_entry = entry.copy()
                    if i < len(translation_response.translations):
                        portuguese_entry['explanation'] = translation_response.translations[i].portuguese
                    portuguese_data.append(portuguese_entry)
                
                # Save Spanish file
                spanish_file_path = f"{base_name}_enriched_es.json"
                try:
                    with open(spanish_file_path, 'w', encoding='utf-8') as f:
                        json.dump(spanish_data, f, ensure_ascii=False, indent=4)
                    print(f"[translate_explanations_for_city] Updated Spanish file: {spanish_file_path}")
                except Exception as e:
                    print(f"[translate_explanations_for_city] Failed to write Spanish file: {e}")
                    continue
                
                # Save Portuguese file
                portuguese_file_path = f"{base_name}_enriched_pt.json"
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
        pattern = os.path.join(DATA_DIR, '*_enriched_en.json')
        english_files = glob.glob(pattern)
        
        # Extract unique locodes from filenames
        locodes = set()
        for file_path in english_files:
            filename = os.path.basename(file_path)
            # Extract locode from pattern: output_LOCODE_TYPE_enriched_en.json
            parts = filename.split('_')
            if len(parts) >= 4 and parts[0] == 'output':
                # Handle locodes with spaces (e.g., "BR VDS")
                if len(parts) == 5:  # output_BR_VDS_TYPE_enriched_en.json
                    locode = f"{parts[1]} {parts[2]}"
                else:  # output_LOCODE_TYPE_enriched_en.json
                    locode = parts[1]
                locodes.add(locode)
        
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
