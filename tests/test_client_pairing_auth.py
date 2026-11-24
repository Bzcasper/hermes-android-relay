"""Regression tests for clients used after relay bearer-auth enforcement."""
import importlib.util
import pathlib
import sys
import types
import unittest
from unittest.mock import patch

SECRET = "0123456789abcdef0123456789abcdef"
ROOT = pathlib.Path(__file__).resolve().parents[1]
if not (ROOT / "phone_controller.py").exists():
    ROOT = pathlib.Path(__file__).resolve().parent

def load_file(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(name, None)
    return module

class ClientAuthTests(unittest.TestCase):
    def test_controller_requires_credential(self):
        fake_requests = types.ModuleType("requests")
        fake_requests.request = lambda *args, **kwargs: None
        with patch.dict(sys.modules, {"requests": fake_requests}), patch.dict("os.environ", {"PAIRING_CODE": ""}):
            mod = load_file("phone_controller_none", "phone_controller.py")
            with self.assertRaisesRegex(ValueError, "PAIRING_CODE"):
                mod.PhoneController()

    def test_controller_sends_bearer(self):
        received = {}
        def request(*args, **kwargs):
            received.update(kwargs)
            return types.SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"status": "ok"})
        fake_requests = types.ModuleType("requests")
        fake_requests.request = request
        with patch.dict(sys.modules, {"requests": fake_requests}), patch.dict("os.environ", {"PAIRING_CODE": SECRET}):
            mod = load_file("phone_controller_valid", "phone_controller.py")
            self.assertEqual(mod.PhoneController()._get("/ping").get("status"), "ok")
        self.assertEqual(received["headers"]["Authorization"], "Bearer " + SECRET)

    def test_mobile_operations_sends_bearer(self):
        received = {}
        def request(*args, **kwargs):
            received.update(kwargs)
            return types.SimpleNamespace(status_code=200, text="{}", json=lambda: {})
        fake_requests = types.ModuleType("requests")
        fake_requests.request = request
        with patch.dict(sys.modules, {"requests": fake_requests}), patch.dict("os.environ", {"PAIRING_CODE": SECRET}):
            mod = load_file("mobile_operator_valid", "mobile_operator_flows.py")
            ops = mod.RelayOps()
            ops.req("GET", "/screen")
        self.assertEqual(received["headers"]["Authorization"], "Bearer " + SECRET)

if __name__ == "__main__":
    unittest.main()
