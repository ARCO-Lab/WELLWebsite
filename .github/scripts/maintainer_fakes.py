"""A fake HTTP transport for the maintainer scripts' unit tests: canned JSON per (method, path), no network."""
import json
import urllib.parse


class FakeTransport:
    def __init__(self, routes):
        # {(method, path): body or (status, body) or (status, body, headers)}; path has no host or query string.
        self.routes = routes
        self.calls = []

    def __call__(self, method, url, headers, body):
        parsed = urllib.parse.urlsplit(url)
        self.calls.append({"method": method, "path": parsed.path, "query": urllib.parse.parse_qs(parsed.query),
                           "headers": headers, "body": json.loads(body) if body else None, "url": url})
        key = (method, parsed.path)
        if key not in self.routes:
            return 404, {}, json.dumps({"message": "Not Found"}).encode()
        value = self.routes[key]
        status, data, response_headers = 200, value, {}
        if isinstance(value, tuple):
            status, data = value[0], value[1]
            response_headers = value[2] if len(value) > 2 else {}
        return status, response_headers, json.dumps(data).encode()

    def paths(self):
        return [c["path"] for c in self.calls]
