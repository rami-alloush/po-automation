import os
import json
import requests
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

url = f"{env_url}/v1/{app_id}/openai/deployments/{model}/chat/completions?api_version=2024-10-21"

def generate_tasks(user_story_content):
    # Prepare the payload
    payload = json.dumps(
        {
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert project management assistant. Your task is to analyze user stories and break them down into actionable tasks. Ensure that each task is clear, concise, and includes necessary details such as objectives, responsible parties, and deadlines. Return the tasks in a structured JSON format with the following structure: { 'tasks': [ { 'Work Item Type': 'Task', 'Description': <task_description>, 'Original Estimate': <original_estimate>, 'Title': <title>, 'Assigned To': <assigned_to>, 'State': <state>, 'Tags': <tags> } ] }. Every story point is 6 hours, the total tasks estimates should sum up to the story points multiplied by 6 hours. IMPORTANT: Output ONLY valid JSON. Do not include any conversational text, markdown formatting, or explanations.",
                },
                {"role": "user", "content": json.dumps(user_story_content)},
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

    if response.status_code != 200:
         raise Exception(f"Spark API Error: {response.status_code} - {response.text}")

    # Parse the response as JSON
    response_json = response.json()

    # Extract the content from the response
    response_content = response_json["choices"][0]["message"]["content"]

    # Remove the code block formatting and parse the JSON
    try:
        # Find the first '{' and last '}' to extract JSON content
        start_idx = response_content.find('{')
        end_idx = response_content.rfind('}')
        
        if start_idx != -1 and end_idx != -1:
            cleaned_content = response_content[start_idx:end_idx+1]
        else:
            cleaned_content = response_content.strip()
            
        response_content_json = json.loads(cleaned_content)
        return response_content_json
    except json.JSONDecodeError:
        # Fallback if the response isn't perfect JSON
        raise Exception(f"Failed to parse JSON from Spark response: {response_content}")

if __name__ == "__main__":
    # Test data
    test_story = {
        "id": 9950586,
        "title": "Test Story",
        "description": "Test Description",
        "acceptance_criteria": "Test AC",
        "story_points": 1
    }
    try:
        tasks = generate_tasks(test_story)
        print(json.dumps(tasks, indent=2))
    except Exception as e:
        print(e)
