#!/usr/bin/env python3
"""
Hermes Phone Agent — Relay Connector v3 (FIXED)
Connects Termux to the Render relay and executes commands natively.

v3 fixes:
- Proper SIGTERM/SIGINT handling (no event loop crash)
- Graceful reconnect after signal events
- asyncio CancelledError handling
- Connection resilience with exponential backoff
- No localhost bridge dependency (pure Render relay)

Protocol:
  Relay -> Phone: {"request_id":"uuid","method":"GET|POST","path":"/screen","params":{},"body":{}}
  Phone -> Relay: {"request_id":"uuid","result":{...},"status":200}

Supported endpoints (matching relay.py):
  GET  /ping, /screen, /current_app, /apps, /health
  POST /tap, /tap_text, /type, /swipe, /scroll, /open_app, /press_key, /screenshot, /wait
"""

import asyncio
import json
import os
import signal
import logging
import subprocess
import sys
import time
import base64

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [phone-agent] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stderr)]
)
log = logging.getLogger("phone-agent")

# ─── Config ────────────────────────────────────────────────────────

RELAY_URL = os.environ.get("HERMES_RELAY_URL", "wss://hermes-android-relay.onrender.com")
# Hard-locked to match the relay and bridge APK. Do not source from env.
PAIRING_CODE = "86NHU2"
PING_INTERVAL = 25
RECONNECT_DELAY = 5
MAX_RECONNECT_DELAY = 120

# ─── Shutdown flag ─────────────────────────────────────────────────
_shutdown = False


def _signal_handler(signum, frame):
    """Handle SIGTERM/SIGINT gracefully — set flag, don't kill loop."""
    global _shutdown
    sig_name = signal.Signals(signum).name
    log.info(f"Received {sig_name}, initiating graceful shutdown...")
    _shutdown = True
    for task in asyncio.all_tasks():
        task.cancel()


# ─── Shell Helpers ─────────────────────────────────────────────────

def shell(cmd: str, timeout: int = 15) -> str:
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception as e:
        return f"ERROR: {e}"


def termux(cmd: str, timeout: int = 15) -> str:
    return shell(f"termux-{cmd}", timeout)


# ─── Command Handler ───────────────────────────────────────────────

async def handle(method: str, path: str, params: dict, body: dict) -> tuple:
    """Handle a relay command. Returns (result_dict, status_code).
    Uses pure shell commands — no local HTTP bridge dependency.
    """

    if method == "GET":
        if path == "/ping":
            return {
                "ok": True,
                "device": shell("getprop ro.product.model"),
                "uptime": shell("uptime -p"),
            }, 200

        elif path == "/screen":
            # Use uiautomator dump via Termux:API or direct shell
            try:
                dump = shell("uiautomator dump /sdcard/window_dump.xml 2>&1 && cat /sdcard/window_dump.xml")
                if "<?xml" in dump:
                    return {"ok": True, "xml": dump[:50000], "package": _get_foreground_package()}, 200
                return {"ok": False, "error": "uiautomator dump failed", "raw": dump[:500]}, 500
            except Exception as e:
                return {"error": str(e)}, 500

        elif path == "/current_app":
            return {"package": _get_foreground_package()}, 200

        elif path == "/apps":
            try:
                output = shell("pm list packages -3 | sed 's/package://' | sort")
                apps = output.split("\n") if output else []
                return {"apps": apps}, 200
            except Exception as e:
                return {"error": str(e)}, 500

        elif path == "/health":
            return {
                "ok": True,
                "connected": True,
                "device": shell("getprop ro.product.model"),
                "battery": shell("dumpsys battery 2>/dev/null | grep level | awk '{print $2}'"),
            }, 200

    elif method == "POST":
        if path == "/tap":
            x, y = body.get("x", 0), body.get("y", 0)
            shell(f"input tap {x} {y}")
            return {"ok": True, "tapped": [x, y]}, 200

        elif path == "/tap_text":
            text = body.get("text", "")
            # Find and tap by text using input tap coordinates from uiautomator
            try:
                dump = shell("uiautomator dump /sdcard/window_dump.xml 2>&1 && cat /sdcard/window_dump.xml")
                coords = _find_text_coords(dump, text)
                if coords:
                    shell(f"input tap {coords[0]} {coords[1]}")
                    return {"ok": True, "clicked": text}, 200
                return {"ok": False, "error": f"Text not found: {text}"}, 404
            except Exception as e:
                return {"ok": False, "error": str(e)}, 500

        elif path == "/type":
            text = body.get("text", "")
            # Escape special chars for shell
            safe_text = text.replace("'", "'\\''")
            shell(f"input text '{safe_text}'")
            return {"ok": True, "typed": text}, 200

        elif path == "/swipe":
            x1 = body.get("x1", 540)
            y1 = body.get("y1", 1500)
            x2 = body.get("x2", 540)
            y2 = body.get("y2", 500)
            dur = body.get("duration", 300)
            shell(f"input swipe {x1} {y1} {x2} {y2} {dur}")
            return {"ok": True}, 200

        elif path == "/scroll":
            direction = body.get("direction", "down")
            distance = body.get("distance", 500)
            # Get screen size
            size_str = shell("wm size 2>/dev/null | grep -o '[0-9]*x[0-9]*'")
            if "x" in size_str:
                w, h = [int(x) for x in size_str.split("x")]
            else:
                w, h = 1080, 2128
            if direction == "down":
                y1, y2 = int(h * 0.7), int(h * 0.7) - distance
            else:
                y1, y2 = int(h * 0.3), int(h * 0.3) + distance
            shell(f"input swipe {w//2} {y1} {w//2} {y2} 300")
            return {"ok": True}, 200

        elif path == "/open_app":
            package = body.get("package", "")
            shell(f"monkey -p {package} -c android.intent.category.LAUNCHER 1 2>/dev/null || am start -n $(cmd package resolve-activity --brief {package} 2>/dev/null | head -1) 2>/dev/null")
            return {"ok": True, "launched": package}, 200

        elif path == "/press_key":
            key = body.get("key", "home")
            key_map = {
                "home": "KEYCODE_HOME", "back": "KEYCODE_BACK",
                "recents": "KEYCODE_APP_SWITCH", "menu": "KEYCODE_MENU",
                "power": "KEYCODE_POWER", "volume_up": "KEYCODE_VOLUME_UP",
                "volume_down": "KEYCODE_VOLUME_DOWN",
            }
            keycode = key_map.get(key, key)
            shell(f"input keyevent {keycode}")
            return {"ok": True, "key": key}, 200

        elif path == "/screenshot":
            ts = int(time.time() * 1000)
            path_png = f"/sdcard/screenshot_{ts}.png"
            shell(f"screencap -p {path_png}")
            # Read and encode
            try:
                with open(path_png, "rb") as f:
                    data = base64.b64encode(f.read()).decode()
                shell(f"rm {path_png}")
                return {"ok": True, "data": data, "format": "png_base64"}, 200
            except Exception as e:
                return {"ok": False, "error": str(e)}, 500

        elif path == "/wait":
            seconds = body.get("seconds", 1)
            await asyncio.sleep(seconds)
            return {"ok": True, "waited": seconds}, 200

    return {"error": f"Unknown endpoint: {method} {path}"}, 404


