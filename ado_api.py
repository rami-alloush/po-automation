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

# Configuration
organization = get_env("ADO_ORGANIZATION", required=False, default="spglobal")
project = get_env("ADO_PROJECT", required=False, default="Platts")


# Define a custom exception for Authentication errors
class ADOAuthenticationError(Exception):
    pass


# Helper to check response
def check_response(response, action_desc):
    if response.status_code == 200:
        return response.json()
    elif response.status_code == 401:
        # Check specific content if needed, but 401 is generally Auth Error
        raise ADOAuthenticationError(
            "Access Denied2: Your Azure DevOps Personal Access Token (PAT) has expired or is invalid. "
            "Please update the ADO_PAT_TOKEN in your .env file."
        )
    else:
        raise Exception(
            f"Failed to {action_desc}: {response.status_code} - {response.text}"
        )


def get_work_item(work_item_id):
    # Azure DevOps REST API URL
    url = f"https://dev.azure.com/{organization}/{project}/_apis/wit/workitems/{work_item_id}?$expand=relations&api-version=6.0"

    # Make the request
    response = requests.get(url, auth=HTTPBasicAuth("", pat_token))

    work_item_details = check_response(response, "retrieve work item")

    work_item = {
        "ID": work_item_details["id"],
        "Work Item Type": work_item_details["fields"]["System.WorkItemType"],
        "Description": work_item_details["fields"].get("System.Description", ""),
        "Title": work_item_details["fields"]["System.Title"],
        "Assigned To": work_item_details["fields"]
        .get("System.AssignedTo", {})
        .get("displayName", "Unassigned"),
        "State": work_item_details["fields"]["System.State"],
        "Tags": work_item_details["fields"].get("System.Tags", "").split("; "),
        "Created By": work_item_details["fields"]["System.CreatedBy"]["displayName"],
        "Created Date": work_item_details["fields"]["System.CreatedDate"],
        "Changed By": work_item_details["fields"]
        .get("System.ChangedBy", {})
        .get("displayName", ""),
        "Changed Date": work_item_details["fields"]["System.ChangedDate"],
        "Acceptance Criteria": work_item_details["fields"].get(
            "Microsoft.VSTS.Common.AcceptanceCriteria", ""
        ),
        "External Dependencies": work_item_details["fields"].get(
            "Custom.ExternalDependencies", ""
        ),
        "Non Functional Requirements": work_item_details["fields"].get(
            "Custom.NonFunctionalRequirements_MI", ""
        ),
        "Get Story Points": work_item_details["fields"].get(
            "Microsoft.VSTS.Scheduling.StoryPoints", 0
        ),
        "Story Points": work_item_details["fields"].get(
            "Microsoft.VSTS.Scheduling.StoryPoints", 0
        ),
        "Stack Rank": work_item_details["fields"].get(
            "Microsoft.VSTS.Common.StackRank",
            work_item_details["fields"].get("Microsoft.VSTS.Common.BacklogPriority", 0),
        ),
        "Stack Rank Field": (
            "Microsoft.VSTS.Common.StackRank"
            if "Microsoft.VSTS.Common.StackRank" in work_item_details["fields"]
            else "Microsoft.VSTS.Common.BacklogPriority"
        ),
        "Area Path": work_item_details["fields"]["System.AreaPath"],
        "Iteration Path": work_item_details["fields"]["System.IterationPath"],
        "url": work_item_details["url"],
        "Web URL": work_item_details.get("_links", {}).get("html", {}).get("href", ""),
        "Relations": work_item_details.get("relations", []),
        "Original Estimate": work_item_details["fields"].get(
            "Microsoft.VSTS.Scheduling.OriginalEstimate", 0
        ),
        "Activity": work_item_details["fields"].get(
            "Microsoft.VSTS.Common.Activity", "Development"
        ),
        "CMDB App Name": work_item_details["fields"].get("Custom.CMDBAppName", ""),
    }
    return work_item


