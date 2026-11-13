# This script downloads and processes new sampling data files from the Borealis Dataverse API.
# It tracks processed files, downloads unprocessed ones, and invokes inject_sampling.py to import data.
# Only the dataset's published version is read: a file uploaded but not yet published (still in the draft) is
# imported on the first run after a curator publishes it, and the log says when a draft is waiting. Restricted
# files are skipped, so reading needs no token; BOREALIS_API_TOKEN is sent when it is set (an invalid one fails the run).
# A file that fails validation is recorded as refused (logs/processed.json, by Dataverse file id), its problems are
# logged once, and it isn't retried: a corrected upload gets a new id. A run that refused or failed to import a file
# reports OUTPUT: REJECTED_<n>_FILES or FAILED_<n>_FILES and exits 1, so the scheduler reports it as a failure.
# A logs/processed.json that exists but can't be read stops the run before anything is downloaded (exit 1, so the
# download heartbeat gets /fail), and a copy is kept in logs/processed.json.bad; it is never read as empty.
# Files are imported oldest first (by upload date, then Dataverse file id, which only grows, so same-day uploads keep
# their upload order), so when a newer file has a different value for a stored reading, the newer value is the one
# kept (inject_sampling.py applies it and logs a [CORRECTED] line). A file imported after a newer one (an older file
# whose import failed and is retried, or one re-imported with --force) gets the newer files' scopes (what each
# covers, recorded in logs/processed.json) and doesn't change the readings they cover: those corrections are held
# back and reported. Held corrections and stored readings a file covers but no longer has get an ATTENTION: line,
# which the scheduler sends to Sentry as a warning, and the run's SUMMARY: line counts them with the new and
# corrected rows.
#   python scripts/download_data.py                          import every new file
#   python scripts/download_data.py --force --file 57195     import that file again, even if processed or refused
#                                                            (its corrections apply, except to readings that a
#                                                            newer imported file covers)
#   python scripts/download_data.py --list-files             list the dataset's files only

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
import shutil
import tempfile
import subprocess

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from config import Config
from utils.sampling_csv import INVALID_FILE_EXIT
from utils.borealis import Dataverse, DataverseError, api_base, base_url, is_demo, published_files

load_dotenv()

# Environment variables (config.py: the BOREALIS_* names, or the older DEMO_* ones)
BOREALIS_URL = Config.BOREALIS_URL
BOREALIS_API_TOKEN = Config.BOREALIS_API_TOKEN
BOREALIS_AW_PERSISTENT_ID = Config.BOREALIS_SAMPLING_PERSISTENT_ID


# Persistent state file to track all processed files
STATE_FILE = os.path.join(os.path.dirname(__file__), "..", "logs", "processed.json")
STATE_FILE = os.path.abspath(STATE_FILE)

class StateFileError(Exception):
    """logs/processed.json exists but can't be read as the state file."""


def keep_bad_copy(path):
    """Copy an unreadable state file to <path>.bad (replacing an older copy), so a person can see what was in it
    and repair it. The path of the copy, or None if the copy failed too."""
    try:
        shutil.copy2(path, path + ".bad")
        return path + ".bad"
    except OSError:
        return None


def load_state():
    """The state file: {"processed_files": [...], "refused_files": [...]}, each entry a dataset file (id, filename,
    create_date). A refused file failed validation; its entry also has "errors" (the problem count) and
    "refused_at". Both lists are keyed by the Dataverse file id, which a corrected re-upload doesn't share.

    No file means an empty state (the first run). A file that exists but can't be read raises StateFileError, after
    a copy is kept in processed.json.bad: read as empty, every dataset file would be imported again, oldest first,
    bringing back rows a person deleted and undoing corrections that were held back."""
    print("DEBUG: Loading processed files state from", STATE_FILE)
    state = {"processed_files": [], "refused_files": []}
    if not os.path.exists(STATE_FILE):
        print("DEBUG: No state file found, starting from an empty state")
        return state
    try:
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("it doesn't hold a JSON object")
        for key in state:
            value = data.get(key, [])
            if not isinstance(value, list) or not all(isinstance(entry, dict) for entry in value):
                raise ValueError(f"{key} isn't a list of files")
            state[key] = value
    except (OSError, ValueError) as e:   # json.JSONDecodeError and UnicodeDecodeError are ValueErrors
        copy = keep_bad_copy(STATE_FILE)
        raise StateFileError(
            f"{STATE_FILE} can't be read ({e}), so nothing was downloaded or imported. "
            + (f"A copy is in {copy}. " if copy else "")
            + "Repair the file (or restore it from a backup) and run again; deleting it would import every dataset "
              "file again.") from None
    print(f"DEBUG: Loaded {len(state['processed_files'])} processed and {len(state['refused_files'])} refused files")
    for pf in state["processed_files"]:
        print(f"DEBUG: Processed file: {pf.get('filename')} (ID: {pf.get('id')}, Created: {pf.get('create_date')})")
    return state

