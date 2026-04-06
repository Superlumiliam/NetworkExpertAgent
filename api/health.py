from http.server import BaseHTTPRequestHandler

from src.web.app import build_health_response, build_method_not_allowed_response


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self._send_response(build_health_response())

    def do_POST(self) -> None:
        self._send_response(build_method_not_allowed_response("GET"))

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
