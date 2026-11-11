"""The standard sampling file format, and its validator. Pure: no database, no network.

The format is documented in docs/sampling-csv-format.md (the template is app/sampling_template.csv): a UTF-8 CSV with
one reading per row ("long" layout), with the columns date, site, parameter, value and unit, and optionally time,
creek, below_detection, qc_flag, sampler, method and notes.

validate_csv() parses a file and returns every problem at once, each with the file's row number, so a researcher can
fix the whole file in one go. Nothing is imported from a file with any error: callers check `result.ok` first. It
never guesses: an unlisted site, a date like 01/02/2026 or a unit that doesn't match the parameter is an error, not a
best effort. validate_wide_excel() reads the older one-row-per-visit Excel sheets into the same records and checks
them the same way, so both layouts end up as identical rows.

The site and parameter lists below are the only place they are defined for imports; the dashboard's own lists are in
dashboard/frontend/src/components/config/filters.tsx and must name the same sites and parameters.

Provisional, to confirm with the lab (each is marked "TO CONFIRM WITH THE LAB" where it is decided below, and listed in
the format page's "To confirm with the lab" section): the site list, the parameter list and units, the below-detection
convention, and the replicate and QC-flag rules.
"""
import csv
import difflib
import io
import math
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("America/Toronto")   # sampling times are local wall-clock times, stored without a zone

# Creek key -> (name, creek id). The ids are the OpenStreetMap way ids the dashboard's map and filters use.
CREEKS = {
    "ancaster": ("Ancaster Creek", "19431905"),
    "tiffany": ("Tiffany Creek", "20962187"),
    "sulphur": ("Sulphur Creek", "3212839"),
    "coldwater": ("Coldwater Creek", "336415129"),
    "spencer": ("Spencer's Creek", "19755185"),
}


@dataclass(frozen=True)
class Site:
    id: str          # stored as text in sampling_measurements.site_id
    name: str
    creek: str       # key of CREEKS


# The sampling sites, numbered and named as in the lab's 2025 field sheet (there is no site 7).
# TO CONFIRM WITH THE LAB: the official names, and whether sites will be added.
SITES = (
    Site("1", "Falkirk Forest", "tiffany"),
    Site("2", "Maple Lane Pk", "ancaster"),
    Site("3", "Jerseyville Rd", "sulphur"),
    Site("4", "Sulphur Springs", "sulphur"),
    Site("5", "Sherman Falls", "ancaster"),
    Site("6", "Tiffany Falls", "tiffany"),
    Site("8", "Osler Dr", "coldwater"),
    Site("9", "McMaster Lot P", "coldwater"),
    Site("10", "Cootes Dr", "spencer"),
)


@dataclass(frozen=True)
class Parameter:
    name: str                  # stored in sampling_measurements.measurement_type; the dashboard shows these names
    unit: str                  # the one unit values must be in (stored with each row)
    unit_aliases: tuple = ()   # other spellings of that same unit
    aliases: tuple = ()        # other spellings of the name
    minimum: float = 0.0       # values below this are rejected as impossible
    maximum: float = math.inf


# The parameters the dashboard shows. TO CONFIRM WITH THE LAB: whether TSS (mg/L) and water temperature (°C), which
# the field sheet records, should be added; whether the units are final; whether E. coli is ever in MPN/100 mL.
PARAMETERS = (
    Parameter("E. coli", "CFU/100 mL", aliases=("E.coli", "E coli", "Escherichia coli")),
    Parameter("Total coliform", "CFU/100 mL", aliases=("Total coliforms",)),
    Parameter("Turbidity", "NTU"),
    Parameter("pH", "pH units", unit_aliases=("pH",), maximum=14),
    Parameter("Conductivity", "µS/cm", aliases=("Specific conductance", "Specific conductivity")),
    Parameter("Chloride", "mg/L"),
    Parameter("Total phosphorus", "µg/L", aliases=("TP",)),
    Parameter("Soluble reactive phosphorus", "µg/L", aliases=("SRP",)),
    Parameter("Total nitrogen", "mg/L", aliases=("TN",)),
    Parameter("Nitrate nitrogen", "mg/L", aliases=("Nitrate-N", "Total nitrate nitrogen")),
    Parameter("Ammonia nitrogen", "mg/L", aliases=("Ammonia-N", "Total ammonia nitrogen")),
)

