"""Checks the API routes share on text taken from a request.

PostgreSQL's driver refuses a string with a NUL character (psycopg2 raises a plain ValueError, which isn't a
database error) and Python can't encode a lone surrogate ("\\ud800", which JSON allows) as UTF-8. Either reached a
query as a 500 and an error report, so such text is refused with a 400 before it gets there. Other control
characters (tabs, newlines) are never part of a station, measurement or series name, so they're refused too.
"""
import re

_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def bad_text(value: str) -> bool:
    """Whether `value` holds a control character or can't be encoded as UTF-8."""
    if _CONTROL.search(value):
        return True
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return True
    return False
