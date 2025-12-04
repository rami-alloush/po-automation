import requests
import os
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth
import json

load_dotenv()
pat_token = os.getenv("ADO_PAT_TOKEN")
organization = "spglobal"
project = "Platts"
work_item_id = "9988957"

url = f"https://dev.azure.com/{organization}/{project}/_apis/wit/workitems/{work_item_id}?api-version=6.0"
response = requests.get(url, auth=HTTPBasicAuth("", pat_token))

if response.status_code == 200:
    data = response.json()
    for key in sorted(data["fields"].keys()):
        print(key)
else:
    print(response.status_code, response.text)
