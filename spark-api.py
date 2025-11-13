import os
import requests
import json
from dotenv import load_dotenv

# Load environment variables from a .env file if present
load_dotenv()


def get_env(name, required=True, default=None):
    val = os.getenv(name, default)
    if required and (val is None or val == ""):
        raise RuntimeError(f"Missing required environment variable: {name}")
    return val


# Required sensitive value
api_key = get_env("SPARK_API_KEY")

# Optional configuration values with sensible defaults
env_url = get_env(
    "SPARK_ENV_URL", required=False, default="https://sparkuatapi.spglobal.com"
)
app_id = get_env("SPARK_APP_ID", required=False, default="sparkassist")
model = get_env("SPARK_MODEL", required=False, default="gpt-4o-2024-11-20")

url = f"{env_url}/v1/{app_id}/openai/deployments/{model}/chat/completions?api_version=2024-02-01"

# Define your user story content as a JSON object
user_story_content = {
    "id": 9960516,
    "work_item_type": "User Story",
    "acceptance_criteria": [
        "Work on IHDC Terraform script to create new EBS volume and attach to new EC2.",
        "Create TechOps ticket to mount to the new volume.",
        "/dev/mapper/datadg-appdata /appdata",
        "User Story 7771898: Mount /appdata to EBS volume in AWS EC2 RH8.",
        "Setup so IHDC can log the data to this new appdata location.",
        "Release notes are updated."
    ],
    "story_points": 1,
    "description_html": "<p>As an owner of the AWS IHDC service,<br>I want to create EBS volume in new EC2 RH8 and mount to it<br>so that IHDC use it to store IHDC logs</p>",
    "description": "As an owner of the AWS IHDC service, I want to create EBS volume in new EC2 RH8 and mount to it so that IHDC use it to store IHDC logs.",
    "title": "[IHDC] Create EBS volume in new EC2 RH8 so we can use it for loggings",
    "assigned_to": "Zblewski, Szymon",
    "state": "Closed",
    "tags": ["EDS.BAU", "EDS.IHDC"]
}

# Prepare the payload
payload = json.dumps(
    {
        "messages": [
            {
                "role": "system",
                "content": "You are an expert project management assistant. Your task is to analyze user stories and break them down into actionable tasks. Ensure that each task is clear, concise, and includes necessary details such as objectives, responsible parties, and deadlines.",
            },
            {
                "role": "user",
                "content": json.dumps(
                    user_story_content
                ),  # Convert user story content to JSON string
            },
        ],
        "temperature": 0.2,
        "n": 1,
        "stream": "False",
        "presence_penalty": 0,
        "frequency_penalty": 0,
        "top_p": 1,
    }
)

headers = {"api-key": f"{api_key}", "Content-Type": "application/json"}
response = requests.request("POST", url, headers=headers, data=payload)

# Parse the response as JSON
response_json = response.json()
print(json.dumps(response_json, indent=2))  # Pretty print the JSON response
