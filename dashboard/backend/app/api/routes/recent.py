# This file defines the /api/recent route: the latest creek sampling results, for the dashboard's sampling cards.
# For each measurement type it takes that type's latest sampling day (the date of its newest recorded_at) and
# returns the newest row of each site on that day. Sites are sampled one after another on a visit (site 1 at 09:40,
# site 9 at 12:05), so matching only the single newest timestamp would keep just the last site. recorded_at is
# naive America/Toronto wall time, so its date is the sampling day.

from flask import jsonify
from db.database import db
from db.models import SamplingMeasurement


def latest_per_site(rows):
    """The newest row per (measurement type, site) among `rows`, in the order sampling rows are listed elsewhere:
    time, then site number (shorter ids first, so "2" before "10"), then parameter, text compared byte for byte."""
    newest = {}
    for r in rows:
        key = (r.measurement_type, r.site_id)
        if key not in newest or r.recorded_at > newest[key].recorded_at:
            newest[key] = r
    return sorted(newest.values(), key=lambda r: (r.recorded_at, len(r.site_id), r.site_id.encode(),
                                                  r.measurement_type.encode()))


def register_recent_route(app):
    @app.route("/api/recent", methods=["GET"])
    def get_recent_sampling_metrics():
        # The newest timestamp per measurement type
        subquery = db.session.query(
            SamplingMeasurement.measurement_type,
            db.func.max(SamplingMeasurement.recorded_at).label("max_time")
        ).group_by(SamplingMeasurement.measurement_type).subquery()

        # Every row of that type from the start of that timestamp's day on, i.e. the latest visit's rows (a few per
        # site at most). date() is the same function on PostgreSQL and SQLite.
        query = db.session.query(SamplingMeasurement).join(
            subquery,
            db.and_(
                SamplingMeasurement.measurement_type == subquery.c.measurement_type,
                SamplingMeasurement.recorded_at >= db.func.date(subquery.c.max_time)
            )
        )

        # Format query results as a list of dicts
        results = [
            {
                "site_id": r.site_id,
                "creek_id": r.creek_id,
                "measurement_type": r.measurement_type,
                "value": r.value,
                "unit": r.unit,
                "recorded_at": r.recorded_at.isoformat()
            }
            for r in latest_per_site(query.all())
        ]

        return jsonify(results)
