"""
Script used to upload a file to an S3 bucket.

This script handles uploading files to an S3 bucket specified in the environment variables.
It requires AWS credentials to be properly configured either through environment variables
or AWS credentials file.

Usage:
    python upload_to_s3.py --file_name name_of_file --s3_key path_in_bucket
"""

import boto3
from dotenv import load_dotenv
import argparse
import os
from pathlib import Path

# Define the base path to the project root
BASE_DIR = Path(__file__).parent.parent.parent

# Load environment variables
load_dotenv()
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")

if not S3_BUCKET_NAME:
    raise ValueError("S3_BUCKET_NAME environment variable is not set")


def upload_to_s3(file_name: str, s3_key: str) -> None:
    """
    Upload a file to an S3 bucket.

    Args:
        file_name (str): The name of the file to upload (file must be in the data/frontend folder)
        s3_key (str): The S3 key (path in the bucket) where the file will be stored
    """

    # Set the file path to the data/frontend folder and the file name
    folder_path = BASE_DIR / "data" / "frontend"
    file_path = folder_path / file_name

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Initialize S3 client
    s3_client = boto3.client("s3")

    try:
        s3_client.upload_file(str(file_path), S3_BUCKET_NAME, s3_key)
        print(f"File {file_path} uploaded to {S3_BUCKET_NAME}/{s3_key}")
    except Exception as e:
        print(f"Error uploading file: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload a file to an S3 bucket.")

    parser.add_argument(
        "--file_name",
        type=str,
        required=True,
        help="The name of the file to upload (file must be in the data/frontend folder)",
    )
    parser.add_argument(
        "--s3_key",
        type=str,
        required=True,
        help="S3 key (path in the bucket) where the file will be stored",
    )

    args = parser.parse_args()
    upload_to_s3(args.file_name, args.s3_key)
