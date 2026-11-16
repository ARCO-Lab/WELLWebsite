# This script uploads WELL data as CSV files to a SharePoint document library through Microsoft Graph, as a second
# off-VM copy: one day, ISO week or month of sensor data (the layout of the file scripts/upload_data.py sends to
# Borealis, built by the same code), or the creek sampling readings of each month (the standard sampling format,
# docs/sampling-csv-format.md). Where they go depends on SHAREPOINT_LAYOUT (utils/sharepoint.py lists the settings):
#   unset (year layout)   sensor months only, in <SHAREPOINT_FOLDER>/<year>/WELLWestCampus_<Mon><YYYY>.csv
#   cadence               in <SHAREPOINT_FOLDER> (default the library root):
#                           West Campus/Daily/<year>/<MM>/WELLWestCampus_2026-11-14.csv
#                           West Campus/Weekly/<ISO year>/WELLWestCampus_2026-W46.csv
#                           West Campus/Monthly/<year>/WELLWestCampus_Oct2026.csv
#                           Ancaster Watershed/<year>/WELLAncasterWatershed_Oct2026.csv
#
#   python scripts/sharepoint_upload.py --year 2026 --month 10    that month of sensor data
#   python scripts/sharepoint_upload.py --week 2026-W46           that ISO week, Monday to Monday (cadence layout)
#   python scripts/sharepoint_upload.py --day 2026-11-14          that day (cadence layout)
#   python scripts/sharepoint_upload.py                           last month
#   python scripts/sharepoint_upload.py --sampling all            every month with sampling readings (cadence layout)
#   python scripts/sharepoint_upload.py --sampling 2026-10        that month's sampling readings (cadence layout)
#   python scripts/sharepoint_upload.py --check                   sign in and find the site, library and folders;
#                                                                 uploads nothing
# Running it again is safe: an identical file isn't sent again, and a changed one replaces the old copy (SharePoint
# keeps it in the file's version history), so `--sampling all` every night sends only the months whose readings were
# added or corrected. It prints "Successfully uploaded <file> to SharePoint" only when the file is there, and exits 2
# when there are no readings; the scheduler records a sensor period as done only after that line
# (logs/sharepoint_*.json).

import argparse
import io
import pathlib
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv  # noqa: E402
from utils import periods, sharepoint  # noqa: E402
from utils.jobs import NO_DATA_EXIT  # noqa: E402

load_dotenv()

SITE_TZ = ZoneInfo("America/Toronto")
# --sampling all stops after this many files fail: the cause is then likely a setting or SharePoint itself
SAMPLING_FAILURES = 3


def configured_client(session=None):
    """A SharePoint client from the environment. Exits 1 when the settings are off, incomplete or invalid."""
    state, missing = sharepoint.status()
    if state == "off":
        print("ERROR: SharePoint upload is off: set SHAREPOINT_TENANT_ID, SHAREPOINT_CLIENT_ID, "
              "SHAREPOINT_CLIENT_SECRET and SHAREPOINT_SITE (see utils/sharepoint.py)")
        sys.exit(1)
    if state == "incomplete":
        print(f"ERROR: SharePoint settings incomplete: {', '.join(missing)} not set (see utils/sharepoint.py)")
        sys.exit(1)
    config = sharepoint.settings()
    try:
        sharepoint.cadences(config)
    except ValueError as e:
        print(f"ERROR: {e} (see utils/sharepoint.py)")
        sys.exit(1)
    return sharepoint.SharePoint(config, session=session)


def check(client):
    """Read-only: sign in, find the site, the library and the folder(s). Exits 1 on the first failure."""
    config = client.config
    try:
        client.token()
        print("OK      signed in to Microsoft as the app")
        site = client.site()
        print(f"OK      site: {site.get('displayName') or site.get('name')} ({site.get('webUrl')})")
        client.drive()
        print(f"OK      library: {config['library']}")
        folders = [config["folder"]] if config["folder"] else []
        if config["layout"] == "cadence":
            uploads = sharepoint.cadences(config)
            print(f"OK      layout: cadence; uploading {', '.join(uploads)}")
            sensor = f"{config['folder']}/{config['sensor_folder']}".strip("/")
            folders += [sensor] + [f"{sensor}/{name}" for cadence, name in sharepoint.CADENCE_FOLDERS.items()
                                   if cadence in uploads]
            if "sampling" in uploads:
                folders.append(f"{config['folder']}/{config['sampling_folder']}".strip("/"))
        if not config["folder"]:
            print("OK      folder: (library root)")
        for path in folders:
            folder = client.item(path)
            if folder is None:
                print(f"OK      folder {path} doesn't exist yet; the first upload creates it")
            else:
                print(f"OK      folder: {folder.get('webUrl')}")
    except sharepoint.SharePointError as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    print("Ready. (Writing is only tested by an upload: a read-only grant passes this check but fails the upload.)")


