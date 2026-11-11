# Checks a sampling file against the standard format (docs/sampling-csv-format.md) without touching the database.
#   python scripts/check_sampling_csv.py <file> [<file> ...]
# Prints every problem with its row number, or a summary of what an import would store. Exit code 0 when every
# file is valid, 1 otherwise. Needs no DATABASE_URL or other settings.

import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))
from utils.sampling_csv import validate_file  # noqa: E402


def check(path):
    try:
        result = validate_file(path)
    except OSError as e:
        print(f"{path}: cannot read the file ({e.strerror})")
        return False
    for note in result.notes:
        print(f"{path}: note: {note}")
    if result.ok:
        print(f"{path}: OK, {result.summary()}")
        return True
    for issue in result.errors:
        print(f"{path}: {issue}")
    print(f"{path}: {len(result.errors)} problems; an import would store nothing from this file")
    return False


def main(argv):
    if not argv:
        print("Usage: python scripts/check_sampling_csv.py <file> [<file> ...]")
        return 2
    results = [check(path) for path in argv]   # every file, even after a bad one
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
