
import unittest
from unittest.mock import MagicMock
from http_server import create_app

class TestHttpServer(unittest.TestCase):
    def setUp(self):
        # Mock rtl_data to avoid real initialization and network calls
        self.mock_rtl_data = MagicMock()
        self.app = create_app(rtl_data=self.mock_rtl_data).test_client()

    def test_health_check(self):
        response = self.app.get('/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"status": "ok"})

if __name__ == '__main__':
    unittest.main()
