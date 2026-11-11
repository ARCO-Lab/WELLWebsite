# Preflight for the Borealis jobs: checks the settings, the API token, the two collections and the two datasets,
# and prints exactly what is still missing before the monthly sensor upload (scripts/upload_data.py) and the weekly
# sampling download (scripts/download_data.py) can work. Read-only: it only sends GET requests and changes nothing.
#   docker compose exec worker python scripts/borealis_check.py --check
# Exits 0 when nothing is missing, 1 otherwise. Never prints the token.
# Settings: utils/borealis.py lists them (BOREALIS_URL, BOREALIS_API_TOKEN, BOREALIS_UPLOAD_PERSISTENT_ID,
# BOREALIS_SAMPLING_PERSISTENT_ID, BOREALIS_UPLOAD_DATAVERSE, BOREALIS_SAMPLING_DATAVERSE).

import argparse
import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from config import Config  # noqa: E402
from utils.borealis import Dataverse, DataverseError, base_url, collection_alias, is_demo  # noqa: E402

# The sampling dataset should hold the template and a README for whoever uploads. The import ignores the template
# under this name (download_data.py skips WELLAncasterWatershed_SAMPLE.*) and any file without the prefix.
TEMPLATE_NAME = "WELLAncasterWatershed_SAMPLE.csv"
SAMPLING_PREFIX = "wellancasterwatershed_"


class Report:
    """Collects OK / WARN / MISSING lines; `missing` is the to-do list printed at the end."""

    def __init__(self, out=print):
        self.out, self.missing, self.warnings = out, [], []

    def ok(self, text):
        self.out(f"OK      {text}")

    def warn(self, text):
        self.warnings.append(text)
        self.out(f"WARN    {text}")

    def need(self, text):
        self.missing.append(text)
        self.out(f"MISSING {text}")

    def info(self, text):
        self.out(f"        {text}")


def check_settings(report, settings):
    """The server URL, or None when it can't be used. Reports each missing setting."""
    url = settings.get("url")
    server = None
    if not url:
        report.need("BOREALIS_URL is not set: set it to https://borealisdata.ca")
    else:
        try:
            server = base_url(url)
            report.ok(f"BOREALIS_URL: {server}")
        except ValueError as e:
            report.need(str(e))
        if server and is_demo(server):
            report.need(f"BOREALIS_URL is the demo server ({server}), which is reset from time to time: set it to "
                        f"https://borealisdata.ca")
    if not settings.get("token"):
        report.need("BOREALIS_API_TOKEN is not set: create a token on Borealis (your name > API Token) and set it")
    for name, key in (("BOREALIS_UPLOAD_PERSISTENT_ID", "upload_pid"), ("BOREALIS_SAMPLING_PERSISTENT_ID", "sampling_pid")):
        pid = settings.get(key)
        if not pid:
            report.need(f"{name} is not set: the dataset's persistent id, e.g. doi:10.5683/SP3/ABCDEF (dataset page > "
                        f"Metadata > Persistent Identifier)")
        elif is_demo(persistent_id=pid):
            report.need(f"{name} is {pid}, a dataset on the demo server: create the dataset on borealisdata.ca "
                        f"and set its id")
    for name, key in (("BOREALIS_UPLOAD_DATAVERSE", "upload_alias"), ("BOREALIS_SAMPLING_DATAVERSE", "sampling_alias")):
        if not settings.get(key):
            report.warn(f"{name} is not set, so its collection isn't checked (the alias at the end of the "
                        f"collection's URL, e.g. https://borealisdata.ca/dataverse/<alias>)")
    return server


def check_token(report, client):
    """True if the token is accepted."""
    if not client.token:
        return False
    try:
        me = client.me()
    except DataverseError as e:
        if e.status == 401:
            report.need("BOREALIS_API_TOKEN is rejected (wrong or expired): create a new token on Borealis "
                        "(your name > API Token > Create/Recreate Token) and set it")
        else:
            report.need(f"the token couldn't be checked: {e}")
        return False
    report.ok(f"the API token is valid, for account {me.get('identifier') or me.get('id')}")
    try:
        expiry = client.token_expiry()
        if expiry:
            report.info(expiry)
    except DataverseError:
        pass   # the expiry date is only informative; the token itself was just accepted
    return True