def save_state(state):
    """Save the state file (see load_state)."""
    print(f"DEBUG: Saving {len(state['processed_files'])} processed and {len(state['refused_files'])} refused files")
    try:
        # Written to a temporary file and renamed, so a crash or a full disk leaves the previous state intact
        with open(STATE_FILE + ".tmp", "w") as f:
            json.dump({"processed_files": state["processed_files"], "refused_files": state["refused_files"]}, f,
                      indent=2)
        os.replace(STATE_FILE + ".tmp", STATE_FILE)
        print(f"DEBUG: Saved state to {STATE_FILE}")
    except Exception as e:
        print(f"ERROR: Failed to save {STATE_FILE}: {e}")

def parse_filename_date(filename):
    """Parse date from filename suffix after WELLAncasterWatershed_, if possible."""
    print(f"DEBUG: Parsing filename: {filename}")
    match = re.search(r'WELLAncasterWatershed_(.+?)\.(xlsx|tab|csv)', filename, re.IGNORECASE)
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
            pass   # not a season name either; reported just below and the caller falls back to create_date
        print(f"DEBUG: Failed to parse date from suffix: {suffix}. Falling back to create_date.")
        return None

def get_files_from_dataset(list_files=False, client=None):
    """Fetch all files from the dataset's published version matching WELLAncasterWatershed_, excluding SAMPLE."""
    print(f"DEBUG: Fetching dataset with persistent ID: {BOREALIS_AW_PERSISTENT_ID}")

    missing = [k for k, v in {"BOREALIS_URL": BOREALIS_URL,
                              "BOREALIS_SAMPLING_PERSISTENT_ID": BOREALIS_AW_PERSISTENT_ID}.items() if not v]
    if missing:
        print(f"ERROR: Missing environment variables: {', '.join(missing)}")
        raise ValueError(f"Missing environment variables: {', '.join(missing)}")
    server = api_base(BOREALIS_URL)   # logs, once, which server the download reads from
    if is_demo(server) != is_demo(persistent_id=BOREALIS_AW_PERSISTENT_ID):
        message = (f"BOREALIS_URL is {server} but the dataset {BOREALIS_AW_PERSISTENT_ID} is on the "
                   f"{'production' if is_demo(server) else 'demo'} server: set "
                   f"BOREALIS_SAMPLING_PERSISTENT_ID to the sampling dataset's id on {server}")
        print(f"ERROR: {message}")
        raise ValueError(message)
    if not BOREALIS_API_TOKEN:
        print("DEBUG: BOREALIS_API_TOKEN is not set; reading the dataset as a guest (public files only)")

    try:
        client = client or Dataverse(BOREALIS_URL, BOREALIS_API_TOKEN)
        files = published_files(client, BOREALIS_AW_PERSISTENT_ID)
        if not files:
            print("DEBUG: No files in the dataset's published version.")
            return []

        # Filter for .xlsx, .tab (how Dataverse lists an ingested table) or .csv files, excluding SAMPLE
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
                not re.match(r'WELLAncasterWatershed_SAMPLE\.(xlsx|tab|csv)', filename, re.IGNORECASE) and
                filename.lower().endswith((".xlsx", ".tab", ".csv"))):
                
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
        
    except DataverseError as e:
        print(f"ERROR: {e}")
        raise
    except Exception as e:
        print(f"ERROR: Error fetching dataset: {e}")
        raise

