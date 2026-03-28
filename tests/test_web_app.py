import os
import sys
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

# Set dummy env vars BEFORE importing anything from src
os.environ["OPENROUTER_API_KEY"] = "dummy_key"
os.environ["DEFAULT_MODEL"] = "dummy_model"
os.environ["ENABLE_LANGSMITH_TRACING"] = "false"

sys.path.append(os.getcwd())

from src.web.server import app


class TestWebApp(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_index_page_renders(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Network Expert Agent", response.text)
        self.assertIn('id="chatForm"', response.text)
        self.assertIn('/app.js', response.text)

    def test_health_endpoint(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_static_assets_render(self):
        css_response = self.client.get("/app.css")
        js_response = self.client.get("/app.js")

        self.assertEqual(css_response.status_code, 200)
        self.assertIn("--bg:", css_response.text)
        self.assertEqual(js_response.status_code, 200)
        self.assertIn("fetch('/api/chat'", js_response.text)

    def test_chat_endpoint_returns_answer(self):
        with patch("src.web.server.process_question", new=AsyncMock(return_value="Hello from server")) as mock_process:
            response = self.client.post("/api/chat", json={"message": "hello"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"answer": "Hello from server"})
        mock_process.assert_awaited_once_with("hello")

    def test_chat_endpoint_rejects_empty_message(self):
        response = self.client.post("/api/chat", json={"message": "   "})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"error": "Message is required"})

    def test_chat_endpoint_rejects_invalid_json(self):
        response = self.client.post(
            "/api/chat",
            data="{",
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"error": "Invalid JSON body"})

    def test_chat_endpoint_surfaces_processing_errors(self):
        with patch("src.web.server.process_question", new=AsyncMock(side_effect=RuntimeError("boom"))):
            response = self.client.post("/api/chat", json={"message": "hello"})

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json(), {"error": "Failed to process request: boom"})
