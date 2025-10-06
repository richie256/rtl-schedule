
import unittest
from http_server import create_app

class TestHttpServer(unittest.TestCase):
    def setUp(self):
        self.app = create_app().test_client()

    def test_health_check(self):
        response = self.app.get('/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"status": "ok"})

if __name__ == '__main__':
    unittest.main()
