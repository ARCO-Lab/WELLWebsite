# This script downloads and processes new sampling data files from the Borealis Dataverse API.
# It tracks processed files, downloads unprocessed ones, and invokes inject_sampling.py to import data.

import os
import sys
import pathlib
import json
import argparse
import requests
from datetime import datetime
from dotenv import load_dotenv
from dateutil import parser as date_parser
import io
import re
import tempfile
import subprocess

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from config import Config

load_dotenv()

# Environment variables
BOREALIS_URL = Config.DEMO_BOREALIS_URL
BOREALIS_API_TOKEN = Config.BOREALIS_API_TOKEN
BOREALIS_AW_PERSISTENT_ID = Config.DEMO_BOREALIS_AW_PERSISTENT_ID


# Persistent state file to track all processed files
STATE_FILE = os.path.join(os.path.dirname(__file__), "..", "logs", "processed.json")
STATE_FILE = os.path.abspath(STATE_FILE)

def load_state():
    """Load all processed files from state file."""
    print("DEBUG: Loading processed files state from", STATE_FILE)
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
                processed_files = data.get("processed_files", [])
                print(f"DEBUG: Loaded {len(processed_files)} processed files")
                for pf in processed_files:
                    print(f"DEBUG: Processed file: {pf.get('filename')} (ID: {pf.get('id')}, Created: {pf.get('create_date')})")
                return processed_files
        except Exception as e:
            print(f"ERROR: Failed to load {STATE_FILE}: {e}")
            print("DEBUG: Using empty processed files list")
            return []
    print("DEBUG: No state file found, returning empty processed files list")
    return []

def save_state(processed_files):
    """Save all processed files to state file."""
    print(f"DEBUG: Saving {len(processed_files)} processed files to state")
    try:
        data = {"processed_files": processed_files}
        with open(STATE_FILE, "w") as f:
            json.dump(data, f, indent=2)
        print(f"DEBUG: Saved state to {STATE_FILE}")
    except Exception as e:
        print(f"ERROR: Failed to save {STATE_FILE}: {e}")

def parse_filename_date(filename):
    """Parse date from filename suffix after WELLAncasterWatershed_, if possible."""
    print(f"DEBUG: Parsing filename: {filename}")
    match = re.search(r'WELLAncasterWatershed_(.+?)\.(xlsx|tab)', filename, re.IGNORECASE)
    if not match:
        print(f"ERROR: Invalid filename format: {filename}")
        raise ValueError(f"Invalid filename format: {filename}")
    suffix = match.group(1)
    
    # Try to parse suffix as MonthYear (e.g., Jan2025) or Season+Year (e.g., Spring2026)
    try:
        return datetime.strptime(suffix, "%b%Y")
    except ValueError:
        try:
            # Handle season names
            season_map = {
                'spring': 'Mar', 'summer': 'Jun', 
                'fall': 'Sep', 'autumn': 'Sep', 'winter': 'Dec'
            }
            season_match = re.match(r'(spring|summer|fall|autumn|winter)(\d{4})', suffix.lower())
            if season_match:
                season, year = season_match.groups()
                month_abbr = season_map[season]
                return datetime.strptime(f"{month_abbr}{year}", "%b%Y")
        except ValueError:
            pass
        print(f"DEBUG: Failed to parse date from suffix: {suffix}. Falling back to create_date.")
        return None

