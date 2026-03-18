#!/usr/bin/env python3
import json
import logging
import os
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

TOKEN = os.getenv("TOKEN", "")
CHECK_URL = f"https://api.telegram.org/bot{TOKEN}/getMe" if TOKEN else ""
CACHE_TTL_SECONDS = int(os.getenv("TELEGRAM_HEALTH_CACHE_TTL", "60"))
BOT_IDENTIFIER = os.getenv("BOT_IDENTIFIER", "telegram-showcase").strip() or "telegram-showcase"

_last_check_at = 0
_last_result_ok = False
_last_error = None

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def check_telegram():
    global _last_check_at, _last_result_ok, _last_error

    now = int(time.time())
    if now - _last_check_at < CACHE_TTL_SECONDS:
        return _last_result_ok, _last_error

    if not TOKEN:
        _last_check_at = now
        _last_result_ok = False
        _last_error = "missing_token"
        return _last_result_ok, _last_error

    request = Request(
        CHECK_URL,
        headers={"User-Agent": f"{BOT_IDENTIFIER}-health"},
    )
    try:
        with urlopen(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
            _last_check_at = now
            _last_result_ok = bool(payload.get("ok"))
            _last_error = None
            return _last_result_ok, _last_error
    except HTTPError as exc:
        logger.warning("Telegram health HTTP error: code=%s", exc.code)
        _last_check_at = now
        _last_result_ok = False
        _last_error = f"http_error_{exc.code}"
        return _last_result_ok, _last_error
    except (URLError, TimeoutError) as exc:
        logger.warning("Telegram health network error: %s", exc)
        _last_check_at = now
        _last_result_ok = False
        _last_error = "network_error"
        return _last_result_ok, _last_error
    except Exception as exc:
        logger.exception("Telegram health unexpected error")
        _last_check_at = now
        _last_result_ok = False
        _last_error = "unexpected_error"
        return _last_result_ok, _last_error


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path not in ("/", "/status"):
            self._send_json(404, {"error": "not found"})
            return

        ok, error = check_telegram()
        payload = {
            "ok": True,
            "timestamp": int(time.time()),
            "telegram_ok": ok,
        }
        if error:
            payload["error"] = error

        self._send_json(200, payload)

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 9106), Handler)
    server.serve_forever()