def chosen_period(args, now=None):
    """The sensor period the arguments name; last month when they name none."""
    if args.day:
        return periods.parse("daily", args.day)
    if args.week:
        return periods.parse("weekly", args.week)
    if args.year:
        return periods.parse("monthly", f"{args.year:04d}-{args.month:02d}")
    # recorded_at is Toronto wall-clock time, so "last month" is measured there, not on the container's UTC clock
    this_month = periods.containing("monthly", (now or datetime.now(SITE_TZ)).date())
    return periods.containing("monthly", this_month.start.date() - timedelta(days=1))


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Export one day, week or month of WELL sensor data, or the monthly "
                                                 "sampling files, and upload them to SharePoint.")
    parser.add_argument("--year", type=int, help="Year (e.g. 2026), with --month")
    parser.add_argument("--month", type=int, help="Month (1-12), with --year")
    parser.add_argument("--week", help="An ISO week, e.g. 2026-W46 (Monday to Monday; cadence layout)")
    parser.add_argument("--day", help="A day, e.g. 2026-11-14 (cadence layout)")
    parser.add_argument("--sampling", help="'all' (every month with sampling readings) or a month, e.g. 2026-10 "
                                           "(cadence layout)")
    parser.add_argument("--check", action="store_true", help="Check the settings and access only; upload nothing")
    args = parser.parse_args(argv)
    if bool(args.year) != bool(args.month):
        parser.error("give both --year and --month, or neither (last month)")
    if sum(map(bool, (args.year, args.week, args.day, args.sampling))) > 1:
        parser.error("give one of --year/--month, --week, --day and --sampling")
    try:
        if args.sampling and args.sampling != "all":
            periods.parse("monthly", args.sampling)
        args.period = None if args.check or args.sampling else chosen_period(args)
    except ValueError as e:
        parser.error(str(e))
    return args


def sampling_file_name(month):
    """WELLAncasterWatershed_Oct2026.csv for the month (a monthly Period) October 2026."""
    return f"WELLAncasterWatershed_{periods.MONTHS[month.start.month - 1]}{month.start.year}.csv"


def sampling_months(which):
    """The months (monthly Periods, oldest first) `which` names: every month with sampling readings for "all", else
    that month ("YYYY-MM"). Needs the app context (the database)."""
    if which != "all":
        return [periods.parse("monthly", which)]
    from db.database import db
    from db.models import SamplingMeasurement
    stamps = db.session.query(SamplingMeasurement.recorded_at).distinct()
    keys = sorted({periods.containing("monthly", stamp.date()).key for (stamp,) in stamps})
    return [periods.parse("monthly", key) for key in keys]


def export_sampling_csv(start, end):
    """The sampling readings from `start` up to, not including, `end` as a standard sampling CSV
    (utils/sampling_csv.write_standard_csv), or None if there are none. Needs the app context."""
    from db.database import db
    from db.models import SamplingMeasurement
    from db.ordering import sampling_order
    from utils.sampling_csv import write_standard_csv
    m = SamplingMeasurement
    query = db.session.query(m.site_id, m.measurement_type, m.value, m.unit, m.recorded_at).filter(
        m.recorded_at >= start, m.recorded_at < end).order_by(*sampling_order(db.engine.dialect.name))
    buffer = io.StringIO()
    if not write_standard_csv((row._asdict() for row in query), buffer):
        return None
    return buffer.getvalue()


def upload_sampling(client, which):
    """Upload the sampling file of each month `which` names (sampling_months). Exits NO_DATA_EXIT when there are no
    readings, and 1 if a file failed (the others still go up, up to SAMPLING_FAILURES failures)."""
    if client.config["layout"] != "cadence":
        print("ERROR: sampling files need SHAREPOINT_LAYOUT=cadence (see utils/sharepoint.py)")
        sys.exit(1)
    from server import create_app
    with create_app().app_context():
        files = [(month, export_sampling_csv(month.start, month.end)) for month in sampling_months(which)]
    files = [(month, content) for month, content in files if content]
    if not files:
        print(f"ERROR: No sampling readings found ({which}); nothing uploaded.")
        sys.exit(NO_DATA_EXIT)
    failed = 0
    for month, content in files:
        name = sampling_file_name(month)
        try:
            outcome, web_url = sharepoint.put_file(client, sharepoint.sampling_folder(client.config, month.start.year),
                                                   name, content)
        except sharepoint.SharePointError as e:
            print(f"ERROR: Uploading {name} to SharePoint: {e}")
            failed += 1
            if failed >= SAMPLING_FAILURES:
                break
            continue
        print(f"Successfully uploaded {name} to SharePoint ({outcome}): {web_url}")
    if failed:
        print(f"ERROR: {failed} sampling file(s) didn't go up to SharePoint")
        sys.exit(1)


def main(argv=None):
    args = parse_args(argv)
    client = configured_client()
    if args.check:
        check(client)
        return
    if args.sampling:
        upload_sampling(client, args.sampling)
        return
    period = args.period
    try:
        folder = sharepoint.period_folder(client.config, period)
    except ValueError as e:
        print(f"ERROR: {e} (see utils/sharepoint.py)")
        sys.exit(1)

    from server import create_app
    from upload_data import exported_range
    with create_app().app_context():
        csv_name, csv_content = exported_range(period.start, period.end, periods.file_name(period))
    try:
        outcome, web_url = sharepoint.put_file(client, folder, csv_name, csv_content)
    except sharepoint.SharePointError as e:
        print(f"ERROR: Uploading {csv_name} to SharePoint: {e}")
        sys.exit(1)
    print(f"Successfully uploaded {csv_name} to SharePoint ({outcome}): {web_url}")


if __name__ == "__main__":
    main()