def download_file_to_memory(file_id, filename):
    """Download file content to memory as BytesIO, ensuring original format."""
    print(f"DEBUG: Downloading file ID {file_id} to memory (original format)")
    
    try:
        headers = {"X-Dataverse-key": BOREALIS_API_TOKEN} if BOREALIS_API_TOKEN else {}
        params = {"format": "original"}
        response = requests.get(f"{base_url(BOREALIS_URL)}/api/access/datafile/{file_id}", headers=headers,
                                params=params, timeout=(10, 600))
        response.raise_for_status()
        
        file_buffer = io.BytesIO(response.content)
        print("DEBUG: Downloaded to memory")
        return file_buffer
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else None
        if status in (401, 403):
            print(f"ERROR: Access denied to file {file_id} (HTTP {status}). Check BOREALIS_API_TOKEN (unset it to read "
                  f"as a guest) and that the file is published and not restricted.")
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
    
    # Save buffer to a temporary file (named .xlsx whatever it holds: the import tells Excel from CSV by content)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_file:
        tmp_file.write(file_buffer.getvalue())
        tmp_file_path = tmp_file.name
    
    print(f"DEBUG: Saved file to temporary path: {tmp_file_path}")
    return tmp_file_path

def is_named(file_info, names):
    """True if the file's id or filename is among `names` (as given with --file)."""
    return str(file_info["id"]) in names or file_info["filename"] in names


def choose_files(all_files, state, names=(), force=False):
    """The files to import this run, oldest first.

    New files: neither processed nor refused. With --force, the files named with --file are imported again even if
    they were processed or refused (e.g. after a site was added to the site list). --force alone re-imports nothing,
    so a refused file isn't retried until a corrected file is uploaded (which gets a new id).
    """
    done = {pf["id"] for pf in state["processed_files"]} | {rf["id"] for rf in state["refused_files"]}
    chosen = [f for f in all_files if f["id"] not in done or (force and is_named(f, names))]
    # Dataverse file ids only grow, so they order same-day uploads (whose create_date can tie)
    return sorted(chosen, key=lambda f: (f["create_date"], int(f["id"])))


def newer_files(state, file_info):
    """The processed files newer (higher Dataverse id) than `file_info`, as inject_sampling.py's --newer list:
    {"file": name and id, "scope": what it covers, or None if unknown (processed before scopes were recorded),
    which counts as covering everything}."""
    return [{"file": f"{pf['filename']} (ID: {pf['id']})", "scope": pf.get("scope")}
            for pf in state["processed_files"] if int(pf["id"]) > int(file_info["id"])]


def record(state, file_info, outcome, errors=0, scope=None):
    """Record a file as "processed" (with `scope`, what it covers) or "refused", replacing any earlier entry for its
    id."""
    entry = {"filename": file_info["filename"], "id": file_info["id"],
             "create_date": file_info["create_date"].isoformat()}
    for key in ("processed_files", "refused_files"):
        state[key] = [f for f in state[key] if f["id"] != file_info["id"]]
    if outcome == "refused":
        entry.update(errors=errors, refused_at=datetime.now().isoformat(timespec="seconds"))
        state["refused_files"].append(entry)
    else:
        entry["scope"] = scope
        state["processed_files"].append(entry)


def import_outcome(returncode, stdout):
    """("processed", rows inserted), ("refused", problem count) or ("failed", None) for one inject_sampling.py run.
    It exits with INVALID_FILE_EXIT when the file itself is invalid (nothing stored); any other non-zero code is a
    failure worth retrying, e.g. the database was down."""
    if returncode == 0:
        match = re.search(r"^\[INFO\] Inserted (\d+) new sampling records\.", stdout or "", flags=re.MULTILINE)
        return "processed", int(match.group(1)) if match else 0
    if returncode == INVALID_FILE_EXIT:
        match = re.search(r"^\[ERROR\] (\d+) problems in ", stdout or "", flags=re.MULTILINE)
        return "refused", int(match.group(1)) if match else 0
    return "failed", None


# The lines inject_sampling.py prints for a stored file, and the count each one gives
_COUNT_LINES = {
    "inserted": r"^\[INFO\] Inserted (\d+) new sampling records\.",
    "corrected": r"^\[INFO\] Corrected (\d+) stored sampling records",
    "withdrawn": r"^\[WARN\] (\d+) rows present in the DB but not in the latest file",
    "held": r"^\[WARN\] (\d+) corrections not applied",
}