def check_collection(report, client, alias, role, with_token):
    """Report whether the collection exists, is published, and what the token's account may do in it."""
    try:
        collection = client.collection(alias)
    except DataverseError as e:
        report.need(f"{role} collection {alias}: {e}")
        return
    name = collection.get("name") or alias
    if collection.get("isReleased"):
        report.ok(f"{role} collection {alias} ({name}) is published")
    else:
        report.need(f"publish the {role} collection {alias} ({name}): open it on Borealis > Publish. Its datasets "
                    f"can't be published before it is")
    if not with_token:
        return
    try:
        perms = client.collection_permissions(alias)
    except DataverseError as e:
        report.warn(f"couldn't read your permissions on {alias}: {e}")
        return
    granted = sorted(k for k, v in perms.items() if v)
    report.info(f"your permissions on {alias}: {', '.join(granted) or 'none'}")
    if not perms.get("canAddDataset"):
        report.warn(f"your account can't create datasets in {alias} (needed only to create them; the Curator or "
                    f"Admin role on the collection gives it)")


def dataset_summary(client, pid):
    """(latest version, published version or None) of the dataset; raises DataverseError."""
    latest = client.dataset(pid).get("latestVersion") or {}
    published = latest if latest.get("versionState") == "RELEASED" else client.published_version(pid)
    return latest, published


def check_dataset_common(report, client, pid, role):
    """The (latest, published) versions, or None if the dataset can't be read."""
    try:
        latest, published = dataset_summary(client, pid)
    except DataverseError as e:
        report.need(f"{role} dataset {pid}: {e}")
        return None
    title = latest.get("datasetTitle") or title_of(latest) or pid
    report.ok(f"{role} dataset {pid} ({title}) is readable; latest version: {latest.get('versionState')}")
    if published:
        report.ok(f"{role} dataset has a published version "
                  f"{published.get('versionNumber')}.{published.get('versionMinorNumber')} "
                  f"with {len(published.get('files') or [])} files")
    license_name = ((latest.get("license") or {}).get("name") or latest.get("termsOfUse"))
    if license_name:
        report.ok(f"{role} dataset licence: {license_name}")
    else:
        report.warn(f"{role} dataset has no licence: choose one (CC BY 4.0 suggested) under Terms before publishing")
    try:
        locks = client.locks(pid)
        if locks:
            report.warn(f"{role} dataset is locked ({', '.join(str(lock.get('lockType')) for lock in locks)}); "
                        f"changes wait until it is unlocked")
    except DataverseError:
        pass   # locks are only a warning; a dataset that can't be read was already reported above
    return latest, published


def title_of(version):
    """The title from a version's citation metadata, if there."""
    fields = (((version.get("metadataBlocks") or {}).get("citation") or {}).get("fields")) or []
    for field in fields:
        if field.get("typeName") == "title":
            return field.get("value")
    return None


def check_permissions(report, client, pid, role, needed):
    """Report the token's permissions on the dataset; each of `needed` (name -> why) that is false is missing."""
    try:
        perms = client.dataset_permissions(pid)
    except DataverseError as e:
        report.need(f"couldn't read your permissions on the {role} dataset: {e}")
        return
    for permission, why in needed.items():
        if perms.get(permission):
            report.ok(f"{role} dataset: {permission}")
        else:
            report.need(f"{role} dataset: your account lacks {permission} ({why}). Ask a collection admin for the "
                        f"Curator role on the dataset or its collection")


def check_upload_dataset(report, client, pid, with_token):
    versions = check_dataset_common(report, client, pid, "upload")
    if versions is None:
        return
    latest, published = versions
    if not published:
        report.warn("the upload dataset has never been published: the first monthly upload publishes version 1.0, "
                    "which needs its collection published first")
    if latest.get("versionState") == "DRAFT" and published:
        report.warn("the upload dataset has an unpublished draft: the next monthly upload publishes it with its file")
    if with_token:
        check_permissions(report, client, pid, "upload", {
            "canEditDataset": "to add each month's file",
            "canPublishDataset": "to publish each month's version",
        })


