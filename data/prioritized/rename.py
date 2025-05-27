import os

# Directory containing the files (current directory)
directory = os.path.dirname(os.path.abspath(__file__))

for filename in os.listdir(directory):
    if filename.endswith('_updated.json'):
        new_filename = filename.replace('_updated.json', '.json')
        old_path = os.path.join(directory, filename)
        new_path = os.path.join(directory, new_filename)
        # Avoid overwriting existing files
        if not os.path.exists(new_path):
            os.rename(old_path, new_path)
            print(f"Renamed: {filename} -> {new_filename}")
        else:
            print(f"Skipped (target exists): {filename} -> {new_filename}")