REQUIRED_COLUMNS = ("date", "site", "parameter", "value", "unit")
OPTIONAL_COLUMNS = ("time", "creek", "below_detection", "qc_flag", "sampler", "method", "notes")

BLANK_VALUES = {"", "na", "n/a"}                  # "not measured": the row is skipped, not an error
# TO CONFIRM WITH THE LAB: the QC flags. "rejected" rows are checked but not imported; flags aren't stored.
QC_FLAGS = {"", "ok", "suspect", "rejected"}
TRUE_WORDS, FALSE_WORDS = {"true", "yes", "y", "1"}, {"false", "no", "n", "0", ""}
# A plain decimal number in ASCII digits: no thousands separators, no "1_000", no other scripts' digits
_NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")

KEY = ("site_id", "measurement_type", "recorded_at")   # the sampling_measurements unique key

# scripts/inject_sampling.py exits with this code when a file is invalid (and stores nothing), so that
# scripts/download_data.py can tell a file to fix from a failure worth retrying.
INVALID_FILE_EXIT = 3


def _fold(text):
    """Case-, width- and space-insensitive form of a name, for matching only."""
    text = " ".join(unicodedata.normalize("NFKC", str(text)).split()).casefold()
    # NFKC and casefold() turn the micro sign into Greek mu; use the micro sign, as the unit names do
    return text.replace("\N{GREEK SMALL LETTER MU}", "\N{MICRO SIGN}")


def _unit_fold(text):
    return _fold(text).replace("\N{MICRO SIGN}", "u").replace(" ", "")


_SITE_LOOKUP = {}
for _s in SITES:
    for _form in (_s.name, _s.id, f"#{_s.id}", f"#{_s.id} {_s.name}", f"Site {_s.id}", f"Site {_s.id} {_s.name}"):
        _SITE_LOOKUP[_fold(_form)] = _s
_CREEK_LOOKUP = {}
for _key, (_name, _) in CREEKS.items():
    for _form in (_name, _name.replace("'s", "s"), _name.replace("'s", "")):
        _CREEK_LOOKUP[_fold(_form)] = _key
_PARAM_LOOKUP = {_fold(n): p for p in PARAMETERS for n in (p.name, *p.aliases)}


def site_names():
    return [f"{s.id} {s.name}" for s in SITES]


@dataclass
class Issue:
    row: int          # the row number a spreadsheet shows (the header is row 1); 0 for the file as a whole
    column: str
    message: str

    def __str__(self):
        where = f"row {self.row}" if self.row else "file"
        return f"{where}, {self.column}: {self.message}" if self.column else f"{where}: {self.message}"


@dataclass
class Result:
    records: list = field(default_factory=list)   # sampling_measurements rows (dicts), only meaningful when ok
    errors: list = field(default_factory=list)    # Issue objects
    blank: int = 0                                 # rows without a value ("not measured"), skipped
    rejected: int = 0                              # rows with qc_flag "rejected", checked but not imported
    below_detection: int = 0                       # stored rows that were below the detection limit
    notes: list = field(default_factory=list)      # informational lines, e.g. columns of a sheet not imported

    @property
    def ok(self):
        return not self.errors

    def summary(self):
        return (f"{len(self.records)} readings ({self.below_detection} below the detection limit), "
                f"{self.blank} blank values skipped, {self.rejected} rows flagged rejected")


def _suggest(text, choices):
    match = difflib.get_close_matches(str(text), choices, n=1, cutoff=0.6)
    return f" Did you mean '{match[0]}'?" if match else ""


def parse_site(text):
    """The Site a name refers to, or raises ValueError. Exact names only (case and spacing aside)."""
    site = _SITE_LOOKUP.get(_fold(text))
    if site is None:
        names = [s.name for s in SITES]
        raise ValueError(f"unknown site '{text}'.{_suggest(text, names)} Allowed: {', '.join(site_names())}")
    return site