def get_work_items_batch(ids):
    if not ids:
        return []

    ids_str = ",".join(map(str, ids))
    url = f"https://dev.azure.com/{organization}/{project}/_apis/wit/workitems?ids={ids_str}&api-version=6.0"

    response = requests.get(url, auth=HTTPBasicAuth("", pat_token))

    data = check_response(response, "retrieve work items batch")

    items = []
    for work_item_details in data["value"]:
        items.append(
            {
                "ID": work_item_details["id"],
                "Work Item Type": work_item_details["fields"]["System.WorkItemType"],
                "Description": work_item_details["fields"].get(
                    "System.Description", ""
                ),
                "Title": work_item_details["fields"]["System.Title"],
                "Assigned To": work_item_details["fields"]
                .get("System.AssignedTo", {})
                .get("displayName", "Unassigned"),
                "State": work_item_details["fields"]["System.State"],
                "Story Points": work_item_details["fields"].get(
                    "Microsoft.VSTS.Scheduling.StoryPoints", 0
                ),
                "Stack Rank": work_item_details["fields"].get(
                    "Microsoft.VSTS.Common.StackRank",
                    work_item_details["fields"].get(
                        "Microsoft.VSTS.Common.BacklogPriority", 0
                    ),
                ),
                "Stack Rank Field": (
                    "Microsoft.VSTS.Common.StackRank"
                    if "Microsoft.VSTS.Common.StackRank" in work_item_details["fields"]
                    else "Microsoft.VSTS.Common.BacklogPriority"
                ),
                "Acceptance Criteria": work_item_details["fields"].get(
                    "Microsoft.VSTS.Common.AcceptanceCriteria", ""
                ),
                "Iteration Path": work_item_details["fields"].get(
                    "System.IterationPath", ""
                ),
                "Area Path": work_item_details["fields"].get("System.AreaPath", ""),
                "url": work_item_details["url"],
                "Web URL": work_item_details.get("_links", {})
                .get("html", {})
                .get("href", ""),
                "Original Estimate": work_item_details["fields"].get(
                    "Microsoft.VSTS.Scheduling.OriginalEstimate", 0
                ),
                "Activity": work_item_details["fields"].get(
                    "Microsoft.VSTS.Common.Activity", "Development"
                ),
            }
        )
    return items


