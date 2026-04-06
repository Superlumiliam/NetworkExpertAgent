import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from src.web.app import (
    build_invalid_content_length_response,
    dispatch_local_request,
)


class NetworkExpertHandler(BaseHTTPRequestHandler):
    server_version = "NetworkExpertHTTP/0.1"

    def do_GET(self) -> None:
        self._send_response(dispatch_local_request("GET", self.path))

    def do_POST(self) -> None:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_response(build_invalid_content_length_response())
            return

        self._send_response(
            dispatch_local_request("POST", self.path, self.rfile.read(content_length))
        )

    def log_message(self, format: str, *args) -> None:
        return

    def _send_response(self, response) -> None:
        self.send_response(response.status)
        self.send_header("Content-Type", response.content_type)
        self.send_header("Content-Length", str(len(response.body)))
        for header_name, header_value in response.headers:
            self.send_header(header_name, header_value)
        self.end_headers()
        self.wfile.write(response.body)


def main() -> None:
    host = os.getenv("NETWORK_EXPERT_WEB_HOST", "127.0.0.1")
    port = int(os.getenv("NETWORK_EXPERT_WEB_PORT", "8000"))

    server = ThreadingHTTPServer((host, port), NetworkExpertHandler)
    print(f"Network Expert Web UI available at http://{host}:{port}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\\nShutting down web server...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