def get_files_from_dataset(list_files=False):
    """Fetch all files from dataset matching WELLAncasterWatershed_, excluding SAMPLE."""
    print(f"DEBUG: Fetching dataset with persistent ID: {BOREALIS_AW_PERSISTENT_ID}")
    
    if not all([BOREALIS_URL, BOREALIS_API_TOKEN, BOREALIS_AW_PERSISTENT_ID]):
        missing = [k for k, v in {
            "DEMO_BOREALIS_URL": BOREALIS_URL,
            "BOREALIS_API_TOKEN": BOREALIS_API_TOKEN,
            "BOREALIS_AW_PERSISTENT_ID": BOREALIS_AW_PERSISTENT_ID
        }.items() if not v]
        print(f"ERROR: Missing environment variables: {', '.join(missing)}")
        raise ValueError(f"Missing environment variables: {', '.join(missing)}")
    
    try:
        headers = {"X-Dataverse-key": BOREALIS_API_TOKEN}
        params = {"persistentId": BOREALIS_AW_PERSISTENT_ID}
        print(f"DEBUG: Sending request to {BOREALIS_URL}/api/datasets/:persistentId")
        response = requests.get(f"{BOREALIS_URL}/api/datasets/:persistentId", params=params, headers=headers)
        print(f"DEBUG: Response status: {response.status_code}")
        print(f"DEBUG: Response URL: {response.url}")
        response.raise_for_status()
        
        data = response.json()["data"]
        latest_version = data["latestVersion"]
        
        if latest_version["versionState"] != "RELEASED":
            print(f"DEBUG: Dataset version state is {latest_version['versionState']}, not RELEASED.")
            return []
        
        files = latest_version["files"]
        if not files:
            print("DEBUG: No files in the dataset.")
            return []
        
        # Filter for files with .xlsx or .tab extension, excluding SAMPLE
        target_files = []
        for f in files:
            datafile = f["dataFile"]
            filename = datafile["filename"]
            file_id = datafile["id"]
            create_date = datafile.get("createDate", datafile.get("creationDate"))
            restricted = datafile.get("restricted", False)
            
            # Check if file matches criteria
            if (filename.lower().startswith("wellancasterwatershed_") and
                not restricted and
                not re.match(r'WELLAncasterWatershed_SAMPLE\.(xlsx|tab)', filename, re.IGNORECASE) and
                filename.lower().endswith((".xlsx", ".tab"))):
                
                # Parse create_date
                if create_date:
                    create_date_parsed = date_parser.parse(create_date)
                else:
                    create_date_parsed = datetime.now()
                    print(f"DEBUG: No createDate for {filename}, using current time: {create_date_parsed}")
                
                target_files.append({
                    "filename": filename,
                    "id": file_id,
                    "create_date": create_date_parsed
                })
        
        if list_files:
            print("DEBUG: All files in dataset:")
            for tf in target_files:
                print(f"  - File: {tf['filename']}, ID: {tf['id']}, Created: {tf['create_date']}")
        
        print(f"DEBUG: Found {len(target_files)} matching files")
        return target_files
        
    except requests.exceptions.HTTPError as e:
        print(f"ERROR: HTTP error: {e}")
        if e.response:
            print(f"DEBUG: Response content: {e.response.text}")
        raise
    except Exception as e:
        print(f"ERROR: Error fetching dataset: {e}")
        raise

def download_file_to_memory(file_id, filename):
    """Download file content to memory as BytesIO, ensuring original format."""
    print(f"DEBUG: Downloading file ID {file_id} to memory (original format)")
    
    try:
        headers = {"X-Dataverse-key": BOREALIS_API_TOKEN}
        params = {"format": "original"}
        response = requests.get(f"{BOREALIS_URL}/api/access/datafile/{file_id}", headers=headers, params=params)
        response.raise_for_status()
        
        file_buffer = io.BytesIO(response.content)
        print("DEBUG: Downloaded to memory")
        return file_buffer
    except requests.exceptions.HTTPError as e:
        if e.response and e.response.status_code == 403:
            print("ERROR: Access denied to file. Check API token permissions.")
        raise
    except Exception as e:
        print(f"ERROR: downloading file: {e}")
        raise

def process_single_file(file_info):
    """Process a single file and return the temporary file path."""
    filename = file_info["filename"]
    file_id = file_info["id"]
    create_date = file_info["create_date"]
    
    print(f"DEBUG: Processing file: {filename} (ID: {file_id}, Created: {create_date})")
    
    file_buffer = download_file_to_memory(file_id, filename)
    
    # Save buffer to temporary file with .xlsx extension
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_file:
        tmp_file.write(file_buffer.getvalue())
        tmp_file_path = tmp_file.name
    
    print(f"DEBUG: Saved file to temporary path: {tmp_file_path}")
    return tmp_file_path

