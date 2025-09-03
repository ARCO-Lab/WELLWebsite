import os
import requests
from dotenv import load_dotenv

load_dotenv()

BOREALIS_URL = os.getenv("borealis_url")
BOREALIS_API_TOKEN = os.getenv("borealis_api_token")
DOWNLOAD_DIR = "app/downloads"

def list_files():
    # Example: List files in a Dataverse dataset (replace with your actual API endpoint)
    headers = {"X-Dataverse-key": BOREALIS_API_TOKEN}
    resp = requests.get(f"{BOREALIS_URL}/api/access/dataset/:persistentId?persistentId=YOUR_DATASET_PID", headers=headers)
    resp.raise_for_status()
    files = resp.json()["data"]["latestVersion"]["files"]
    return [f for f in files if f["dataFile"]["filename"].startswith("WELLAncasterWatershed")]

def download_file(file_id, filename):
    headers = {"X-Dataverse-key": BOREALIS_API_TOKEN}
    url = f"{BOREALIS_URL}/api/access/datafile/{file_id}"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    with open(os.path.join(DOWNLOAD_DIR, filename), "wb") as f:
        f.write(resp.content)
    print(f"Downloaded {filename}")

def main():
    files = list_files()
    for f in files:
        file_id = f["dataFile"]["id"]
        filename = f["dataFile"]["filename"]
        local_path = os.path.join(DOWNLOAD_DIR, filename)
        if not os.path.exists(local_path):
            download_file(file_id, filename)

if __name__ == "__main__":
    main()