#!/usr/bin/env python3
"""Dependency-light MVP API and static app server."""

from __future__ import annotations

import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "public"
SCENARIO_DIR = ROOT / "data" / "scenarios"
SCENARIOS = [50, 100, 150, 200, 250]


class RequestHandler(BaseHTTPRequestHandler):
    server_version = "BangaloreFloodRiskMVP/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path == "/health":
            self.send_json({"status": "ok"})
            return

        if path == "/scenarios":
            self.send_json({"rainfall_mm": SCENARIOS, "default": 100, "unit": "mm"})
            return

        if path.startswith("/risk/"):
            self.handle_risk(path)
            return

        self.handle_static(path)

    def handle_risk(self, path: str) -> None:
        raw_value = path.removeprefix("/risk/").removesuffix(".geojson")
        try:
            rainfall_mm = int(raw_value)
        except ValueError:
            self.send_error_json(HTTPStatus.BAD_REQUEST, "Rainfall must be an integer in millimeters.")
            return

        if rainfall_mm not in SCENARIOS:
            self.send_error_json(HTTPStatus.NOT_FOUND, f"Unsupported rainfall scenario: {rainfall_mm}mm.")
            return

        scenario_path = SCENARIO_DIR / f"risk_{rainfall_mm:03d}mm.geojson"
        if not scenario_path.exists():
            self.send_error_json(HTTPStatus.NOT_FOUND, f"Scenario file missing for {rainfall_mm}mm. Run scripts/build_sample_scenarios.py.")
            return

        self.send_file(scenario_path, "application/geo+json")

    def handle_static(self, path: str) -> None:
        if path in ("", "/"):
            path = "/index.html"

        requested = (APP_DIR / path.lstrip("/")).resolve()
        if APP_DIR not in requested.parents and requested != APP_DIR:
            self.send_error_json(HTTPStatus.FORBIDDEN, "Forbidden")
            return

        if requested.is_dir():
            requested = requested / "index.html"

        if not requested.exists():
            self.send_error_json(HTTPStatus.NOT_FOUND, "Not found")
            return

        mime_type = mimetypes.guess_type(requested.name)[0] or "application/octet-stream"
        self.send_file(requested, mime_type)

    def send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, status: HTTPStatus, message: str) -> None:
        self.send_json({"error": message}, status)

    def send_file(self, path: Path, mime_type: str) -> None:
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8000), RequestHandler)
    print("Bangalore Flood Risk MVP running at http://127.0.0.1:8000")
    print("Static app: public/")
    print("Optional local API: /health, /scenarios, /risk/{rainfall_mm}")
    server.serve_forever()


if __name__ == "__main__":
    main()
