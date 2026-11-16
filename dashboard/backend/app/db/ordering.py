# The order sampling rows are listed and exported in, so readings that share a time always come out the same way.
#
# Several readings share a recorded_at (one site's parameters, or sites sampled together), and ordering by time
# alone leaves their order to the database. Ties are broken by site, then parameter, which together with the time
# is the table's unique key, so the order is total. Sites are numbered ("1".."10", stored as text), so shorter ids
# come first and "2" sorts before "10". Text is compared byte for byte (COLLATE "C" on PostgreSQL, SQLite's default
# BINARY), so the order doesn't depend on the database's locale and is the same on SQLite in the tests.

from sqlalchemy import func

from db.models import SamplingMeasurement


def bytewise(column, dialect_name):
    """`column` compared byte for byte on this database."""
    return column.collate("C") if dialect_name == "postgresql" else column


def sampling_order(dialect_name):
    """ORDER BY terms for sampling_measurements: time, then site number, then parameter."""
    m = SamplingMeasurement
    return (m.recorded_at, func.length(m.site_id), bytewise(m.site_id, dialect_name),
            bytewise(m.measurement_type, dialect_name))


def sampling_sort_key(row):
    """sampling_order()'s order in Python, for rows already loaded (e.g. picked from a larger query): a sort key for
    objects with recorded_at, site_id and measurement_type. Comparing UTF-8 bytes matches COLLATE "C"."""
    return (row.recorded_at, len(row.site_id), row.site_id.encode(), row.measurement_type.encode())
