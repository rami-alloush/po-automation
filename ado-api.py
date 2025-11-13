import os
import json
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

# Load environment variables from a .env file if present
load_dotenv()


def get_env(name, required=True, default=None):
    val = os.getenv(name, default)
    if required and (val is None or val == ""):
        raise RuntimeError(f"Missing required environment variable: {name}")
    return val


# Required sensitive value
pat_token = get_env("ADO_PAT_TOKEN")

# Replace these variables with your own information
organization = "spglobal"
project = "Platts"
work_item_id = "9960516"

# Azure DevOps REST API URL
url = f"https://dev.azure.com/{organization}/{project}/_apis/wit/workitems/{work_item_id}?api-version=6.0"

# Make the request
response = requests.get(url, auth=HTTPBasicAuth("", pat_token))

# Check if the request was successful
if response.status_code == 200:
    work_item_details = response.json()
    # print(json.dumps(work_item_details, indent=2))  # Pretty print the JSON response
    work_item ={
        "ID": work_item_details["id"],
        "Work Item Type": work_item_details["fields"]["System.WorkItemType"],
        "Description": work_item_details["fields"]["System.Description"],
        "Title": work_item_details["fields"]["System.Title"],
        "Assigned To": work_item_details["fields"]["System.AssignedTo"]["displayName"],
        "State": work_item_details["fields"]["System.State"],
        "Tags": work_item_details["fields"]["System.Tags"].split("; "),
        "Created By": work_item_details["fields"]["System.CreatedBy"]["displayName"],
        "Created Date": work_item_details["fields"]["System.CreatedDate"],
        "Changed By": work_item_details["fields"]["System.ChangedBy"]["displayName"],
        "Changed Date": work_item_details["fields"]["System.ChangedDate"],
        "Acceptance Criteria": work_item_details["fields"][
            "Microsoft.VSTS.Common.AcceptanceCriteria"
        ],
    }
    print(json.dumps(work_item, indent=2))
else:
    print(f"Failed to retrieve work item: {response.status_code} - {response.text}")
