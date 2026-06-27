from __future__ import annotations

import json
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
API_DIR = ROOT_DIR / "api"
sys.path.append(str(API_DIR))

from portfolio_analysis.report import analyze_portfolio


class LocalAnalyzeHandler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self) -> None:
        if self.path != "/api/analyze":
            self._send_json(404, {"error": "Ruta no encontrada."})
            return

        try:
            content_length = int(self.headers.get("content-length", "0"))
            raw_body = self.rfile.read(content_length)
            payload = json.loads(raw_body.decode("utf-8") or "{}")
            self._send_json(200, analyze_portfolio(payload))
        except ValueError as error:
            self._send_json(400, {"error": str(error)})
        except Exception as error:
            traceback.print_exc()
            self._send_json(500, {"error": f"Error generando el informe: {error}"})

    def log_message(self, format: str, *args) -> None:
        print(f"[local-api] {self.address_string()} - {format % args}", flush=True)


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    server = ThreadingHTTPServer(("127.0.0.1", port), LocalAnalyzeHandler)
    print(f"[local-api] listening on http://127.0.0.1:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
