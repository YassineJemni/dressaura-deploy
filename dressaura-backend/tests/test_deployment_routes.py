import os
import unittest
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "test-secret-key-only")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "3306")
os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("DB_NAME", "test")

from app.database import Base


class DeploymentRouteTests(unittest.TestCase):
    def test_render_entrypoint_registers_application_routers(self):
        with patch.object(Base.metadata, "create_all"):
            import main

        paths_and_methods = {
            (route.path, frozenset(getattr(route, "methods", set()) or set()))
            for route in main.app.routes
        }
        self.assertIn(("/orders/", frozenset({"POST"})), paths_and_methods)
        self.assertIn(("/auth/login", frozenset({"POST"})), paths_and_methods)
        self.assertIn(("/dresses/", frozenset({"GET"})), paths_and_methods)
        self.assertIn(("/chat/conversation", frozenset({"POST"})), paths_and_methods)
        self.assertIn(
            ("/chat/ws/{user_id}", frozenset()),
            paths_and_methods,
        )
