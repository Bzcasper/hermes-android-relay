#!/usr/bin/env python3
"""
Hermes Android Relay - Render Free Tier Optimized
WebSocket relay bridging HTTP to Android phones.

Render Free Tier Notes:
- WebSocket messages keep service alive (2026-02-24 update)
- 15 min idle timeout = phone reconnects automatically
- Ephemeral filesystem = state resets on deploy (acceptable)
- 750 hours/month = ~31 days continuous (sufficient)
"""

import asyncio
import json
import logging
import os
import time
import uuid
from typing import Dict, Optional
from datetime import datetime

import aiohttp
from aiohttp import web

# Configure logging for Render
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]  # Render captures stdout
)
logger = logging.getLogger("android_relay")

# Config from environment
PAIRING_CODE = os.getenv("PAIRING_CODE", "DEFAULT")
PORT = int(os.getenv("PORT", "8766"))
HOST = os.getenv("HOST", "0.0.0.0")
WS_PING_INTERVAL = float(os.getenv("WS_PING_INTERVAL", "25"))
CONNECTION_TIMEOUT = float(os.getenv("CONNECTION_TIMEOUT", "60"))

# State tracking (ephemeral - fine for Render)
phone_connections: Dict[str, web.WebSocketResponse] = {}
pending_requests: Dict[str, asyncio.Future] = {}
connection_times: Dict[str, float] = {}


def get_active_connection() -> Optional[tuple[str, web.WebSocketResponse]]:
    """Return newest healthy phone connection, cleaning up closed sockets."""
    # Remove closed sockets first
    for cid, ws in list(phone_connections.items()):
        if ws.closed:
            phone_connections.pop(cid, None)
            connection_times.pop(cid, None)

    if not phone_connections:
        return None

    # Pick most recent connection to avoid stale routing
    conn_id = max(connection_times, key=connection_times.get)
    ws = phone_connections.get(conn_id)
    if ws is None:
        return None
    return conn_id, ws


class RelayState:
    """Relay state management with Render optimizations."""
    
    def __init__(self):
        self.start_time = time.time()
        self.connection_count = 0
        self.request_count = 0
        
    def get_stats(self) -> dict:
        return {
            "uptime_seconds": time.time() - self.start_time,
            "connections_total": self.connection_count,
            "requests_total": self.request_count,
            "current_connections": len(phone_connections),
            "pending_requests": len(pending_requests)
        }


state = RelayState()


# ─── Handlers ─────────────────────────────────────────────────────────────────

async def health_handler(request: web.Request) -> web.Response:
    """Health check for Render + status info."""
    # Render expects 200 OK, returns quickly
    ws_url = str(request.url).replace("https://", "wss://").replace("/health", "/ws")
    
    return web.json_response({
        "ok": True,
        "status": "healthy",
        "service": "hermes-android-relay",
        "version": "0.3.0-render",
        "phone_connected": len(phone_connections) > 0,
        "pairing_code_prefix": PAIRING_CODE[:2] + "***",
        "stats": state.get_stats(),
        "websocket_endpoint": ws_url + "?token=" + PAIRING_CODE,
        "timestamp": datetime.utcnow().isoformat()
    })


async def ping_handler(request: web.Request) -> web.Response:
    """Quick ping for phone connectivity check."""
    return web.json_response({
        "status": "ok",
        "phone_connected": len(phone_connections) > 0,
        "timestamp": time.time()
    })


async def ws_handler(request: web.Request) -> web.WebSocketResponse:
    """
    WebSocket handler for phone connections.
    Render optimization: keeps service alive via WebSocket traffic.
    """
    # Validate pairing code before upgrade
    token = request.query.get("token", "")
    if token != PAIRING_CODE:
        logger.warning(f"Rejected connection: invalid token from {request.remote}")
        return web.Response(
            status=401,
            text=json.dumps({"error": "Invalid pairing code"})
        )
    
    # Upgrade to WebSocket
    ws = web.WebSocketResponse(
        heartbeat=WS_PING_INTERVAL,
        autoping=True,
        timeout=CONNECTION_TIMEOUT
    )
    await ws.prepare(request)
    
    conn_id = str(uuid.uuid4())[:8]
    logger.info(f"Phone connected [{conn_id}] from {request.remote}")
    
    # Register connection
    phone_connections[conn_id] = ws
    connection_times[conn_id] = time.time()
    state.connection_count += 1

    # Keep only one active phone connection to avoid stale routing/races.
    for old_id, old_ws in list(phone_connections.items()):
        if old_id == conn_id:
            continue
        logger.info(f"Closing stale connection [{old_id}] in favor of [{conn_id}]")
        try:
            await old_ws.close(code=1000, message=b"Replaced by newer connection")
        except Exception:
            pass
        phone_connections.pop(old_id, None)
        connection_times.pop(old_id, None)
    
    try:
        # Send welcome message
        await ws.send_json({
            "type": "connected",
            "conn_id": conn_id,
            "relay_version": "0.3.0-render",
            "message": "Connected to hermes-android relay"
        })
        
        # Message loop
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                await handle_phone_message(msg.json(), conn_id)
            elif msg.type == aiohttp.WSMsgType.ERROR:
                logger.error(f"WebSocket error [{conn_id}]: {ws.exception()}")
                break
            elif msg.type == aiohttp.WSMsgType.CLOSED:
                break
                
    except Exception as e:
        logger.error(f"Connection error [{conn_id}]: {e}")
    finally:
        # Cleanup
        logger.info(f"Phone disconnected [{conn_id}]")
        if conn_id in phone_connections:
            del phone_connections[conn_id]
        if conn_id in connection_times:
            del connection_times[conn_id]
        
        # Fail pending requests for this connection
        for req_id, future in list(pending_requests.items()):
            if req_id.startswith(conn_id + ":"):
                if not future.done():
                    future.set_exception(ConnectionError("Phone disconnected"))
                pending_requests.pop(req_id, None)
    
    return ws


