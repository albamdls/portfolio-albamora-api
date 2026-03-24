import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


class ContactApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    @patch("app.services.contact_service.RESEND_API_KEY", "re_test_key")
    @patch("app.services.contact_service._send_resend_email")
    def test_contact_endpoint_sends_message(self, mocked_send):
        response = self.client.post(
            "/api/contact",
            json={
                "name": "Test User",
                "email": "test@example.com",
                "message": "Hello from the portfolio contact form.",
            },
            headers={"Origin": "http://localhost:5174"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["success"], True)
        mocked_send.assert_called_once()

    def test_contact_endpoint_validates_email(self):
        response = self.client.post(
            "/api/contact",
            json={
                "name": "Test User",
                "email": "invalid-email",
                "message": "Hello from the portfolio contact form.",
            },
            headers={"Origin": "http://localhost:5174"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("valid email", response.json()["detail"].lower())