def import_counts(stdout):
    """{"inserted", "corrected", "withdrawn", "held"} row counts from a successful inject_sampling.py run's output (0
    for a line it didn't print)."""
    counts = {}
    for name, pattern in _COUNT_LINES.items():
        match = re.search(pattern, stdout or "", flags=re.MULTILINE)
        counts[name] = int(match.group(1)) if match else 0
    return counts


def import_scope(stdout):
    """The file's scope from inject_sampling.py's [SCOPE] line (JSON), or None if it printed none."""
    match = re.search(r"^\[SCOPE\] (.+)$", stdout or "", flags=re.MULTILINE)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except ValueError:
        return None


def run_status(processed, refused, failed):
    """The OUTPUT status for the scheduler. A refused or failed file also makes the run exit 1."""
    if refused:
        return f"REJECTED_{refused}_FILES"
    if failed:
        return f"FAILED_{failed}_FILES"
    return f"PROCESSED_{processed}_FILES" if processed else "NO_FILES_PROCESSED"


def import_file(file_info, inject_script, newer=()):
    """Download one file and run inject_sampling.py on it, with `newer` (newer_files) as --newer. Returns
    import_outcome()'s pair, the run's import_counts() and the file's import_scope()."""
    tmp_file_path = None
    try:
        tmp_file_path = process_single_file(file_info)
        print(f"DEBUG: Running inject_sampling.py for {file_info['filename']}")
        cmd = [sys.executable, inject_script, tmp_file_path]
        if newer:
            cmd += ["--newer", json.dumps(newer)]
            print(f"DEBUG: {len(newer)} newer files are already imported; their readings keep their values")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.stdout:
            print("inject_sampling.py stdout:", result.stdout)
        if result.stderr:
            print("inject_sampling.py stderr:", result.stderr)
        if result.returncode not in (0, INVALID_FILE_EXIT):
            print(f"ERROR: inject_sampling.py failed with return code {result.returncode}")
        outcome, number = import_outcome(result.returncode, result.stdout)
        ok = result.returncode == 0
        return outcome, number, import_counts(result.stdout if ok else ""), import_scope(result.stdout) if ok else None
    except Exception as e:
        print(f"ERROR: Failed to process {file_info['filename']}: {e}")
        return "failed", None, import_counts(""), None
    finally:
        if tmp_file_path:
            try:
                os.unlink(tmp_file_path)
                print(f"DEBUG: Cleaned up temporary file: {tmp_file_path}")
            except Exception as e:
                print(f"WARNING: Failed to clean up temporary file {tmp_file_path}: {e}")