async def handle_phone_message(data: dict, conn_id: str):
    """Process responses from phone."""
    req_id = data.get("request_id")
    if req_id and req_id in pending_requests:
        future = pending_requests.pop(req_id)
        if not future.done():
            future.set_result(data)


async def proxy_handler(request: web.Request) -> web.Response:
    """Proxy HTTP requests from tools to phone via WebSocket."""
    state.request_count += 1
    
    # Check if any phone is connected (use newest healthy connection)
    active = get_active_connection()
    if not active:
        return web.json_response(
            {"error": "No phone connected", "connected_phones": 0},
            status=503
        )

    conn_id, ws = active
    
    try:
        # Build command
        body = None
        if request.can_read_body:
            body_text = await request.text()
            if body_text:
                try:
                    body = json.loads(body_text)
                except json.JSONDecodeError:
                    body = body_text
        
        req_id = f"{conn_id}:{uuid.uuid4().hex[:12]}"
        command = {
            "request_id": req_id,
            "method": request.method,
            "path": str(request.rel_url),
            "headers": {"content-type": request.content_type} if request.content_type else {},
            "body": body
        }
        
        # Create response future
        future = asyncio.get_event_loop().create_future()
        pending_requests[req_id] = future
        
        # Send to phone
        await ws.send_json(command)
        logger.debug(f"Sent command [{req_id}]: {command['method']} {command['path']}")
        
        # Wait for response with timeout
        result = await asyncio.wait_for(future, timeout=CONNECTION_TIMEOUT)
        
        return web.json_response(result.get("result", {}))
        
    except asyncio.TimeoutError:
        pending_requests.pop(req_id, None)
        logger.warning(f"Request timeout [{req_id}]")
        return web.json_response(
            {"error": "Request timeout", "timeout_seconds": CONNECTION_TIMEOUT},
            status=504
        )
    except Exception as e:
        logger.error(f"Proxy error: {e}")
        return web.json_response(
            {"error": str(e)},
            status=500
        )


# ─── Application Setup ──────────────────────────────────────────────────────

def create_app() -> web.Application:
    """Create aiohttp application with routes."""
    app = web.Application(
        client_max_size=10*1024*1024,  # 10MB for screenshots
        middlewares=[error_middleware]
    )
    
    # Routes - order matters for matching
    app.router.add_get("/health", health_handler)
    app.router.add_get("/ping", ping_handler)
    app.router.add_get("/ws", ws_handler)
    app.router.add_route("*", "/{path:.*}", proxy_handler)
    
    return app


@web.middleware
async def error_middleware(request, handler):
    """Catch-all error middleware."""
    try:
        return await handler(request)
    except web.HTTPException as ex:
        raise
    except Exception as e:
        logger.error(f"Unhandled error: {e}")
        return web.json_response(
            {"error": "Internal server error", "detail": str(e)},
            status=500
        )


# ─── Entry Point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = create_app()
    
    logger.info("=" * 60)
    logger.info("HERMES-ANDROID RELAY v0.3.0 (Render Free Tier)")
    logger.info("=" * 60)
    logger.info(f"Pairing Code: {PAIRING_CODE}")
    logger.info(f"Listening on: {HOST}:{PORT}")
    logger.info(f"Health check: http://{HOST}:{PORT}/health")
    logger.info("")
    logger.info("Phone connects to: /ws?token=" + PAIRING_CODE)
    logger.info("=" * 60)
    
    web.run_app(
        app,
        host=HOST,
        port=PORT,
        access_log=logger,  # Log all requests
        handle_signals=True
    )
