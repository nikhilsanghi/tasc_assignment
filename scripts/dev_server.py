"""Local dev server: static public/ + /api/<name> via each module's handle(). Fallback for `vercel dev`."""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import importlib
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

from core.paths import ROOT, load_dotenv
from api._shared import dispatch

PUBLIC = ROOT / "public"
CONTENT_TYPES = {".html": "text/html", ".js": "application/javascript", ".css": "text/css"}


class Handler(BaseHTTPRequestHandler):
    def _serve_static(self, path: pathlib.Path) -> None:
        if not path.exists():
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", CONTENT_TYPES.get(path.suffix, "application/octet-stream"))
        self.end_headers()
        self.wfile.write(path.read_bytes())

    def _api(self) -> None:
        name = self.path.split("/api/", 1)[1].split("?")[0]
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b""
        body = json.loads(raw) if raw else {}
        try:
            module = importlib.import_module(f"api.{name}")
        except ModuleNotFoundError:
            self.send_response(404)
            self.end_headers()
            return
        status, payload = dispatch(module.handle, dict(self.headers.items()), body)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode())

    def do_GET(self) -> None:
        if self.path.startswith("/api/"):
            self._api()
        elif self.path in ("/", "/index.html"):
            self._serve_static(PUBLIC / "index.html")
        elif self.path in ("/app.js", "/views.js", "/drawer.js", "/extras.js", "/styles.css"):
            self._serve_static(PUBLIC / self.path.lstrip("/"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self) -> None:
        if self.path.startswith("/api/"):
            self._api()
        else:
            self.send_response(404)
            self.end_headers()


if __name__ == "__main__":
    load_dotenv()
    server = HTTPServer(("localhost", 3000), Handler)
    print("Serving on http://localhost:3000")
    server.serve_forever()