def main():
    # Main entry point for downloading and processing files
    parser = argparse.ArgumentParser(description="Download all unprocessed files and process them sequentially.")
    parser.add_argument("--force", action="store_true",
                        help="Import the files named with --file again, even if they were processed or refused")
    parser.add_argument("--file", action="append", default=[], metavar="ID_OR_NAME",
                        help="With --force: a dataset file id or filename to import again (repeatable)")
    parser.add_argument("--list-files", action="store_true", help="List the dataset's files and exit, without downloading or importing anything")
    args = parser.parse_args()
    if args.file and not args.force:
        parser.error("--file only applies with --force")

    print("DEBUG: Starting process...")
    print(f"DEBUG: BOREALIS_URL: {BOREALIS_URL}")
    print(f"DEBUG: BOREALIS_API_TOKEN: {'***' if BOREALIS_API_TOKEN else 'Not set'}")
    print(f"DEBUG: BOREALIS_SAMPLING_PERSISTENT_ID: {BOREALIS_AW_PERSISTENT_ID}")

    try:
        state = load_state()

        # Get all files from dataset
        all_files = get_files_from_dataset(list_files=args.list_files)
        # A --file that names no file of the dataset is a typo; importing nothing would hide it
        unmatched = [name for name in args.file if not any(is_named(f, [name]) for f in all_files)]
        if unmatched:
            print(f"ERROR: --file {', '.join(unmatched)} matches no file of the dataset (give a file id or its exact "
                  f"filename; --list-files lists them)")
            sys.exit(2)
        if not all_files:
            print("No files to process. Use --list-files to debug available files.")
            if args.list_files:
                sys.exit(1)
            print("OUTPUT: NO_NEW_FILES")   # the scheduler reads this line (utils/jobs.download_status)
            sys.exit(0)

        files_to_process = choose_files(all_files, state, args.file, args.force)
        print(f"DEBUG: Processed files: {len(state['processed_files'])}")
        print(f"DEBUG: Files to import: {[f['filename'] for f in files_to_process]}")
        # A refused file's problems were listed when it was refused; later runs give a one-line reminder, for the
        # refused files still in the dataset (one deleted from it needs no correction)
        chosen_ids = {f["id"] for f in files_to_process}
        dataset_ids = {f["id"] for f in all_files}
        for rf in state["refused_files"]:
            if rf["id"] in dataset_ids and rf["id"] not in chosen_ids:
                print(f"WARNING: {rf['filename']} (ID: {rf['id']}) was refused on {rf.get('refused_at', '?')} with "
                      f"{rf.get('errors', '?')} problems; upload a corrected file to import it")

        # --list-files only lists; it never downloads or imports. The scheduler runs it under a short
        # time limit to debug a failed download, and an import stopped part-way could lose rows.
        if args.list_files:
            sys.exit(0)

        if not files_to_process:
            print("DEBUG: All files have been processed.")
            print("OUTPUT: NO_NEW_FILES")
            sys.exit(0)

        print(f"DEBUG: Will process {len(files_to_process)} files in chronological order")
        inject_script = os.path.join(os.path.dirname(__file__), "inject_sampling.py")
        counts = {"processed": 0, "refused": 0, "failed": 0}
        rows = import_counts("")
        for i, file_info in enumerate(files_to_process, 1):
            print(f"\nDEBUG: === Processing file {i}/{len(files_to_process)} ===")
            outcome, number, file_rows, scope = import_file(file_info, inject_script, newer_files(state, file_info))
            counts[outcome] += 1
            if outcome == "processed":
                # Recorded even when every row was already stored: importing it again would add nothing
                record(state, file_info, "processed", scope=scope)
                rows = {name: rows[name] + file_rows[name] for name in rows}
                print(f"DEBUG: Successfully processed {file_info['filename']} (Inserted {number} records, corrected "
                      f"{file_rows['corrected']})")
                # The scheduler sends ATTENTION: lines to Sentry: these rows need a person's decision
                if file_rows["withdrawn"]:
                    print(f"ATTENTION: {file_info['filename']} (ID: {file_info['id']}): {file_rows['withdrawn']} rows "
                          f"present in the DB but not in the latest file were kept; see the [WARN] lines above and "
                          f"delete them by hand if the file withdrew them.")
                if file_rows["held"]:
                    print(f"ATTENTION: {file_info['filename']} (ID: {file_info['id']}): {file_rows['held']} corrections "
                          f"not applied, because a newer file already imported covers those readings; see the [WARN] "
                          f"lines above.")
            elif outcome == "refused":
                record(state, file_info, "refused", number)
                print(f"ERROR: {file_info['filename']} (ID: {file_info['id']}) was refused: {number} problems, listed "
                      f"above. Nothing from it was imported, and it won't be retried; upload a corrected file.")
            else:
                print(f"ERROR: Importing {file_info['filename']} failed; it will be retried next run")

        save_state(state)
        print("\nDEBUG: === Processing Complete ===")
        print(f"DEBUG: {counts['processed']} processed, {counts['refused']} refused, {counts['failed']} failed, "
              f"out of {len(files_to_process)} files")
        print(f"SUMMARY: {rows['inserted']} new, {rows['corrected']} corrected, {rows['held']} corrections not "
              f"applied (a newer file covers them), {rows['withdrawn']} rows present in the DB but not in the latest "
              f"file")
        # The scheduler reads this line (utils/jobs.download_status)
        print(f"OUTPUT: {run_status(counts['processed'], counts['refused'], counts['failed'])}")
        if counts["refused"] or counts["failed"]:
            sys.exit(1)

    except SystemExit:
        raise
    except Exception as e:
        print(f"ERROR: Process failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
