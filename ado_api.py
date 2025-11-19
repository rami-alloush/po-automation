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

def get_work_item(work_item_id):
    # Azure DevOps REST API URL
    url = f"https://dev.azure.com/{organization}/{project}/_apis/wit/workitems/{work_item_id}?api-version=6.0"

    # Make the request
    response = requests.get(url, auth=HTTPBasicAuth("", pat_token))

    # Check if the request was successful
    if response.status_code == 200:
        work_item_details = response.json()
        work_item = {
            "ID": work_item_details["id"],
            "Work Item Type": work_item_details["fields"]["System.WorkItemType"],
            "Description": work_item_details["fields"].get("System.Description", ""),
            "Title": work_item_details["fields"]["System.Title"],
            "Assigned To": work_item_details["fields"].get("System.AssignedTo", {}).get("displayName", "Unassigned"),
            "State": work_item_details["fields"]["System.State"],
            "Tags": work_item_details["fields"].get("System.Tags", "").split("; "),
            "Created By": work_item_details["fields"]["System.CreatedBy"]["displayName"],
            "Created Date": work_item_details["fields"]["System.CreatedDate"],
            "Changed By": work_item_details["fields"].get("System.ChangedBy", {}).get("displayName", ""),
            "Changed Date": work_item_details["fields"]["System.ChangedDate"],
            "Acceptance Criteria": work_item_details["fields"].get("Microsoft.VSTS.Common.AcceptanceCriteria", ""),
            "Story Points": work_item_details["fields"].get("Microsoft.VSTS.Scheduling.StoryPoints", 0),
            "Area Path": work_item_details["fields"]["System.AreaPath"],
            "Iteration Path": work_item_details["fields"]["System.IterationPath"],
            "url": work_item_details["url"],
            "Web URL": work_item_details["_links"]["html"]["href"]
        }
        return work_item
    else:
        raise Exception(f"Failed to retrieve work item: {response.status_code} - {response.text}")

def create_task(parent_work_item, task_data):
    url = f"https://dev.azure.com/{organization}/{project}/_apis/wit/workitems/$Task?api-version=6.0"
    
    # Construct the JSON Patch document
    patch_document = [
        {
            "op": "add",
            "path": "/fields/System.Title",
            "value": task_data.get("Title")
        },
        {
            "op": "add",
            "path": "/fields/System.Description",
            "value": task_data.get("Description")
        },
        {
            "op": "add",
            "path": "/fields/System.AreaPath",
            "value": parent_work_item["Area Path"]
        },
        {
            "op": "add",
            "path": "/fields/System.IterationPath",
            "value": parent_work_item["Iteration Path"]
        },
        {
            "op": "add",
            "path": "/fields/Microsoft.VSTS.Scheduling.OriginalEstimate",
            "value": task_data.get("Original Estimate")
        },
        {
            "op": "add",
            "path": "/fields/Microsoft.VSTS.Common.Activity",
            "value": task_data.get("Activity", "Development")
        },
        {
             "op": "add",
             "path": "/relations/-",
             "value": {
                 "rel": "System.LinkTypes.Hierarchy-Reverse",
                 "url": parent_work_item["url"]
             }
        }
    ]

    if "Assigned To" in task_data and task_data["Assigned To"]:
         patch_document.append({
            "op": "add",
            "path": "/fields/System.AssignedTo",
            "value": task_data["Assigned To"]
        })

    response = requests.post(
        url, 
        json=patch_document, 
        headers={"Content-Type": "application/json-patch+json"},
        auth=HTTPBasicAuth("", pat_token)
    )

    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to create task: {response.status_code} - {response.text}")

if __name__ == "__main__":
    # Test the function
    try:
        wi = get_work_item("9950586")
        print(json.dumps(wi, indent=2))
    except Exception as e:
        print(e)
