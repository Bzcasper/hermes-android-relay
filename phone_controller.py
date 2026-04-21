#!/usr/bin/env python3
"""
Hermes Phone Controller v2 — Control an Android phone via the Render relay.

Architecture:
  Desktop (this) → HTTP → Render Relay → WebSocket → Phone (relay_connector.py)

No localhost bridge needed — all traffic goes through the Render relay.
The relay proxies HTTP requests to the phone's WebSocket connection.

Usage:
  controller = PhoneController()  # defaults to Render relay
  controller.ping()
  controller.tap(540, 1000)
  controller.screenshot()
"""

import json
import os
import time
import base64
import re
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    import urllib.request


@dataclass
class UINode:
    """Represents a UI element on screen."""
    id: int
    className: str = ""
    text: str = ""
    contentDesc: str = ""
    bounds: Dict[str, int] = field(default_factory=dict)
    clickable: bool = False
    editable: bool = False
    scrollable: bool = False
    enabled: bool = True
    checked: bool = False
    selected: bool = False
    packageName: str = ""

    @property
    def label(self) -> str:
        return self.text or self.contentDesc or ""

    @property
    def center(self) -> tuple:
        b = self.bounds
        return ((b.get("left", 0) + b.get("right", 0)) // 2,
                (b.get("top", 0) + b.get("bottom", 0)) // 2)


RENDER_RELAY = os.environ.get("HERMES_RENDER_RELAY", "https://hermes-android-relay.onrender.com")


class PhoneController:
    """Full phone control via Render relay (no localhost dependency)."""

    def __init__(self, base_url: str = None, timeout: int = 30):
        self.base_url = (base_url or RENDER_RELAY).rstrip("/")
        self.timeout = timeout
        self._session_state: Dict[str, Any] = {}

    # ─── HTTP Layer ───────────────────────────────────────────────

    def _request(self, method: str, path: str, data: Optional[dict] = None) -> dict:
        """Make HTTP request to bridge API."""
        url = f"{self.base_url}{path}"
        if HAS_REQUESTS:
            resp = requests.request(
                method, url,
                json=data,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"}
            )
            resp.raise_for_status()
            return resp.json()
        else:
            if data:
                body = json.dumps(data).encode()
                req = urllib.request.Request(url, data=body, method=method)
                req.add_header("Content-Type", "application/json")
            else:
                req = urllib.request.Request(url, method=method)
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read())

    def _get(self, path: str) -> dict:
        return self._request("GET", path)

    def _post(self, path: str, data: Optional[dict] = None) -> dict:
        return self._request("POST", path, data)

    # ─── Screen State ─────────────────────────────────────────────

    def get_state(self) -> dict:
        """Get full UI state: current package + accessibility node tree."""
        state = self._get("/state")
        self._session_state["last_package"] = state.get("package", "")
        return state

    def get_nodes(self) -> List[UINode]:
        """Get all UI nodes as UINode objects."""
        state = self.get_state()
        nodes = []
        for n in state.get("nodes", []):
            nodes.append(UINode(
                id=n.get("id", 0),
                className=n.get("className", ""),
                text=n.get("text", ""),
                contentDesc=n.get("contentDesc", ""),
                bounds=n.get("bounds", {}),
                clickable=n.get("clickable", False),
                editable=n.get("editable", False),
                scrollable=n.get("scrollable", False),
                enabled=n.get("enabled", True),
                checked=n.get("checked", False),
                selected=n.get("selected", False),
                packageName=n.get("packageName", ""),
            ))
        return nodes

    def get_screen_size(self) -> dict:
        """Get screen dimensions and density."""
        return self._get("/screen/size")

    def get_current_app(self) -> str:
        """Get current foreground app package name."""
        state = self.get_state()
        return state.get("package", "")

    # ─── Node Finding ─────────────────────────────────────────────

    def find_node(self, text: str = None, desc: str = None, class_name: str = None,
                  clickable: bool = None, editable: bool = None,
                  contains: bool = True) -> Optional[UINode]:
        """Find a single UI node matching criteria."""
        nodes = self.get_nodes()
        for n in nodes:
            if text is not None:
                if contains and text.lower() not in n.text.lower():
                    continue
                if not contains and text != n.text:
                    continue
            if desc is not None:
                if contains and desc.lower() not in n.contentDesc.lower():
                    continue
                if not contains and desc != n.contentDesc:
                    continue
            if class_name is not None and class_name.lower() not in n.className.lower():
                continue
            if clickable is not None and n.clickable != clickable:
                continue
            if editable is not None and n.editable != editable:
                continue
            if n.enabled:
                return n
        return None

    def find_all_nodes(self, text: str = None, desc: str = None,
                       class_name: str = None, clickable: bool = None) -> List[UINode]:
        """Find all UI nodes matching criteria."""
        nodes = self.get_nodes()
        results = []
        for n in nodes:
            if text is not None and text.lower() not in n.text.lower():
                continue
            if desc is not None and desc.lower() not in n.contentDesc.lower():
                continue
            if class_name is not None and class_name.lower() not in n.className.lower():
                continue
            if clickable is not None and n.clickable != clickable:
                continue
            results.append(n)
        return results

    # ─── Actions: Click / Tap ─────────────────────────────────────

    def click_node(self, node: UINode) -> dict:
        """Click a UI node by its ID."""
        return self._post("/node/click", {"id": node.id})

    def click_text(self, text: str, timeout: float = 5) -> dict:
        """Find and click a node containing the given text."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            node = self.find_node(text=text, clickable=True)
            if node:
                return self.click_node(node)
            node = self.find_node(text=text)
            if node:
                return self.click_node(node)
            time.sleep(0.5)
        raise ValueError(f"No clickable node found with text: {text}")

    def click_desc(self, desc: str, timeout: float = 5) -> dict:
        """Find and click a node by content description."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            node = self.find_node(desc=desc, clickable=True)
            if node:
                return self.click_node(node)
            time.sleep(0.5)
        raise ValueError(f"No clickable node found with desc: {desc}")

    def tap(self, x: int, y: int) -> dict:
        """Tap at screen coordinates."""
        return self._post("/gesture/tap", {"x": x, "y": y})

    def tap_center(self, node: UINode) -> dict:
        """Tap at the center of a node."""
        cx, cy = node.center
        return self.tap(cx, cy)

    # ─── Actions: Type / Text Input ───────────────────────────────

    def type_text(self, text: str, clear_first: bool = True) -> dict:
        """Type text into the currently focused field."""
        # Find editable node
        node = self.find_node(editable=True)
        if node and clear_first:
            self._post("/node/clear", {"id": node.id})
            time.sleep(0.2)
        return self._post("/input/text", {"text": text})

    def type_in_field(self, field_text: str, text: str, clear_first: bool = True) -> dict:
        """Click an editable field by its label/hint, then type."""
        node = self.find_node(text=field_text, editable=True)
        if not node:
            node = self.find_node(desc=field_text, editable=True)
        if not node:
            # Try clicking near the text label first
            label_node = self.find_node(text=field_text)
            if label_node:
                self.click_node(label_node)
                time.sleep(0.3)
                node = self.find_node(editable=True)
        if not node:
            raise ValueError(f"Editable field not found: {field_text}")
        self.click_node(node)
        time.sleep(0.3)
        return self.type_text(text, clear_first)

    # ─── Actions: Scroll / Swipe ──────────────────────────────────

    def scroll_down(self, distance: int = 500) -> dict:
        """Scroll down on current screen."""
        size = self.get_screen_size()
        w, h = size["width"], size["height"]
        return self._post("/gesture/swipe", {
            "x1": w // 2, "y1": int(h * 0.7),
            "x2": w // 2, "y2": int(h * 0.7) - distance,
            "duration": 300
        })

    def scroll_up(self, distance: int = 500) -> dict:
        """Scroll up on current screen."""
        size = self.get_screen_size()
        w, h = size["width"], size["height"]
        return self._post("/gesture/swipe", {
            "x1": w // 2, "y1": int(h * 0.3),
            "x2": w // 2, "y2": int(h * 0.3) + distance,
            "duration": 300
        })

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 300) -> dict:
        """Custom swipe gesture."""
        return self._post("/gesture/swipe", {
            "x1": x1, "y1": y1, "x2": x2, "y2": y2, "duration": duration
        })

    def scroll_to_text(self, text: str, max_scrolls: int = 10) -> Optional[UINode]:
        """Scroll until a node with given text is visible."""
        for _ in range(max_scrolls):
            node = self.find_node(text=text)
            if node:
                return node
            self.scroll_down()
            time.sleep(0.5)
        return None

    # ─── Actions: Global Navigation ───────────────────────────────

    def home(self) -> dict:
        """Press Home button."""
        return self._post("/global", {"action": "home"})

    def back(self) -> dict:
        """Press Back button."""
        return self._post("/global", {"action": "back"})

    def recents(self) -> dict:
        """Open recent apps."""
        return self._post("/global", {"action": "recents"})

    def notifications(self) -> dict:
        """Pull down notification shade."""
        return self._post("/global", {"action": "notifications"})

    def quick_settings(self) -> dict:
        """Pull down quick settings."""
        return self._post("/global", {"action": "quick_settings"})

    # ─── App Management ───────────────────────────────────────────

    def launch_app(self, package: str) -> dict:
        """Launch an app by package name."""
        return self._post("/app/launch", {"package": package})

    def launch_app_by_name(self, name: str) -> dict:
        """Launch an app by human-readable name (searches installed apps)."""
        apps = self.list_apps()
        name_lower = name.lower()
        for app in apps:
            pkg = app.get("package", "")
            label = app.get("label", "")
            if name_lower in pkg.lower() or name_lower in label.lower():
                return self.launch_app(pkg)
        raise ValueError(f"App not found: {name}")

    def list_apps(self) -> List[dict]:
        """List installed apps."""
        return self._get("/apps").get("apps", [])

    def is_app_running(self, package: str) -> bool:
        """Check if an app is in the foreground."""
        return self.get_current_app() == package

    # ─── Screen Capture ───────────────────────────────────────────

    def screenshot(self, mode: str = "accessibility") -> Optional[bytes]:
        """Take a screenshot. Returns PNG bytes or None."""
        result = self._post("/screen/screenshot", {"mode": mode})
        if result.get("ok"):
            return base64.b64decode(result["data"])
        return None

    def screenshot_save(self, path: str, mode: str = "accessibility") -> bool:
        """Take a screenshot and save to file."""
        data = self.screenshot(mode)
        if data:
            with open(path, "wb") as f:
                f.write(data)
            return True
        return False

    def read_screen_text(self) -> str:
        """Read all visible text from the current screen."""
        nodes = self.get_nodes()
        texts = []
        for n in nodes:
            if n.text and len(n.text.strip()) > 0:
                texts.append(n.text.strip())
            elif n.contentDesc and len(n.contentDesc.strip()) > 0:
                texts.append(f"[{n.contentDesc.strip()}]")
        return "\n".join(texts)

    def get_screen_summary(self) -> str:
        """Get a human-readable summary of the current screen."""
        state = self.get_state()
        pkg = state.get("package", "unknown")
        nodes = self.get_nodes()

        lines = [f"Current app: {pkg}"]
        lines.append(f"UI elements: {len(nodes)}")

        # Group by interesting elements
        buttons = [n for n in nodes if n.clickable and n.label]
        inputs = [n for n in nodes if n.editable]
        texts = [n for n in nodes if n.label and not n.clickable and not n.editable]

        if inputs:
            lines.append("Input fields:")
            for n in inputs[:5]:
                lines.append(f"  - {n.label[:60]}")

        if buttons:
            lines.append("Clickable elements:")
            for n in buttons[:10]:
                lines.append(f"  - {n.label[:60]}")

        if texts:
            lines.append("Text:")
            for n in texts[:10]:
                lines.append(f"  - {n.label[:60]}")

        return "\n".join(lines)

    # ─── Clipboard ────────────────────────────────────────────────

    def get_clipboard(self) -> str:
        """Get clipboard contents via Termux:API."""
        # This needs to be called from Termux shell, not bridge
        # Returns empty string if not accessible from bridge
        try:
            result = self._get("/clipboard")
            return result.get("text", "")
        except Exception:
            return ""

    def set_clipboard(self, text: str) -> dict:
        """Set clipboard contents."""
        return self._post("/clipboard", {"text": text})

    # ─── Convenience Workflows ────────────────────────────────────

    def open_and_read(self, package: str, wait: float = 2) -> str:
        """Open an app and read its screen content."""
        self.launch_app(package)
        time.sleep(wait)
        return self.read_screen_text()

    def fill_form(self, fields: Dict[str, str], submit_text: str = None) -> dict:
        """Fill a form with multiple fields.
        fields: {"field_label": "value_to_type", ...}
        """
        for label, value in fields.items():
            self.type_in_field(label, value)
            time.sleep(0.3)

        if submit_text:
            time.sleep(0.5)
            return self.click_text(submit_text)
        return {"ok": True}

    def navigate_settings(self, path: List[str]) -> bool:
        """Navigate through Android Settings menu.
        path: ["Apps", "Hermes Bridge", "Permissions"]
        """
        for item in path:
            node = self.scroll_to_text(item)
            if not node:
                return False
            self.click_node(node)
            time.sleep(1)
        return True

    def wait_for_app(self, package: str, timeout: float = 10) -> bool:
        """Wait for an app to come to foreground."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.get_current_app() == package:
                return True
            time.sleep(0.5)
        return False

    def wait_for_text(self, text: str, timeout: float = 10) -> Optional[UINode]:
        """Wait for text to appear on screen."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            node = self.find_node(text=text)
            if node:
                return node
            time.sleep(0.5)
        return None

    # ─── Samsung-Specific Helpers ─────────────────────────────────

    def samsung_settings_battery(self) -> dict:
        """Navigate to Samsung battery settings."""
        self.launch_app("com.android.settings")
        time.sleep(2)
        return self.click_text("Battery")

    def samsung_disable_battery_optimization(self) -> bool:
        """Attempt to disable battery optimization for an app.
        Note: This may require manual interaction on Samsung devices.
        """
        self.launch_app("com.android.settings")
        time.sleep(2)
        self.click_text("Apps")
        time.sleep(1)
        return True

    # ─── Debug / Introspection ────────────────────────────────────

    def dump_tree(self, max_depth: int = 3) -> str:
        """Dump the UI tree as a readable string."""
        nodes = self.get_nodes()
        lines = []
        for n in nodes:
            if not n.label and not n.className:
                continue
            indent = "  " * min(3, n.id % 4)  # Approximate depth
            parts = []
            if n.label:
                parts.append(f'"{n.label[:50]}"')
            parts.append(n.className.split(".")[-1])
            flags = []
            if n.clickable: flags.append("click")
            if n.editable: flags.append("edit")
            if n.scrollable: flags.append("scroll")
            if flags:
                parts.append(f"[{'|'.join(flags)}]")
            lines.append(f"{indent}{' '.join(parts)}")
        return "\n".join(lines[:50])  # Limit output

    def health_check(self) -> dict:
        """Check bridge connectivity and basic functionality."""
        try:
            state = self.get_state()
            size = self.get_screen_size()
            return {
                "connected": True,
                "package": state.get("package", ""),
                "screen": f"{size.get('width', 0)}x{size.get('height', 0)}",
                "nodes": len(state.get("nodes", [])),
            }
        except Exception as e:
            return {"connected": False, "error": str(e)}


# ─── CLI Entry Point ───────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    bridge_url = sys.argv[1] if len(sys.argv) > 1 else RENDER_RELAY
    ctrl = PhoneController(bridge_url)

    print("Hermes Phone Controller v2")
    print(f"Relay: {bridge_url}")
    print()

    # Health check
    health = ctrl.health_check()
    print(f"Connected: {health.get('connected', False)}")
    if health.get("connected"):
        print(f"Current app: {health['package']}")
        print(f"Screen: {health['screen']}")
        print(f"UI nodes: {health['nodes']}")
        print()
        print("Screen summary:")
        print(ctrl.get_screen_summary())
    else:
        print(f"Error: {health.get('error', 'unknown')}")
