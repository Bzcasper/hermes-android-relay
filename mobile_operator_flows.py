#!/usr/bin/env python3
"""
Mobile operator flows for Hermes Android relay.

Purpose:
- Run reusable, Samsung-safe UI automation flows over the relay.
- Keep flows small, observable, and restart-safe.

Usage examples:
  python3 mobile_operator_flows.py smoke
  python3 mobile_operator_flows.py settings-search --query battery
  python3 mobile_operator_flows.py camera-capture
  python3 mobile_operator_flows.py whatnot-prep
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests


DEFAULT_BASE = "https://hermes-android-relay.onrender.com"


@dataclass
class StepResult:
    name: str
    ok: bool
    status: int
    ms: int
    body_preview: str


class RelayOps:
    def __init__(self, base_url: str = DEFAULT_BASE, timeout: int = 35):
        self.base = base_url.rstrip("/")
        self.timeout = timeout
        self.results: List[StepResult] = []

    def req(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> requests.Response:
        url = f"{self.base}{path}"
        if payload is None:
            return requests.request(method, url, timeout=self.timeout)
        return requests.request(method, url, json=payload, timeout=self.timeout)

    def step(self, name: str, method: str, path: str, payload: Optional[Dict[str, Any]] = None, sleep_s: float = 0.8) -> requests.Response:
        t0 = time.time()
        r = self.req(method, path, payload)
        ms = int((time.time() - t0) * 1000)
        preview = r.text.replace("\n", " ")[:220]
        ok = (r.status_code == 200)
        self.results.append(StepResult(name=name, ok=ok, status=r.status_code, ms=ms, body_preview=preview))
        if sleep_s:
            time.sleep(sleep_s)
        return r

    def summarize(self) -> int:
        ok_count = sum(1 for r in self.results if r.ok)
        for i, r in enumerate(self.results, start=1):
            print(f"{i:02d}. {'OK' if r.ok else 'FAIL'} | {r.name} | http={r.status} | {r.ms}ms | {r.body_preview}")
        print(f"SUMMARY {ok_count}/{len(self.results)} successful")
        return 0 if ok_count == len(self.results) else 1

    def list_apps(self) -> List[Dict[str, Any]]:
        r = self.step("list apps", "GET", "/apps")
        if r.status_code != 200:
            return []
        return r.json().get("apps", [])


def flow_smoke(ops: RelayOps) -> int:
    ops.step("ping", "GET", "/ping")
    ops.step("screen", "GET", "/screen")
    ops.step("open settings", "POST", "/open_app", {"package": "com.android.settings"})
    ops.step("wait settings", "POST", "/wait", {"text": "Settings", "timeoutMs": 5000})
    ops.step("press home", "POST", "/press_key", {"key": "home"})
    ops.step("current app", "GET", "/current_app")
    return ops.summarize()


def flow_settings_search(ops: RelayOps, query: str) -> int:
    ops.step("open settings", "POST", "/open_app", {"package": "com.android.settings"})
    ops.step("tap search settings", "POST", "/tap_text", {"text": "Search settings", "exact": False})
    ops.step("type search query", "POST", "/type", {"text": query, "clearFirst": True})
    ops.step("wait query visible", "POST", "/wait", {"text": query, "timeoutMs": 5000})
    ops.step("press back", "POST", "/press_key", {"key": "back"})
    return ops.summarize()


def flow_camera_capture(ops: RelayOps) -> int:
    # No shutter click here (safe default). Just open/verify/return.
    ops.step("open camera", "POST", "/open_app", {"package": "com.sec.android.app.camera"})
    ops.step("wait camera", "POST", "/wait", {"timeoutMs": 5000})
    ops.step("screen hash", "GET", "/screen_hash")
    ops.step("press back", "POST", "/press_key", {"key": "back"})
    ops.step("press home", "POST", "/press_key", {"key": "home"})
    return ops.summarize()


def flow_whatnot_prep(ops: RelayOps) -> int:
    apps = ops.list_apps()
    lower = json.dumps(apps).lower()

    # Known/likely package patterns
    candidates = [
        "com.whatnot", "com.whatnotapp", "com.whatnot.mobile",
    ]

    pkg = None
    for c in candidates:
        if c in lower:
            pkg = c
            break

    if not pkg:
        print("WHATNOT not detected in installed apps via relay.")
        print("Install Whatnot app first, then rerun: python3 mobile_operator_flows.py whatnot-prep")
        return ops.summarize()

    ops.step("open whatnot", "POST", "/open_app", {"package": pkg})
    ops.step("wait whatnot", "POST", "/wait", {"timeoutMs": 7000})
    ops.step("screen", "GET", "/screen")
    ops.step("current app", "GET", "/current_app")
    return ops.summarize()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("flow", choices=["smoke", "settings-search", "camera-capture", "whatnot-prep"])
    ap.add_argument("--base-url", default=DEFAULT_BASE)
    ap.add_argument("--query", default="battery")
    args = ap.parse_args()

    ops = RelayOps(base_url=args.base_url)

    if args.flow == "smoke":
        return flow_smoke(ops)
    if args.flow == "settings-search":
        return flow_settings_search(ops, args.query)
    if args.flow == "camera-capture":
        return flow_camera_capture(ops)
    if args.flow == "whatnot-prep":
        return flow_whatnot_prep(ops)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
