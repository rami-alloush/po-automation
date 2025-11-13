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

payload = json.dumps(
    {
        "messages": [
            {
                "role": "system",
                "content": "You are an expert project management assistant. Your task is to analyze user stories and break them down into actionable tasks. Ensure that each task is clear, concise, and includes necessary details such as objectives, responsible parties, and deadlines.",
            },
            {"role": "user", "content": "Importance to DTS strategy?"},
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
print(response.text)
