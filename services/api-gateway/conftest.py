"""
Pytest configuration and shared fixtures for the API Gateway.

Ensures SECRET_KEY is available before any module imports that instantiate
the Settings singleton (app/core/config.py:settings = Settings()).
"""

import os


def pytest_configure(config):
    os.environ.setdefault(
        "SECRET_KEY",
        "test-secret-key-for-jwt-signing-do-not-use-in-production",
    )