def main():
    # Main entry point for downloading and processing files
    parser = argparse.ArgumentParser(description="Download all unprocessed files and process them sequentially.")
    parser.add_argument("--force", action="store_true", help="Force processing even if file is not new")
    parser.add_argument("--list-files", action="store_true", help="List all files in the dataset for debugging")
    args = parser.parse_args()

    print("DEBUG: Starting process...")
    print(f"DEBUG: BOREALIS_URL: {BOREALIS_URL}")
    print(f"DEBUG: BOREALIS_API_TOKEN: {'***' if BOREALIS_API_TOKEN else 'Not set'}")
    print(f"DEBUG: BOREALIS_AW_PERSISTENT_ID: {BOREALIS_AW_PERSISTENT_ID}")

    try:
        # Load processed files state
        processed_files = load_state()
        processed_ids = {pf["id"] for pf in processed_files}
        
        # Get all files from dataset
        all_files = get_files_from_dataset(list_files=args.list_files)
        if not all_files:
            print("No files to process. Use --list-files to debug available files.")
            sys.exit(1 if args.list_files else 0)
        
        # Find unprocessed files
        unprocessed_files = [f for f in all_files if f["id"] not in processed_ids]
        
        # Sort unprocessed files by creation date (oldest first)
        unprocessed_files.sort(key=lambda x: x["create_date"])
        
        print(f"DEBUG: Processed files: {len(processed_files)}")
        print(f"DEBUG: Unprocessed files: {[f['filename'] for f in unprocessed_files]}")
        
        if not unprocessed_files and not args.force:
            print("DEBUG: All files have been processed.")
            # Still output something for scheduler compatibility
            print("OUTPUT: NO_NEW_FILES")
            sys.exit(0)
        
        # Determine which files to process
        files_to_process = []
        if args.force:
            if unprocessed_files:
                files_to_process = unprocessed_files
                print(f"DEBUG: Force mode - processing {len(files_to_process)} unprocessed files")
            else:
                # If forcing and no unprocessed files, process all files
                files_to_process = sorted(all_files, key=lambda x: x["create_date"])
                print(f"DEBUG: Force mode - reprocessing all {len(files_to_process)} files")
        else:
            files_to_process = unprocessed_files
        
        if not files_to_process:
            print("DEBUG: No files to process.")
            print("OUTPUT: NO_FILES")
            sys.exit(0)
        
        print(f"DEBUG: Will process {len(files_to_process)} files in chronological order")
        
        # Process each file sequentially
        processed_count = 0
        for i, file_to_process in enumerate(files_to_process, 1):
            print(f"\nDEBUG: === Processing file {i}/{len(files_to_process)} ===")
            
            try:
                # Process the file
                tmp_file_path = process_single_file(file_to_process)
                
                # Import the data using inject_sampling.py
                script_dir = os.path.dirname(__file__)
                inject_script = os.path.join(script_dir, "inject_sampling.py")
                python_exe = sys.executable
                
                print(f"DEBUG: Running inject_sampling.py for {file_to_process['filename']}")
                result = subprocess.run([python_exe, inject_script, tmp_file_path], 
                                      capture_output=True, text=True)
                
                # Print the output from inject_sampling.py
                if result.stdout:
                    print("inject_sampling.py stdout:", result.stdout)
                if result.stderr:
                    print("inject_sampling.py stderr:", result.stderr)
                
                if result.returncode != 0:
                    print(f"ERROR: inject_sampling.py failed with return code {result.returncode}")
                    # Clean up temp file
                    try:
                        os.unlink(tmp_file_path)
                        print(f"DEBUG: Cleaned up temporary file: {tmp_file_path}")
                    except:
                        pass
                    continue
                
                # Clean up temporary file
                try:
                    os.unlink(tmp_file_path)
                    print(f"DEBUG: Cleaned up temporary file: {tmp_file_path}")
                except Exception as e:
                    print(f"WARNING: Failed to clean up temporary file {tmp_file_path}: {e}")
                
                # Check if any records were inserted
                inserted = 0
                for line in result.stdout.splitlines():
                    match = re.search(r"\[INFO\] Inserted (\d+) new sampling records\.", line)
                    if match:
                        inserted = int(match.group(1))
                        break

                if inserted > 0:
                    # Update processed files state
                    file_record = {
                        "filename": file_to_process["filename"],
                        "id": file_to_process["id"],
                        "create_date": file_to_process["create_date"].isoformat()
                    }
                    # Remove existing record with same ID (in case of force mode)
                    processed_files = [pf for pf in processed_files if pf["id"] != file_to_process["id"]]
                    processed_files.append(file_record)
                    processed_count += 1
                    print(f"DEBUG: Successfully processed {file_to_process['filename']} (Inserted {inserted} records)")
                else:
                    print(f"DEBUG: Skipping {file_to_process['filename']} (Inserted 0 records, not marking as processed)")
                
            except Exception as e:
                print(f"ERROR: Failed to process {file_to_process['filename']}: {e}")
                continue
        
        # Save updated state
        save_state(processed_files)
        
        print(f"\nDEBUG: === Processing Complete ===")
        print(f"DEBUG: Successfully processed {processed_count} out of {len(files_to_process)} files")
        
        # Output for scheduler compatibility
        if processed_count > 0:
            print(f"OUTPUT: PROCESSED_{processed_count}_FILES")
        else:
            print("OUTPUT: NO_FILES_PROCESSED")
        
    except Exception as e:
        print(f"ERROR: Process failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()