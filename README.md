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

### Automated pipeline

Run the `run_pipeline` script inside `/scripts` folder with `bash run_pipeline LOCODE` where `LOCODE` needs to be replaced by a matching locode from the cities data file inside `data/cities`.

This script will automatically create the ranked actions for this city, format and upload those actions to the AWS S3 bucket for displaying in the frontend app.

To run the script, the packages inside `/extractor/requirements.txt` needs to be installed. The script will be looking for a virtual environment `.extractor` inside the `/extractor` folder.
