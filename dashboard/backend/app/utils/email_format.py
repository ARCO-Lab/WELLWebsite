"""The shared look of the WELL emails (the alerts, utils/alerts.py, and the daily digest, utils/digest.py). Pure: no
database, network or SMTP, so it is unit-tested.

Every email is written once, as plain Markdown: `## ` headings, `- ` bullets (an item's extra lines indented two
spaces, a nested bullet four), `**bold**` names, a `---` rule above the footer, and bare URLs. That text is the
plain-text part, and markdown_to_html() renders the same text as the HTML part, so both carry the same content. The
HTML is deliberately simple (inline styles, no images, colours or external assets), so it reads the same in Outlook,
webmail and on a phone.
"""
import html
import re
from datetime import datetime, timezone

from utils.parsers import LOGGER_CONFIG
from utils.timezone import EST_TZ

# The README section on what each email means, linked from every email's footer as "Why did I get this?".
HELP_URL = "https://github.com/ARCO-Lab/WELLWebsite/blob/main/dashboard/backend/README.md#why-did-i-get-this-email"

LOGGER_NUMBERS = {str(c["station_id"]): c["logger_num"] for c in LOGGER_CONFIG.values()}
STATION_NAMES = {"WQData": "Water quality station", "LI-COR": "Weather station"}
# Plain words for the measurement names that aren't plain already.
MEASUREMENT_NAMES = {"Water Surface Elevation": "water level", "ODO": "dissolved oxygen",
                     "ODOSat": "oxygen saturation", "TDS": "TDS", "TSS": "TSS", "RH": "relative humidity"}


def aware(ts):
    """A database time as an aware datetime: PostgreSQL's timestamptz already is; SQLite (tests) returns naive UTC.
    An ISO string (as /health/data and the digest's alert lists carry) is parsed first."""
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts)
    if ts is None or ts.tzinfo:
        return ts
    return ts.replace(tzinfo=timezone.utc)


