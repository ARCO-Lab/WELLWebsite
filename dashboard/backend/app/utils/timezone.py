from datetime import datetime
from zoneinfo import ZoneInfo

EST_TZ = ZoneInfo("America/Toronto")


def est_now() -> datetime:
    # Store as naive datetime in local EST/EDT wall time to match existing DB column types.
    return datetime.now(EST_TZ).replace(tzinfo=None)
