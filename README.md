# Climate Action Prioritization (CAP) Tool

This is a multi-stage tool for generating climate action priorities for cities.

## License

This project is licensed under the Affero General Public License v3.0. See the [LICENSE](LICENSE) file for details.

## Directories

- `data/`: Contains data files used by the different stages.
- `schema/`: Contains JSON schemas for the data files.
- `extractor/`: Extracts action data and generates a JSON file.
- `prioritizer/`: Prioritizes actions based on the extracted data.
- `scripts/`: Contains helper scripts like adding ccras, ghgis or uploading files to AWS S3. This folder also contains a `run_pipeline` script which automatically prioritizes all actions inside the long list of actions against a chosen city, transforms the data to match the required frontend schema and uploads the created file to the AWS S3 bucket for updating the frontend.

## Usage

### Data Import

We are importing data from several sources:

1. City context data from: "https://ccglobal.openearth.dev/api/v0/city_context/city"
2. City CCRA data from: "https://ccglobal.openearth.dev/api/v0/ccra/risk_assessment/city"
3. City GHGI data from exported .csv files from CityCatalyst inventories

We have a file with all the city locodes we want to import:
`data/cities/brazil_city_locodes.json`

There are 3 utilities files to import all the data:

1. `python scripts/create_city_data/run_context_bulk_import.py --bulk_file data/cities/brazil_city_locodes.json`
2. `python scripts/create_city_data/run_ghgi_bulk_import.py --bulk_file data/cities/brazil_city_locodes.json`
3. `python scripts/create_city_data/run_ccra_bulk_import.py --bulk_file data/cities/brazil_city_locodes.json`

This will import all the city data and store inside `data/cities/city_data.json`.

### Automated pipeline

Run the `run_pipeline` script inside `root` folder with `sh scripts/run_pipeline.sh LOCODE` where `LOCODE` needs to be replaced by a matching locode from the cities data file inside `data/cities`.

This script will automatically create the ranked actions for this city, format and upload those actions to the AWS S3 bucket for displaying in the frontend app.

### Requirements

To run this pipeline, AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY must be set in an `.env` file with permissions to write to the S3 bucket `/data` folder.

To run the script, the packages inside `/extractor/requirements.txt` needs to be installed. The script will be looking for a virtual environment `.cap` inside the `/.cap` top level folder.

If you create the virtual environment with a different name then `.cap` the path inside `run_pipeline.sh` must be adjusted accordingly.

Under Windows OS, this script is best executed under WSL oder Git bash.

## Debugging

### Langsmith

If the LLM logs should be logged by langsmith, the .env variables must be set
`LANGCHAIN_TRACING_V2=true`
as well as the corresponding project name and api key.
