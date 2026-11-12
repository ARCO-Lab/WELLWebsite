"""The worker's file logs (logs/*.log, written by scripts/scheduler_temp.py): timestamped lines, rotated by size,
and never an error for the job that logs them.

Each file is kept to about MAX_BYTES: when it is full it is renamed to <name>.1 (the older copies move to .2 and
.3, and the oldest is deleted), so each log uses at most (BACKUP_COUNT + 1) * MAX_BYTES of disk. A file that is
already over the limit when the worker starts is rotated on the first line written to it.

A line that can't be written (disk full, permissions, a missing folder) is dropped: a job must go on and do its work,
and reach its heartbeat ping, even when its log can't be written. The first such failure per file is reported once
on stderr (docker compose logs worker), so it doesn't go unnoticed.
"""
import builtins
import logging
import logging.handlers
import sys
import threading
import time

MAX_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 3

_original_print = builtins.print   # the real print, captured before scheduler_temp.py replaces builtins.print


class _QuietRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """A RotatingFileHandler that drops a line it can't write instead of printing a traceback for each one."""

    def __init__(self, path, max_bytes, backup_count):
        # delay: the file is opened on the first line, so an unwritable folder doesn't fail at startup
        super().__init__(path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8", delay=True)
        self.failed = False

    def handleError(self, record):
        if not self.failed:
            self.failed = True
            error = sys.exc_info()[1]
            try:
                sys.stderr.write(f"[worklog] can't write {self.baseFilename} ({type(error).__name__}: {error}); "
                                 f"dropping its lines until it works again\n")
            except Exception:
                pass
        # Closed, so the next line opens the file again (it may work once the disk has room)
        try:
            self.close()
        except Exception:
            pass

    def emit(self, record):
        super().emit(record)
        if self.stream is not None:
            self.failed = False   # written again: report the next failure too


_handlers = {}
_handlers_lock = threading.Lock()


def _handler(path, max_bytes, backup_count):
    with _handlers_lock:
        handler = _handlers.get(path)
        if handler is None:
            handler = _QuietRotatingFileHandler(path, max_bytes, backup_count)
            handler.setFormatter(logging.Formatter("%(message)s"))
            _handlers[path] = handler
        return handler


def file_logger(path, mirror_stdout=False, max_bytes=MAX_BYTES, backup_count=BACKUP_COUNT):
    """A print-like function that appends "[YYYY-mm-dd HH:MM:SS] <args joined by sep>" to `path`, rotating it by
    size, and also prints the line when `mirror_stdout` is set. It never raises. Called with file=<stream>, it is
    plain print to that stream, so it can stand in for builtins.print."""
    handler = _handler(path, max_bytes, backup_count)

    def log(*args, sep=" ", end="\n", file=None, flush=False):
        if file is not None:
            _original_print(*args, sep=sep, end=end, file=file, flush=flush)
            return
        line = time.strftime("[%Y-%m-%d %H:%M:%S]") + " " + (sep if sep is not None else " ").join(map(str, args))
        try:
            handler.handle(logging.LogRecord(path, logging.INFO, path, 0, line, None, None))
        except Exception:   # handle() reports through handleError; this is only a last guard
            pass
        if mirror_stdout:
            try:
                _original_print(line, flush=True)
            except Exception:
                pass

    return log