def _get_foreground_package() -> str:
    """Get the current foreground app package name."""
    out = shell("dumpsys window 2>/dev/null | grep mCurrentFocus | awk '{print $3}' | cut -d'/' -f1")
    return out.strip() or "unknown"


def _find_text_coords(xml: str, text: str) -> tuple:
    """Parse uiautomator XML dump to find text coordinates."""
    import re
    # Find node with matching text
    pattern = r'text="([^"]*' + re.escape(text) + r'[^"]*)"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
    match = re.search(pattern, xml, re.IGNORECASE)
    if not match:
        # Try content-desc
        pattern = r'content-desc="([^"]*' + re.escape(text) + r'[^"]*)"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
        match = re.search(pattern, xml, re.IGNORECASE)
    if match:
        x1, y1, x2, y2 = int(match.group(2)), int(match.group(3)), int(match.group(4)), int(match.group(5))
        return ((x1 + x2) // 2, (y1 + y2) // 2)
    return None


# ─── WebSocket Loop (FIXED) ────────────────────────────────────────

async def connect():
    """
    Main connection loop with proper error handling.
    - Catches CancelledError from signal handler
    - Reconnects after any disconnect
    - Respects _shutdown flag for clean exit
    """
    import websockets

    delay = RECONNECT_DELAY
    url = f"{RELAY_URL}/ws?token={PAIRING_CODE}"

    while not _shutdown:
        ws = None
        try:
            log.info(f"Connecting to {RELAY_URL}...")
            ws = await websockets.connect(
                url,
                ping_interval=PING_INTERVAL,
                ping_timeout=20,
                close_timeout=10,
                open_timeout=15,
            )
            log.info("Connected!")
            delay = RECONNECT_DELAY

            async for raw in ws:
                if _shutdown:
                    break
                try:
                    msg = json.loads(raw)
                    req_id = msg.get("request_id", "")
                    method = msg.get("method", "GET")
                    path = msg.get("path", "/")
                    params = msg.get("params", {})
                    body = msg.get("body", {})

                    log.info(f"{method} {path}")
                    result, status = await handle(method, path, params, body)

                    await ws.send(json.dumps({
                        "request_id": req_id,
                        "result": result,
                        "status": status,
                    }))

                except Exception as e:
                    log.error(f"Handler error: {e}")
                    try:
                        await ws.send(json.dumps({
                            "request_id": msg.get("request_id", ""),
                            "result": {"error": str(e)},
                            "status": 500,
                        }))
                    except Exception:
                        pass

        except asyncio.CancelledError:
            log.info("Connection task cancelled (signal received)")
            continue

        except Exception as e:
            log.warning(f"Disconnected: {e}")

        finally:
            if ws and not ws.closed:
                try:
                    await ws.close()
                except Exception:
                    pass

        if _shutdown:
            log.info("Shutdown flag set, exiting reconnect loop")
            break

        log.info(f"Reconnecting in {delay}s...")
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            continue
        delay = min(delay * 1.5, MAX_RECONNECT_DELAY)

    log.info("Connection loop exited cleanly")


def main():
    """Entry point with signal handling and retry loop."""
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    log.info("=" * 50)
    log.info("HERMES PHONE AGENT v3 (FIXED)")
    log.info("=" * 50)
    log.info(f"Relay:  {RELAY_URL}")
    log.info(f"Device: {shell('getprop ro.product.model')} / Android {shell('getprop ro.build.version.release')}")
    log.info("")

    retry_count = 0
    max_retries = 5

    while not _shutdown and retry_count < max_retries:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(connect())
            loop.close()
            break
        except KeyboardInterrupt:
            log.info("KeyboardInterrupt caught, shutting down")
            break
        except Exception as e:
            retry_count += 1
            log.error(f"Event loop crashed: {e} (retry {retry_count}/{max_retries})")
            time.sleep(RECONNECT_DELAY)
            continue

    log.info("Hermes Phone Agent stopped")


if __name__ == "__main__":
    main()