def check_sampling_dataset(report, client, pid):
    versions = check_dataset_common(report, client, pid, "sampling")
    if versions is None:
        return
    latest, published = versions
    if not published:
        report.need("publish the sampling dataset (Borealis: the dataset > Publish Dataset): the weekly download "
                    "imports only files of its published version")
        return
    names = [(f.get("dataFile") or {}).get("filename") or f.get("label") or "" for f in published.get("files") or []]
    data_files = [n for n in names if n.lower().startswith(SAMPLING_PREFIX) and not n.lower().startswith(
        "wellancasterwatershed_sample.")]
    report.info(f"published sampling files the download would consider: {len(data_files)}")
    if not any(n.lower().startswith("wellancasterwatershed_sample.") for n in names):
        report.warn(f"the sampling dataset has no template: add dashboard/backend/app/sampling_template.csv as "
                    f"{TEMPLATE_NAME} (the import ignores that name)")
    if not any(n.lower().startswith("readme") for n in names):
        report.warn("the sampling dataset has no README: add one saying how to name and format files "
                    "(docs/sampling-csv-format.md)")
    if latest.get("versionState") == "DRAFT":
        report.warn("the sampling dataset has an unpublished draft: its new files are imported once it is published")


def settings_from_config():
    return {
        "url": Config.BOREALIS_URL,
        "token": Config.BOREALIS_API_TOKEN,
        "upload_pid": Config.BOREALIS_UPLOAD_PERSISTENT_ID,
        "sampling_pid": Config.BOREALIS_SAMPLING_PERSISTENT_ID,
        "upload_alias": Config.BOREALIS_UPLOAD_DATAVERSE,
        "sampling_alias": Config.BOREALIS_SAMPLING_DATAVERSE,
    }


def run_checks(settings, client=None, out=print):
    """Run every check and print the result. Returns the list of what is missing (empty when ready)."""
    report = Report(out)
    out("Borealis preflight (read-only)")
    server = check_settings(report, settings)
    if server:
        client = client or Dataverse(server, settings.get("token"))
        try:
            report.ok(f"{server} answers: Dataverse {client.version()}")
        except DataverseError as e:
            report.need(f"{server} doesn't answer: {e}")
            client = None
    else:
        client = None

    if client:
        with_token = check_token(report, client)
        if not with_token and client.token:
            client = Dataverse(server, None, session=client.session, sleep=client.sleep)   # what a guest sees
        parent = collection_alias(settings.get("url"))
        for alias, role in ((parent, "parent"), (settings.get("upload_alias"), "upload"),
                            (settings.get("sampling_alias"), "sampling")):
            if alias:
                check_collection(report, client, alias, role, with_token)
        if settings.get("upload_pid") and not is_demo(persistent_id=settings["upload_pid"]):
            check_upload_dataset(report, client, settings["upload_pid"], with_token)
        if settings.get("sampling_pid") and not is_demo(persistent_id=settings["sampling_pid"]):
            check_sampling_dataset(report, client, settings["sampling_pid"])

    out("")
    if report.missing:
        out(f"Not ready: {len(report.missing)} thing(s) missing, in order:")
        for i, item in enumerate(report.missing, 1):
            out(f"  {i}. {item}")
    else:
        out("Ready: the monthly upload and the weekly sampling download have what they need.")
    if report.warnings:
        out(f"{len(report.warnings)} warning(s) above are worth a look but don't block the jobs.")
    return report.missing


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check (read-only) that Borealis is ready for the upload and "
                                                 "download jobs, and print what is missing.")
    parser.add_argument("--check", action="store_true", help="run the checks (the default)")
    parser.parse_args(argv)
    missing = run_checks(settings_from_config())
    sys.exit(1 if missing else 0)


if __name__ == "__main__":
    main()
