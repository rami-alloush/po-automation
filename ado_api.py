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
    url = f"https://dev.azure.com/{organization}/{project}/_apis/wit/workitems/{work_item_id}?$expand=relations&api-version=6.0"

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
            "Web URL": work_item_details.get("_links", {}).get("html", {}).get("href", ""),
            "Relations": work_item_details.get("relations", [])
        }
        return work_item
    else:
        raise Exception(f"Failed to retrieve work item: {response.status_code} - {response.text}")

def get_work_items_batch(ids):
    if not ids:
        return []
    
    ids_str = ",".join(map(str, ids))
    url = f"https://dev.azure.com/{organization}/{project}/_apis/wit/workitems?ids={ids_str}&api-version=6.0"
    
    response = requests.get(url, auth=HTTPBasicAuth("", pat_token))
    
    if response.status_code == 200:
        items = []
        for work_item_details in response.json()["value"]:
             items.append({
                "ID": work_item_details["id"],
                "Work Item Type": work_item_details["fields"]["System.WorkItemType"],
                "Description": work_item_details["fields"].get("System.Description", ""),
                "Title": work_item_details["fields"]["System.Title"],
                "State": work_item_details["fields"]["System.State"],
                "Story Points": work_item_details["fields"].get("Microsoft.VSTS.Scheduling.StoryPoints", 0),
                "Acceptance Criteria": work_item_details["fields"].get("Microsoft.VSTS.Common.AcceptanceCriteria", ""),
                "Iteration Path": work_item_details["fields"].get("System.IterationPath", ""),
                "Area Path": work_item_details["fields"].get("System.AreaPath", ""),
                "url": work_item_details["url"],
                "Web URL": work_item_details.get("_links", {}).get("html", {}).get("href", "")
             })
        return items
    else:
        raise Exception(f"Failed to retrieve work items batch: {response.status_code} - {response.text}")

def create_child_work_item(parent_work_item, item_data, work_item_type="Task"):
    # work_item_type should be 'Task' or 'User Story' etc.
    # The API expects $Task or $User%20Story
    type_encoded = work_item_type.replace(" ", "%20")
    url = f"https://dev.azure.com/{organization}/{project}/_apis/wit/workitems/${type_encoded}?api-version=6.0"
    
    # Construct the JSON Patch document
    patch_document = [
        {
            "op": "add",
            "path": "/fields/System.Title",
            "value": item_data.get("Title")
        },
        {
            "op": "add",
            "path": "/fields/System.Description",
            "value": item_data.get("Description")
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
             "path": "/relations/-",
             "value": {
                 "rel": "System.LinkTypes.Hierarchy-Reverse",
                 "url": parent_work_item["url"]
             }
        }
    ]

    # Add type-specific fields
    if work_item_type == "Task":
        patch_document.append({
            "op": "add",
            "path": "/fields/Microsoft.VSTS.Scheduling.OriginalEstimate",
            "value": item_data.get("Original Estimate")
        })
        patch_document.append({
            "op": "add",
            "path": "/fields/Microsoft.VSTS.Common.Activity",
            "value": item_data.get("Activity", "Development")
        })
    elif work_item_type == "User Story":
        if "Acceptance Criteria" in item_data:
             patch_document.append({
                "op": "add",
                "path": "/fields/Microsoft.VSTS.Common.AcceptanceCriteria",
                "value": item_data.get("Acceptance Criteria")
            })
        if "Story Points" in item_data:
             patch_document.append({
                "op": "add",
                "path": "/fields/Microsoft.VSTS.Scheduling.StoryPoints",
                "value": item_data.get("Story Points")
            })

    if "Assigned To" in item_data and item_data["Assigned To"]:
         patch_document.append({
            "op": "add",
            "path": "/fields/System.AssignedTo",
            "value": item_data["Assigned To"]
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
        raise Exception(f"Failed to create {work_item_type}: {response.status_code} - {response.text}")

def create_task(parent_work_item, task_data):
    return create_child_work_item(parent_work_item, task_data, "Task")

if __name__ == "__main__":
    # Test the function
    try:
        wi = get_work_item("9950586")
        print(json.dumps(wi, indent=2))
    except Exception as e:
        print(e)