def execute_query(query_id):
    """
    Executes a stored query by ID and returns a list of Work Item IDs.
    """
    url = f"https://dev.azure.com/{organization}/{project}/_apis/wit/wiql/{query_id}?api-version=6.0"
    response = requests.get(url, auth=HTTPBasicAuth("", pat_token))

    data = check_response(response, "execute query")

    ids = []
    if "workItems" in data:
        # Flat query
        ids = [item["id"] for item in data["workItems"]]
    elif "workItemRelations" in data:
        # Tree query - extract targets (usually the items we want)
        # or sources depending on what the user wants.
        # For a general "list of stories", we might just take all unique IDs found.
        ids = set()
        for rel in data["workItemRelations"]:
            if rel.get("target"):
                ids.add(rel["target"]["id"])
            if rel.get("source"):
                ids.add(rel["source"]["id"])
        ids = list(ids)

    return ids


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
            "value": item_data.get("Title") or "",
        },
        {
            "op": "add",
            "path": "/fields/System.Description",
            "value": item_data.get("Description") or "",
        },
        {
            "op": "add",
            "path": "/fields/System.AreaPath",
            "value": item_data.get("Area Path") or parent_work_item["Area Path"],
        },
        {
            "op": "add",
            "path": "/fields/System.IterationPath",
            "value": item_data.get("Iteration Path")
            or parent_work_item["Iteration Path"],
        },
    ]

    # Only add parent relation if parent_work_item is provided and has a URL
    if parent_work_item and "url" in parent_work_item:
        patch_document.append(
            {
                "op": "add",
                "path": "/relations/-",
                "value": {
                    "rel": "System.LinkTypes.Hierarchy-Reverse",
                    "url": parent_work_item["url"],
                },
            }
        )

    # Add type-specific fields
    if work_item_type == "Task":
        patch_document.append(
            {
                "op": "add",
                "path": "/fields/Microsoft.VSTS.Scheduling.OriginalEstimate",
                "value": item_data.get("Original Estimate"),
            }
        )
        if "Remaining Work" in item_data:
            patch_document.append(
                {
                    "op": "add",
                    "path": "/fields/Microsoft.VSTS.Scheduling.RemainingWork",
                    "value": item_data.get("Remaining Work"),
                }
            )
        patch_document.append(
            {
                "op": "add",
                "path": "/fields/Microsoft.VSTS.Common.Activity",
                "value": item_data.get("Activity", "Development"),
            }
        )
    elif work_item_type == "User Story":
        if "Acceptance Criteria" in item_data:
            ac_value = item_data.get("Acceptance Criteria") or ""
            # Safety check: if AC is a list, convert to HTML list string
            if isinstance(ac_value, list):
                ac_value = (
                    "<ul>" + "".join([f"<li>{x}</li>" for x in ac_value]) + "</ul>"
                )

            patch_document.append(
                {
                    "op": "add",
                    "path": "/fields/Microsoft.VSTS.Common.AcceptanceCriteria",
                    "value": ac_value,
                }
            )
        if "Story Points" in item_data:
            patch_document.append(
                {
                    "op": "add",
                    "path": "/fields/Microsoft.VSTS.Scheduling.StoryPoints",
                    "value": item_data.get("Story Points"),
                }
            )

    if "Assigned To" in item_data and item_data["Assigned To"]:
        patch_document.append(
            {
                "op": "add",
                "path": "/fields/System.AssignedTo",
                "value": item_data["Assigned To"],
            }
        )

    # Handle CMDB App Name (inherit from parent if not provided)
    cmdb_val = item_data.get("CMDB App Name")
    if not cmdb_val and parent_work_item:
        cmdb_val = parent_work_item.get("CMDB App Name")

    if cmdb_val:
        patch_document.append(
            {
                "op": "add",
                "path": "/fields/Custom.CMDBAppName",
                "value": cmdb_val,
            }
        )

    response = requests.post(
        url,
        json=patch_document,
        headers={"Content-Type": "application/json-patch+json"},
        auth=HTTPBasicAuth("", pat_token),
    )

    return check_response(response, f"create {work_item_type}")


def create_task(parent_work_item, task_data):
    return create_child_work_item(parent_work_item, task_data, "Task")


def update_work_item(work_item_id, updates):
    """
    Updates a work item with the given fields.
    updates: dict of field_name -> new_value
    Example updates:
    {
        "System.Description": "New description...",
        "Microsoft.VSTS.Common.AcceptanceCriteria": "New AC..."
    }
    """
    url = f"https://dev.azure.com/{organization}/{project}/_apis/wit/workitems/{work_item_id}?api-version=6.0"

    patch_document = []
    for field, value in updates.items():
        patch_document.append(
            {
                "op": "add",  # "add" functions as replace/update if field exists
                "path": f"/fields/{field}",
                "value": value,
            }
        )

    response = requests.patch(
        url,
        json=patch_document,
        headers={"Content-Type": "application/json-patch+json"},
        auth=HTTPBasicAuth("", pat_token),
    )

    return check_response(response, f"update work item {work_item_id}")


def get_iterations_by_path(path_str):
    """
    Fetches children iterations for a given path string (e.g. "Platts\\Scrum\\26.02")
    Returns a list of iteration node objects with keys: Name, Path, ID.
    """
    # Remove project name from path if present at start (Classification Nodes API expects path relative to project)
    normalized_path = path_str.replace("\\", "/")
    if normalized_path.startswith(f"{project}/"):
        relative_path = normalized_path[len(project) + 1 :]
    else:
        relative_path = normalized_path

    url = f"https://dev.azure.com/{organization}/{project}/_apis/wit/classificationnodes/Iterations/{relative_path}?$depth=1&api-version=6.0"

    response = requests.get(url, auth=HTTPBasicAuth("", pat_token))

    if response.status_code == 404:
        return []

    data = check_response(response, "fetch iterations")

    children = []
    if "children" in data:
        for child in data["children"]:
            # Construct the absolute path for 'System.IterationPath'
            full_path = f"{path_str}\\{child['name']}"
            children.append(
                {"Name": child["name"], "Path": full_path, "ID": child["id"]}
            )

    return children
