import os
import json
import requests
import re
from dotenv import load_dotenv

# Load environment variables from a .env file if present
# load_dotenv() is now called inside get_spark_config


def get_env(name, required=True, default=None):
    val = os.getenv(name, default)
    if required and (val is None or val == ""):
        raise RuntimeError(f"Missing required environment variable: {name}")
    return val


def get_spark_config():
    load_dotenv(override=True)

    api_key = get_env("SPARK_API_KEY")
    env_url = get_env(
        "SPARK_ENV_URL", required=False, default="https://sparkuatapi.spglobal.com"
    )
    app_id = get_env("SPARK_APP_ID", required=False, default="sparkassist")
    model = get_env("SPARK_MODEL", required=False, default="gpt-4o-2024-11-20")

    url = f"{env_url}/v1/{app_id}/openai/deployments/{model}/chat/completions?api_version=2024-10-21"
    return api_key, url


def generate_tasks(user_story_content):
    api_key, url = get_spark_config()

    # Prepare the payload
    payload = json.dumps(
        {
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert project management assistant. Your task is to analyze user stories and break them down into actionable tasks. Rules: 1. Every story point equals 6 hours. 2. The sum of 'Original Estimate' for all tasks MUST exactly equal (Story Points * 6). 3. You MUST include a final task with Title 'Testing' and 'Original Estimate' of 1. 4. Distribute the remaining hours ((Story Points * 6) - 1) among the other actionable tasks. Return the tasks in a structured JSON format with the following structure: { 'tasks': [ { 'Work Item Type': 'Task', 'Description': <task_description>, 'Original Estimate': <original_estimate>, 'Title': <title>, 'State': <state>, 'Tags': <tags> } ] }. IMPORTANT: Output ONLY valid JSON.",
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
        start_idx = response_content.find("{")
        end_idx = response_content.rfind("}")

        if start_idx != -1 and end_idx != -1:
            cleaned_content = response_content[start_idx : end_idx + 1]
        else:
            cleaned_content = response_content.strip()

        response_content_json = json.loads(cleaned_content)
        return response_content_json
    except json.JSONDecodeError:
        # Fallback if the response isn't perfect JSON
        raise Exception(f"Failed to parse JSON from Spark response: {response_content}")


def suggest_stories(feature, existing_stories):
    api_key, url = get_spark_config()

    # Prepare the existing stories summary
    stories_text = ""
    if existing_stories:
        for s in existing_stories:
            stories_text += f"- ID: {s.get('ID')}, Title: {s.get('Title')}, Description: {s.get('Description')}\n"
    else:
        stories_text = "No existing user stories found."

    # Prepare the payload
    payload = json.dumps(
        {
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert Product Owner. Your task is to analyze a Feature and its existing User Stories, identify gaps in coverage, and suggest additional User Stories to fully achieve the Feature's objective. Return the suggested stories in a structured JSON format with the following structure: { 'stories': [ { 'Work Item Type': 'User Story', 'Title': <title>, 'Description': <description>, 'Acceptance Criteria': <acceptance_criteria>, 'Story Points': <estimated_points> } ] }. IMPORTANT: Output ONLY valid JSON.",
                },
                {
                    "role": "user",
                    "content": f"Feature ID: {feature.get('ID')}\nFeature Title: {feature.get('Title')}\nFeature Description: {feature.get('Description')}\nAssigned To: {feature.get('Assigned To')}\nState: {feature.get('State')}\nAcceptance Criteria: {feature.get('Acceptance Criteria')}\nExternal Dependencies: {feature.get('External Dependencies')}\nNon Functional Requirements: {feature.get('Non Functional Requirements')}\nArea Path: {feature.get('Area Path')}\nIteration Path: {feature.get('Iteration Path')}\nTags: {feature.get('Tags')}\n\nExisting User Stories:\n{stories_text}\n\nPlease suggest additional User Stories needed to complete this Feature.",
                },
            ],
            "temperature": 0.3,
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
        start_idx = response_content.find("{")
        end_idx = response_content.rfind("}")

        if start_idx != -1 and end_idx != -1:
            cleaned_content = response_content[start_idx : end_idx + 1]
        else:
            cleaned_content = response_content.strip()

        response_content_json = json.loads(cleaned_content)
        return response_content_json
    except json.JSONDecodeError:
        # Fallback if the response isn't perfect JSON
        raise Exception(f"Failed to parse JSON from Spark response: {response_content}")


def review_plan(feature, user_stories):
    api_key, url = get_spark_config()

    # Prepare stories text
    stories_text = ""
    if user_stories:
        # Sort by Iteration Path to show current order
        sorted_stories = sorted(user_stories, key=lambda x: x.get("Iteration Path", ""))
        for s in sorted_stories:
            stories_text += f"- ID: {s.get('ID')}, Title: {s.get('Title')}, Iteration: {s.get('Iteration Path')}\n"
    else:
        stories_text = "No existing user stories found."

    # Prepare the payload
    payload = json.dumps(
        {
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert Project Manager and Scrum Master. Your task is to review a Feature and its associated User Stories (which form a plan). Analyze the execution order based on Iteration Paths. Identify any logic gaps, missing steps, or dependency issues. Suggest a better order if needed. Identify potential external dependencies. Return the result in valid JSON format: { 'suggestions': ['suggestion 1', ...], 'missing_steps': [{'Title': '...', 'Description': '...'}], 'external_dependencies': ['dep 1', ...], 'proposed_order': [id1, id2, ...] }. IMPORTANT: Output ONLY valid JSON.",
                },
                {
                    "role": "user",
                    "content": f"Feature: {feature.get('Title')}\nDescription: {feature.get('Description')}\n\nCurrent Plan (User Stories):\n{stories_text}\n\nPlease review this plan.",
                },
            ],
            "temperature": 0.3,
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
        start_idx = response_content.find("{")
        end_idx = response_content.rfind("}")

        if start_idx != -1 and end_idx != -1:
            cleaned_content = response_content[start_idx : end_idx + 1]
        else:
            cleaned_content = response_content.strip()

        response_content_json = json.loads(cleaned_content)
        return response_content_json
    except json.JSONDecodeError:
        # Fallback if the response isn't perfect JSON
        raise Exception(f"Failed to parse JSON from Spark response: {response_content}")


def strip_html(text):
    if not text:
        return ""
    clean = re.compile("<.*?>")
    return re.sub(clean, "", text)


def generate_feature_details(feature, user_stories):
    api_key, url = get_spark_config()

    # Prepare stories text
    stories_text = ""
    if user_stories:
        for s in user_stories:
            desc = strip_html(s.get("Description", ""))
            ac = strip_html(s.get("Acceptance Criteria", ""))
            stories_text += f"- ID: {s.get('ID')}, Title: {s.get('Title')}, Description: {desc}, AC: {ac}\n"
    else:
        stories_text = "No existing user stories found."

    # Prepare the payload
    payload = json.dumps(
        {
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert Product Owner. Your task is to analyze a Feature and its child User Stories to generate a comprehensive Feature definition. You must generate: 1. Description (Executive summary of what the feature delivers). 2. External Dependencies (List of dependencies). 3. Non-functional Requirements (List of NFRs). 4. Acceptance Criteria (High-level ACs for the feature). Return the result in valid JSON format with these EXACT keys: { 'description': 'HTML string', 'external_dependencies': 'HTML string (ul/li) or empty string', 'non_functional_requirements': 'HTML string (ul/li) or empty string', 'acceptance_criteria': 'HTML string (ul/li)' }. If there are no dependencies or NFRs, return an empty string or '<ul><li>None</li></ul>'. IMPORTANT: Output ONLY valid JSON.",
                },
                {
                    "role": "user",
                    "content": f"Feature Title: {feature.get('Title')}\n\nUser Stories:\n{stories_text}\n\nGenerate the feature details based on these stories.",
                },
            ],
            "temperature": 0.3,
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
        start_idx = response_content.find("{")
        end_idx = response_content.rfind("}")

        if start_idx != -1 and end_idx != -1:
            cleaned_content = response_content[start_idx : end_idx + 1]
        else:
            cleaned_content = response_content.strip()

        response_content_json = json.loads(cleaned_content)
        return response_content_json
    except json.JSONDecodeError:
        # Fallback if the response isn't perfect JSON
        raise Exception(f"Failed to parse JSON from Spark response: {response_content}")


def chat_completion(messages):
    api_key, url = get_spark_config()

    # Prepend system message if not present or just ensure it exists in the stream
    # The caller manages the full history
    payload = json.dumps(
        {
            "messages": messages,
            "temperature": 0.5,
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

    response_json = response.json()
    return response_json["choices"][0]["message"]["content"]


def extract_stories_from_chat(chat_history):
    api_key, url = get_spark_config()

    # Convert chat history to a single text block for context
    conversation_text = ""
    for msg in chat_history:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        conversation_text += f"{role.upper()}: {content}\n\n"

    payload = json.dumps(
        {
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert Product Owner. Your task is to extract structured User Stories from a conversation history. "
                    "Based on the discussion, identify the user stories that have been defined or agreed upon. "
                    "Return them in a valid JSON format with the following structure: "
                    "{ 'stories': [ { 'Work Item Type': 'User Story', 'Title': <title>, 'Description': <description>, 'Acceptance Criteria': <acceptance_criteria_as_html_ul_li_string>, 'Story Points': <estimated_points> } ] }. "
                    "Ensure 'Acceptance Criteria' is a single string containing HTML list elements (<ul><li>...</li></ul>), NOT a JSON list. "
                    "If no clear stories are defined, return { 'stories': [] }. IMPORTANT: Output ONLY valid JSON.",
                },
                {
                    "role": "user",
                    "content": f"Here is the conversation history:\n\n{conversation_text}\n\nPlease extract the User Stories discussing in this conversation.",
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

    if response.status_code != 200:
        raise Exception(f"Spark API Error: {response.status_code} - {response.text}")

    response_json = response.json()
    response_content = response_json["choices"][0]["message"]["content"]

    try:
        start_idx = response_content.find("{")
        end_idx = response_content.rfind("}")

        if start_idx != -1 and end_idx != -1:
            cleaned_content = response_content[start_idx : end_idx + 1]
        else:
            cleaned_content = response_content.strip()

        response_content_json = json.loads(cleaned_content)
        return response_content_json
    except json.JSONDecodeError:
        raise Exception(f"Failed to parse JSON from Spark response: {response_content}")
