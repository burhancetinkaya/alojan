"""Loopback-only development health endpoint; not the owner REST API."""

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import psycopg


def database_ready(dsn):
    if not dsn:
        return False
    try:
        with psycopg.connect(dsn, connect_timeout=2) as conn:
            conn.execute("SET LOCAL statement_timeout = 2000")
            return (
                conn.execute(
                    "SELECT count(*) FROM schema_migrations WHERE name = '0001_initial.sql'"
                ).fetchone()[0]
                == 1
            )
    except psycopg.Error:
        return False


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health/live":
            status, body = 200, {"status": "live", "service": "app-api", "mode": "local"}
        elif self.path == "/health/ready":
            ready = database_ready(os.environ.get("ALOJAN_DATABASE_URL"))
            status, body = (
                (200 if ready else 503),
                {
                    "status": "ready" if ready else "not_ready",
                    "service": "app-api",
                    "database": ready,
                    "voice_pipeline_ready": False,
                },
            )
        else:
            status, body = 404, {"error": "not_found"}
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *_):
        pass


def main():
    port = int(os.environ.get("ALOJAN_HEALTH_PORT", "18080"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