def parse_date(text):
    text = str(text).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        try:
            return date.fromisoformat(text)
        except ValueError:
            raise ValueError(f"'{text}' is not a real date")
    if re.fullmatch(r"\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}", text):
        raise ValueError(f"'{text}' is ambiguous (day/month or month/day?); write dates as YYYY-MM-DD")
    raise ValueError(f"'{text}' is not a date in the form YYYY-MM-DD" if text else "date is empty")


def parse_time(text, day):
    """A local wall-clock HH:MM (24-hour) on `day`; empty means the visit's time wasn't recorded (midnight).
    A time in the hour repeated when clocks fall back (e.g. 01:30 on the first Sunday of November) is stored as
    written; which of the two it was isn't recorded."""
    text = str(text).strip()
    if not text:
        return time(0, 0)
    match = re.fullmatch(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", text)
    if not match or int(match[1]) > 23 or int(match[2]) > 59 or int(match[3] or 0) > 59:
        raise ValueError(f"'{text}' is not a 24-hour time HH:MM (e.g. 14:30)")
    when = time(int(match[1]), int(match[2]), int(match[3] or 0))
    # A time skipped when clocks spring forward doesn't exist locally
    local = datetime.combine(day, when, LOCAL_TZ)
    if local.astimezone(timezone.utc).astimezone(LOCAL_TZ).replace(tzinfo=None) != local.replace(tzinfo=None):
        raise ValueError(f"{text} doesn't exist on {day} (clocks went forward); use the time your watch showed")
    return when


def parse_parameter(text):
    param = _PARAM_LOOKUP.get(_fold(text))
    if param is None:
        names = [p.name for p in PARAMETERS]
        raise ValueError(f"unknown parameter '{text}'.{_suggest(text, names)} Allowed: {', '.join(names)}")
    return param


def check_unit(param, text):
    if not str(text).strip():
        raise ValueError(f"unit is empty; {param.name} is in {param.unit}")
    if _unit_fold(text) not in {_unit_fold(u) for u in (param.unit, *param.unit_aliases)}:
        raise ValueError(f"'{text}' doesn't match {param.name}, which must be in {param.unit} (convert the value)")


def parse_flag(text):
    word = _fold(text)
    if word in TRUE_WORDS:
        return True
    if word in FALSE_WORDS:
        return False
    raise ValueError(f"'{text}' is not true or false")


def parse_value(text):
    """(number, below_detection) for a value cell, or None for a blank one. '<0.01' is below a 0.01 limit.

    TO CONFIRM WITH THE LAB: a below-detection value is stored as the detection limit itself (the flag isn't
    stored), and values above an upper limit ('>2420') are rejected.
    """
    raw = str(text).strip()
    if _fold(raw) in BLANK_VALUES:
        return None
    below = raw.startswith("<")
    number = raw[1:].strip() if below else raw
    if number.startswith(">"):
        raise ValueError(f"'{raw}': values above a limit (>) aren't supported; write the number, and the limit in notes")
    if not _NUMBER.fullmatch(number):
        hint = " (no thousands separators)" if "," in number else ""
        raise ValueError(f"'{raw}' is not a number{hint}")
    value = float(number)
    if not math.isfinite(value):   # e.g. 1e999
        raise ValueError(f"'{raw}' is not a number")
    return value, below


def _is_blank(text):
    return _fold(str(text).strip()) in BLANK_VALUES


def _check_record(fields, row, result):
    """One reading (a dict of column -> text) as a sampling_measurements row; problems go to result.errors."""
    errors = []

    def attempt(column, parse, *args):
        try:
            return parse(*args)
        except ValueError as e:
            errors.append(Issue(row, column, str(e)))
            return None

    day = attempt("date", parse_date, fields.get("date", ""))
    when = attempt("time", parse_time, fields.get("time", ""), day) if day else None
    site = attempt("site", parse_site, fields.get("site", ""))
    creek = (fields.get("creek") or "").strip()
    if site and creek:
        if _CREEK_LOOKUP.get(_fold(creek)) != site.creek:
            errors.append(Issue(row, "creek", f"site {site.id} {site.name} is on {CREEKS[site.creek][0]}, "
                                              f"not '{creek}'"))
    param = attempt("parameter", parse_parameter, fields.get("parameter", ""))
    if param and not _is_blank(fields.get("value", "")):   # a blank row stores nothing, so its unit doesn't matter
        attempt("unit", check_unit, param, fields.get("unit", ""))
    parsed = attempt("value", parse_value, fields.get("value", ""))
    flagged = attempt("below_detection", parse_flag, fields.get("below_detection", ""))
    qc = _fold(fields.get("qc_flag", ""))
    if qc not in QC_FLAGS:
        errors.append(Issue(row, "qc_flag", f"'{fields.get('qc_flag')}' is not one of: ok, suspect, rejected "
                                            f"(or empty)"))
    if parsed and param:
        value, below = parsed
        if flagged is False and below and _fold(fields.get("below_detection", "")):
            errors.append(Issue(row, "below_detection", f"says false, but the value '{fields['value']}' is below "
                                                        f"the detection limit"))
        if not (param.minimum <= value <= param.maximum):
            bound = f"between {param.minimum:g} and {param.maximum:g}" if math.isfinite(param.maximum) \
                else f"at least {param.minimum:g}"
            errors.append(Issue(row, "value", f"{value:g} is impossible for {param.name}; it must be {bound}"))
    if parsed is None and flagged:
        errors.append(Issue(row, "value", "is empty, but below_detection is true; write the detection limit"))

    result.errors.extend(errors)
    if errors:
        return None
    if parsed is None:
        result.blank += 1
        return None
    if qc == "rejected":
        result.rejected += 1
        return None
    value, below = parsed
    below = below or bool(flagged)
    result.below_detection += below
    return {
        "site_id": site.id,
        "creek_id": CREEKS[site.creek][1],
        "measurement_type": param.name,
        "value": value,
        "unit": param.unit,
        "recorded_at": datetime.combine(day, when),
    }


def validate_records(records, result=None):
    """Check (row number, fields) pairs, dropping nothing silently. Returns a Result.

    A file with nothing to store is an error too: importing it would do nothing, and a --full-reload would empty
    the table. TO CONFIRM WITH THE LAB: one value per site, parameter, date and time (replicates are averaged
    before upload), so a repeated reading is an error.
    """
    result = result or Result()
    seen = {}
    for row, fields in records:
        record = _check_record(fields, row, result)
        if record is None:
            continue
        key = tuple(record[k] for k in KEY)
        if key in seen:
            result.errors.append(Issue(row, "", f"repeats row {seen[key]} (same site, parameter, date and time). "
                                                f"Report one value per reading: average replicates, or remove the "
                                                f"copy"))
            continue
        seen[key] = row
        result.records.append(record)
    if not result.records and not result.errors:
        result.errors.append(Issue(0, "", f"no readings to import ({result.blank} blank values, {result.rejected} "
                                          f"rows flagged rejected)"))
    return result


def _column_label(index):
    """A spreadsheet column letter (0 -> A, 26 -> AA), for columns that have no header."""
    label = ""
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        label = chr(ord("A") + rest) + label
    return f"column {label}"


def validate_csv(source):
    """Validate a standard sampling CSV, given as a path or as bytes. Returns a Result with every problem found."""
    if isinstance(source, (bytes, bytearray)):
        data = bytes(source)
    else:
        with open(source, "rb") as f:
            data = f.read()
    result = Result()
    try:
        text = data.decode("utf-8-sig")   # -sig: Excel's "CSV UTF-8" starts with a byte-order mark
    except UnicodeDecodeError as e:
        result.errors.append(Issue(0, "", f"not UTF-8 text (byte {e.start}); in Excel use Save As > "
                                          f"'CSV UTF-8 (Comma delimited)'"))
        return result

    # strict: a malformed quote is an error rather than a guess (a runaway quote would swallow the rest of the file)
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
        table = list(reader)
    except csv.Error as e:
        result.errors.append(Issue(0, "", f"can't be read as CSV near line {reader.line_num}: {e}. A double quote "
                                          f"(\") that isn't closed, or text right after a closing quote, is the "
                                          f"usual cause"))
        return result
    if not table or not any(h.strip() for h in table[0]):
        result.errors.append(Issue(0, "", "the file is empty; the first row must be the header"))
        return result
    header, body = table[0], table[1:]
    if len(header) == 1 and (";" in header[0] or "\t" in header[0]):
        result.errors.append(Issue(1, "", "columns must be separated by commas, not semicolons or tabs"))
        return result

    # Excel can leave columns with neither a header nor values (e.g. "date,...,notes,,"): those are ignored. A
    # column with values but no header is an error, as are cells to the right of the last column.
    used = [i for i, h in enumerate(header) if h.strip()]
    for i, h in enumerate(header):
        if not h.strip() and any(i < len(cells) and cells[i].strip() for cells in body):
            result.errors.append(Issue(1, _column_label(i), "has values but no header"))
    columns = {i: _fold(header[i]) for i in used}
    names = list(columns.values())
    known = set(REQUIRED_COLUMNS) | set(OPTIONAL_COLUMNS)
    for i, name in columns.items():
        if name not in known:
            result.errors.append(Issue(1, header[i], f"unknown column.{_suggest(name, sorted(known))} "
                                                     f"Allowed: {', '.join(REQUIRED_COLUMNS + OPTIONAL_COLUMNS)}"))
    for name in sorted({c for c in names if names.count(c) > 1}):
        result.errors.append(Issue(1, name, "column appears more than once"))
    for name in REQUIRED_COLUMNS:
        if name not in names:
            result.errors.append(Issue(1, name, "required column is missing"))
    if result.errors:
        return result

    def rows():
        for number, cells in enumerate(body, start=2):
            if not any(c.strip() for c in cells):
                continue   # blank line
            if any(c.strip() for c in cells[len(header):]):
                result.errors.append(Issue(number, "", f"has values beyond the header's {len(header)} columns (a "
                                                       f"comma inside a value needs double quotes)"))
                continue
            yield number, {name: (cells[i] if i < len(cells) else "") for i, name in columns.items()}

    return validate_records(rows(), result)


# The older one-row-per-visit Excel layout: a column per parameter. Header (folded to letters, digits and µ) ->
# parameter name, or None for columns that are read but not imported. Covers the headers of the sheets uploaded so
# far; any other column is an error, so a new or renamed column is never dropped silently.
def _header_fold(text):
    return re.sub(r"[^0-9a-zµ]", "", _fold(text))


WIDE_PARAMETER_COLUMNS = {_header_fold(h): name for h, name in (
    ("E. coli (CFU/100 mL)", "E. coli"),
    ("Total coliform (CFU/100 mL)", "Total coliform"),
    ("Turbidity (NTU)", "Turbidity"),
    ("pH", "pH"),
    ("Conductivity (µS/cm)", "Conductivity"),
    ("Specific Conductance µS/cm", "Conductivity"),
    ("Chloride (mg/L)", "Chloride"),
    ("Total phosphorus (µg/L)", "Total phosphorus"),
    ("Total phoshporus (µg/L)", "Total phosphorus"),   # spelled so in the 2025 field sheet
    ("Soluble reactive phosphorus (µg/L)", "Soluble reactive phosphorus"),
    ("Total nitrogen (mg/L)", "Total nitrogen"),
    ("Nitrate nitrogen (mg/L)", "Nitrate nitrogen"),
    ("Total nitrate nitrogen (mg/L)", "Nitrate nitrogen"),
    ("Ammonia nitrogen (mg/L)", "Ammonia nitrogen"),
    ("Total ammonia nitrogen (mg/L)", "Ammonia nitrogen"),
)}
WIDE_IGNORED_COLUMNS = {_header_fold(h) for h in (
    "Trip #", "Year", "Latitude", "Longitude", "Weather", "Note", "Notes",
    "TSS (mg/L)", "Temp (C)",   # measured, but the dashboard has no place for them yet
)}


def _cell_text(value):
    """An Excel cell as the text the CSV rules expect (dates as YYYY-MM-DD, numbers as plain digits)."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    if hasattr(value, "to_pydatetime"):
        value = value.to_pydatetime()
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _cell_time(value):
    if hasattr(value, "to_pydatetime"):
        value = value.to_pydatetime()
    return value.strftime("%H:%M") if isinstance(value, datetime) and value.time() != time(0, 0) else ""


def validate_wide_excel(path):
    """Validate an Excel sheet in the older layout (a Date, a Site and an optional Stream column, then one column
    per parameter) by turning each filled cell into a reading and checking it as validate_csv() would."""
    import pandas as pd   # local: the CSV path doesn't need pandas
    result = Result()
    try:
        sheets = pd.read_excel(path, engine="openpyxl", dtype=object, sheet_name=None)
    except Exception as e:
        result.errors.append(Issue(0, "", f"could not read the Excel file: {e}"))
        return result
    # Only one sheet is read, so a workbook with data on several is refused rather than half-imported. Sheets
    # with nothing on them (Excel's default "Sheet2") don't count.
    filled = {name: f for name, f in sheets.items() if len(f.columns) or len(f)}
    if len(filled) != 1:
        result.errors.append(Issue(0, "", f"the workbook has data on {len(filled)} sheets "
                                          f"({', '.join(map(str, filled)) or 'none'}); put the readings on one sheet"))
        return result
    frame = next(iter(filled.values()))

    header, roles = {}, {}
    for position, original in enumerate(frame.columns):
        if str(original).startswith("Unnamed:"):   # pandas' name for a column without a header
            if frame[original].notna().any():
                result.errors.append(Issue(1, _column_label(position), "has values but no header"))
            continue
        folded = _header_fold(original)
        role = "creek" if folded == "stream" else folded
        if folded in header or (role in ("date", "site", "creek") and role in roles):
            other = header.get(folded) or roles[role]
            result.errors.append(Issue(1, str(original), f"means the same as column '{other}'; keep one of them"))
            continue
        header[folded] = original
        if role in ("date", "site", "creek"):
            roles[role] = original
        elif folded not in WIDE_PARAMETER_COLUMNS and folded not in WIDE_IGNORED_COLUMNS:
            result.errors.append(Issue(1, str(original), "unknown column; add it to WIDE_PARAMETER_COLUMNS in "
                                                         "utils/sampling_csv.py, or use the standard CSV format"))
    for needed in ("date", "site"):
        if needed not in roles:
            result.errors.append(Issue(1, needed.title(), "required column is missing"))
    if result.errors:
        return result
    skipped = [str(header[f]) for f in header if f in WIDE_IGNORED_COLUMNS]
    if skipped:
        result.notes.append(f"columns not imported (not shown by the dashboard): {', '.join(skipped)}")

    param_columns = [(original, WIDE_PARAMETER_COLUMNS[folded]) for folded, original in header.items()
                     if folded in WIDE_PARAMETER_COLUMNS]
    unit_of = {p.name: p.unit for p in PARAMETERS}

    def readings():
        for index, row in frame.iterrows():
            number = index + 2
            base = {"date": _cell_text(row[roles["date"]]), "time": _cell_time(row[roles["date"]]),
                    "site": _cell_text(row[roles["site"]]),
                    "creek": _cell_text(row[roles["creek"]]) if "creek" in roles else ""}
            values = [(column, name, _cell_text(row[column])) for column, name in param_columns]
            if not any(v.strip() for _, _, v in values):
                continue   # a row without any reading
            for column, name, value in values:
                if value.strip():
                    yield number, {**base, "parameter": name, "unit": unit_of[name], "value": value}

    return validate_records(readings(), result)


def is_excel(path):
    """True for .xlsx files (zip archives), whatever their name; download_data.py names every download .xlsx."""
    with open(path, "rb") as f:
        return f.read(4) == b"PK\x03\x04"


def validate_file(path):
    """validate_wide_excel() for an Excel file, validate_csv() for anything else."""
    return validate_wide_excel(path) if is_excel(path) else validate_csv(path)
