# This script exports one month of WELL sensor data to CSV (the same file scripts/upload_data.py sends to Borealis)
# and uploads it to a SharePoint document library through Microsoft Graph, as a second off-VM copy, in a folder per
# year: <SHAREPOINT_FOLDER>/<year>/WELLWestCampus_<Mon><YYYY>.csv. utils/sharepoint.py lists the settings.
#   python scripts/sharepoint_upload.py --year 2026 --month 10    that month
#   python scripts/sharepoint_upload.py                           last month
#   python scripts/sharepoint_upload.py --check                   sign in and find the site, library and folder;
#                                                                 uploads nothing
# Running it again for a month is safe: an identical file isn't sent again, and a changed one replaces the old copy
# (SharePoint keeps it in the file's version history). It prints "Successfully uploaded <file> to SharePoint" only
# when the file is there; the scheduler records the month as done only then (logs/sharepoint_uploaded_months.json).

import argparse
import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv  # noqa: E402
from utils import sharepoint  # noqa: E402

load_dotenv()


def configured_client(session=None):
    """A SharePoint client from the environment. Exits 1 when the settings are off or incomplete."""
    state, missing = sharepoint.status()
    if state == "off":
        print("ERROR: SharePoint upload is off: set SHAREPOINT_TENANT_ID, SHAREPOINT_CLIENT_ID, "
              "SHAREPOINT_CLIENT_SECRET and SHAREPOINT_SITE (see utils/sharepoint.py)")
        sys.exit(1)
    if state == "incomplete":
        print(f"ERROR: SharePoint settings incomplete: {', '.join(missing)} not set (see utils/sharepoint.py)")
        sys.exit(1)
    return sharepoint.SharePoint(sharepoint.settings(), session=session)


def check(client):
    """Read-only: sign in, find the site, the library and the folder. Exits 1 on the first failure."""
    config = client.config
    try:
        client.token()
        print("OK      signed in to Microsoft as the app")
        site = client.site()
        print(f"OK      site: {site.get('displayName') or site.get('name')} ({site.get('webUrl')})")
        client.drive()
        print(f"OK      library: {config['library']}")
        folder = client.item(config["folder"]) if config["folder"] else {"webUrl": "(library root)"}
        if folder is None:
            print(f"OK      folder {config['folder']} doesn't exist yet; the first upload creates it")
        else:
            print(f"OK      folder: {folder.get('webUrl')}")
    except sharepoint.SharePointError as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    print("Ready. (Writing is only tested by an upload: a read-only grant passes this check but fails the upload.)")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Export one month of WELL sensor data and upload it to SharePoint.")
    parser.add_argument("--year", type=int, help="Year (e.g. 2026)")
    parser.add_argument("--month", type=int, help="Month (1-12)")
    parser.add_argument("--check", action="store_true", help="Check the settings and access only; upload nothing")
    args = parser.parse_args(argv)
    if bool(args.year) != bool(args.month):
        parser.error("give both --year and --month, or neither (last month)")

    client = configured_client()
    if args.check:
        check(client)
        return

    from server import create_app
    from upload_data import exported_month
    with create_app().app_context():
        csv_name, csv_content, year = exported_month(args)
    try:
        outcome, web_url = sharepoint.upload_month_file(client, csv_name, csv_content, year)
    except sharepoint.SharePointError as e:
        print(f"ERROR: Uploading {csv_name} to SharePoint: {e}")
        sys.exit(1)
    print(f"Successfully uploaded {csv_name} to SharePoint ({outcome}): {web_url}")


if __name__ == "__main__":
    main()
