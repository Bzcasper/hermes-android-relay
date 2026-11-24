"""Standard-library auth regressions with a mocked aiohttp transport."""
import asyncio
import importlib.util
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

SECRET = "0123456789abcdef0123456789abcdef"
SOURCE = Path(__file__).resolve().parents[1] / "hermes_android_relay" / "relay.py"
if not SOURCE.exists():
    SOURCE = Path(__file__).with_name("hermes-android-relay-hardened.py")


def load_relay(secret):
    web = types.ModuleType("aiohttp.web")
    web.Request = object
    web.Application = object
    web.Response = lambda **kwargs: types.SimpleNamespace(status=kwargs.get("status", 200), body=kwargs.get("text"))
    web.WebSocketResponse = object
    web.json_response = lambda payload, status=200: types.SimpleNamespace(status=status, body=payload)
    web.middleware = lambda fn: fn
    aiohttp = types.ModuleType("aiohttp")
    aiohttp.web = web
    with patch.dict(sys.modules, {"aiohttp": aiohttp, "aiohttp.web": web}):
        with patch.dict(os.environ, {"PAIRING_CODE": secret}):
            spec = importlib.util.spec_from_file_location("relay_auth_under_test", SOURCE)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
    return module


class AuthTests(unittest.TestCase):
    def test_missing_secret_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "PAIRING_CODE must be configured"):
            load_relay("")

    def test_public_health_does_not_reveal_secret(self):
        module = load_relay(SECRET)
        request = types.SimpleNamespace(url="https://example.invalid/health")
        response = asyncio.run(module.health_handler(request))
        self.assertNotIn(SECRET, str(response.body))
        self.assertNotIn("token=", str(response.body))

    def test_websocket_rejects_unauthed_and_url_only_credentials(self):
        module = load_relay(SECRET)
        for headers in ({}, {"Authorization": "Bearer wrong"}, {"Authorization": SECRET}):
            with self.subTest(headers=headers):
                request = types.SimpleNamespace(
                    headers=headers, query={"token": SECRET}, remote="127.0.0.1"
                )
                response = asyncio.run(module.ws_handler(request))
                self.assertEqual(response.status, 401)

    def test_proxy_denies_missing_and_invalid_bearer_token(self):
        module = load_relay(SECRET)
        for headers in ({}, {"Authorization": "Bearer wrong"}, {"Authorization": SECRET}):
            with self.subTest(headers=headers):
                request = types.SimpleNamespace(headers=headers)
                response = asyncio.run(module.proxy_handler(request))
                self.assertEqual(response.status, 401)
                self.assertEqual(response.body["error"], "Unauthorized")
        self.assertEqual(module.state.request_count, 0)

    def test_authorized_proxy_reaches_phone_availability_check(self):
        module = load_relay(SECRET)
        request = types.SimpleNamespace(headers={"Authorization": f"Bearer {SECRET}"})
        response = asyncio.run(module.proxy_handler(request))
        self.assertEqual(response.status, 503)
        self.assertEqual(response.body["error"], "No phone connected")
        self.assertEqual(module.state.request_count, 1)


if __name__ == "__main__":
    unittest.main()