def duration(delta):
    """A rounded, readable length of time: "45 min", "3 h", "2.5 days"."""
    minutes = max(0, int(delta.total_seconds() // 60))
    if minutes < 120:
        return f"{minutes} min"
    if minutes < 48 * 60:
        return f"{round(minutes / 60)} h"
    return f"{minutes / 1440:.1f} days"


def when(ts):
    """A time as the emails show it, in Toronto time: "Wed Nov 11, 12:00". Accepts an ISO string too."""
    t = aware(ts).astimezone(EST_TZ)
    return f"{t:%a %b} {t.day}, {t:%H:%M}"


def since(start, now):
    """ "Since Wed Nov 11, 12:00 (20 h)" for something still going on."""
    return f"Since {when(start)} ({duration(aware(now) - aware(start))})"


def span(start, end):
    """ "Wed Nov 11, 12:00 → Thu Nov 12, 08:03 (20 h)" for something that has ended."""
    return f"{when(start)} → {when(end)} ({duration(aware(end) - aware(start))})"


def measurement_name(measurement):
    if measurement in MEASUREMENT_NAMES:
        return MEASUREMENT_NAMES[measurement]
    return measurement if measurement.isupper() else measurement.lower()   # "Rain" -> "rain"; acronyms stay


def what(key):
    """The station and sensor an alert key is about, in plain words: "vendor:LI-COR" -> "LI-COR API",
    "stale:LI-COR" -> "All LI-COR stations", "suspect:LI-COR:2577531:Water Surface Elevation" -> "Logger 1 water
    level". Keys are built in utils/alerts.py; an unknown shape is shown as it is."""
    parts = key.split(":", 3)
    if parts[0] == "vendor" and len(parts) == 2:
        return f"{parts[1]} API"
    if parts[0] not in ("stale", "suspect") or len(parts) < 2:
        return key
    if len(parts) == 2:
        return f"All {parts[1]} stations"
    vendor, station = parts[1], parts[2]
    if station in LOGGER_NUMBERS:
        name = f"Logger {LOGGER_NUMBERS[station]}"
    else:
        name = f"{STATION_NAMES.get(vendor, f'{vendor} station')} {station}"
    return f"{name} {measurement_name(parts[3])}" if len(parts) == 4 else name


def section(heading, items):
    """Markdown lines of one `## ` section; each item is a list of lines (the first is the bullet)."""
    lines = [f"## {heading}", ""]
    loose = any(len(item) > 1 for item in items)   # a blank line between cards, so they read apart as text
    for n, item in enumerate(items):
        lines += [""] if loose and n else []
        lines.append(f"- {item[0]}")
        lines += [f"  {line}" for line in item[1:]]
    return lines + [""]


def footer(dashboard_url, checked_at=None):
    """The footer every email ends with: the dashboard, the health JSON and what the emails mean."""
    base = dashboard_url.rstrip("/")
    lines = ["---", "", f"Dashboard: {base}/", f"Health JSON: {base}/api/health/data",
             f"Why did I get this? {HELP_URL}"]
    if checked_at is not None:
        lines.append(f"Checked {when(checked_at)} (Toronto time).")
    return lines


URL_RE = re.compile(r"https?://[^\s<>\"]+[^\s<>\".,;:)]")
BOLD_RE = re.compile(r"\*\*(.+?)\*\*")

BODY = "margin:0;padding:0;background:#ffffff"
WRAP = ("max-width:640px;margin:0 auto;padding:16px;font-family:Segoe UI,Arial,Helvetica,sans-serif;"
        "font-size:14px;line-height:1.5;color:#222222")
H2 = "font-size:16px;margin:20px 0 8px 0;padding:0;font-weight:bold"
P = "margin:0 0 12px 0"
UL = "margin:0 0 12px 0;padding:0 0 0 20px"
LI = "margin:0 0 10px 0"
HR = "border:0;border-top:1px solid #dddddd;margin:20px 0 12px 0"
FOOT = "margin:0;color:#666666;font-size:12px"


def inline(text):
    """One line of Markdown as HTML: escaped first, so only our own **bold** and links become tags."""
    out = html.escape(text, quote=True)
    out = BOLD_RE.sub(r"<strong>\1</strong>", out)
    # Escaping turned "&" in URLs into "&amp;", which is what an href needs.
    return URL_RE.sub(lambda m: f'<a href="{m.group(0)}" style="color:#1a4f8b">{m.group(0)}</a>', out)


def markdown_to_html(text, title="WELL"):
    """The HTML part for an email's Markdown (the subset described at the top of this file)."""
    lines = text.rstrip("\n").split("\n")
    out, i, after_rule = [], 0, False

    def item_lines(start, indent):
        # The lines of one bullet: its first line, then everything indented more than the bullet itself.
        block = [lines[start][indent + 2:]]
        j = start + 1
        while j < len(lines) and lines[j].startswith(" " * (indent + 2)) and lines[j].strip():
            block.append(lines[j][indent + 2:])
            j += 1
        return block, j

    def render_list(block_lines):
        # A bullet's extra lines: plain lines become line breaks, "- " lines a nested list.
        parts, nested = [], []
        for line in block_lines:
            if line.startswith("- "):
                nested.append(f'<li style="margin:0">{inline(line[2:])}</li>')
            else:
                if nested:
                    parts.append(f'<ul style="margin:4px 0 0 0;padding:0 0 0 18px">{"".join(nested)}</ul>')
                    nested = []
                parts.append(("<br>" if parts else "") + inline(line.rstrip()))
        if nested:
            parts.append(f'<ul style="margin:4px 0 0 0;padding:0 0 0 18px">{"".join(nested)}</ul>')
        return "".join(parts)

    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
        elif line.startswith("## "):
            out.append(f'<h2 style="{H2}">{inline(line[3:])}</h2>')
            i += 1
        elif line.strip() == "---":
            out.append(f'<hr style="{HR}">')
            after_rule = True
            i += 1
        elif line.startswith("- "):
            items = []
            while i < len(lines) and lines[i].startswith("- "):
                block, i = item_lines(i, 0)
                items.append(f'<li style="{LI}">{render_list(block)}</li>')
                if i + 1 < len(lines) and not lines[i].strip() and lines[i + 1].startswith("- "):
                    i += 1   # a blank line between items (a loose list) doesn't end the list
            out.append(f'<ul style="{UL}">{"".join(items)}</ul>')
        else:
            paragraph = []
            while i < len(lines) and lines[i].strip() and not lines[i].startswith(("## ", "- ", "---")):
                paragraph.append(inline(lines[i].strip()))
                i += 1
            out.append(f'<p style="{FOOT if after_rule else P}">{"<br>".join(paragraph)}</p>')
    return ("<!DOCTYPE html>\n<html><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            f"<title>{html.escape(title)}</title></head>\n"
            f'<body style="{BODY}"><div style="{WRAP}">\n' + "\n".join(out) + "\n</div></body></html>\n")
