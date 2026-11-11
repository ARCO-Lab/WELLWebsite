"""Stands in for the LI-COR (HOBOlink) and WQData APIs in the end-to-end test, answering from fixtures/*.json.

    python vendor_stub.py [port]      (default 8900)

  GET /licor/data?loggers=..&start_date_time=..&end_date_time=..    (Authorization: Bearer <key>)
      LI-COR's reply shape: {"max_results": false, "data": [records]}, with the fixture records whose timestamp is
      inside the requested window (both ends included, as LI-COR does).
  GET /wqdata/devices/<id>/parameters/data?apiKey=..&from=..&to=..
      WQData's reply shape, paged the way WQData pages: at most PAGE_VALUES values per reply, a point's values can
      be split between two replies, and info.lastDataPointTimestamp is where the next request starts.

Only the keys and ids the test configures are accepted, so ingestion sending the wrong ones fails the test.
Uses only the standard library, and listens on 127.0.0.1 only. Every request is printed, so the CI log shows
exactly what ingestion asked the "vendors" for.
"""
import json
import pathlib
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"
LICOR = json.loads((FIXTURES / "licor.json").read_text(encoding="utf-8"))
WQDATA = json.loads((FIXTURES / "wqdata.json").read_text(encoding="utf-8"))

# The made-up credentials and ids the CI job gives the backend (see the e2e job in .github/workflows/ci.yml).
LICOR_KEY = "e2e-licor-key"
LICOR_LOGGER = "22051538"
WQ_KEY = "e2e-wq-key"
WQ_DEVICE = "4501"
PAGE_VALUES = 4   # small, so the test's few points still take several pages


def licor(params, headers):
    if headers.get("Authorization") != f"Bearer {LICOR_KEY}":
        return 401, {"error": "unauthorized"}
    if params.get("loggers") != LICOR_LOGGER:
        return 400, {"error": f"unknown logger {params.get('loggers')!r}"}
    start, end = params.get("start_date_time"), params.get("end_date_time")
    if not start or not end:
        return 400, {"error": "start_date_time and end_date_time are required"}
    # Fixture timestamps read "YYYY-MM-DD HH:MM:SSZ", the parameters "YYYY-MM-DD HH:MM:SS" (UTC): same order as text.
    records = [r for r in LICOR["data"] if start <= r["timestamp"].rstrip("Z") <= end]
    return 200, {"max_results": False, "data": records}


def wqdata(device, params):
    if params.get("apiKey") != WQ_KEY:
        return 401, {"error": "invalid key"}
    if device != WQ_DEVICE:
        return 404, {"error": f"unknown device {device!r}"}
    start, end = params.get("from"), params.get("to")
    if not start or not end:
        return 400, {"error": "from and to are required"}
    points = sorted((p for p in WQDATA["data"] if start <= p["timestamp"] <= end), key=lambda p: p["timestamp"])
    values = [(p["timestamp"], v) for p in points for v in p["values"]]
    page = values[:PAGE_VALUES]
    data = []
    for ts, value in page:
        if not data or data[-1]["timestamp"] != ts:
            data.append({"timestamp": ts, "values": []})
        data[-1]["values"].append(value)
    info = {"more": len(values) > len(page), "count": len(page), "total": len(values),
            "lastDataPointTimestamp": page[-1][0] if page else None}
    return 200, {"data": data, "info": info}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlparse(self.path)
        params = {k: v[0] for k, v in parse_qs(url.query).items()}
        parts = url.path.strip("/").split("/")
        if url.path == "/licor/data":
            status, body = licor(params, self.headers)
        elif len(parts) == 5 and parts[0] == "wqdata" and parts[1] == "devices" and parts[3:] == ["parameters", "data"]:
            status, body = wqdata(parts[2], params)
        else:
            status, body = 404, {"error": "not found"}
        shown = {k: v for k, v in params.items() if k != "apiKey"}
        rows = len(body.get("data") or [])
        print(f"[vendor stub] {url.path} {shown} -> {status}, {rows} records/points", flush=True)
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass   # do_GET prints its own line


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8900
    print(f"[vendor stub] listening on 127.0.0.1:{port}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
