import asyncio
import json
import logging
import os
import time
import threading
import uuid
from typing import Dict, Optional

import aiohttp
from aiohttp import web

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("android_relay")

class RelayState:
    """Mutable state for a relay instance."""
    def __init__(self, pairing_code: str, port: int, host: str):
        self.pairing_code = pairing_code
        self.port = port
        self.host = host
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.thread: Optional[threading.Thread] = None
        self.app: Optional[web.Application] = None
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None
        self.phone_ws: Optional[web.WebSocketResponse] = None
        self.pending: Dict[str, asyncio.Future] = {}
        self.pending_lock: Optional[asyncio.Lock] = None
        self.shutdown_event: Optional[asyncio.Event] = None
        self.started: bool = False


class Relay:
    """WebSocket relay bridging HTTP to Android phones."""
    
    _instance: Optional['Relay'] = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance
    
    def __init__(self, pairing_code: str = "DEFAULT", port: int = 8766, host: str = "0.0.0.0"):
        if hasattr(self, '_initialized'):
            return
        self._initialized = True
        
        self.pairing_code = pairing_code
        self.port = port
        self.host = host
        self.state: Optional[RelayState] = None
        self._running = False
        
    @property
    def is_running(self) -> bool:
        return self._running and self.state is not None and self.state.started
        
    def start(self, blocking: bool = False):
        """Start relay in background thread."""
        if self.is_running:
            logger.info("Relay already running")
            return
            
        self.state = RelayState(self.pairing_code, self.port, self.host)
        ready = threading.Event()
        
        def run_loop():
            asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
            self.state.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.state.loop)
            self.state.loop.run_until_complete(self._serve(ready))
            
        self.state.thread = threading.Thread(target=run_loop, daemon=True, name="android-relay")
        self.state.thread.start()
        self._running = True
        
        # Wait for server to be ready
        ready.wait(timeout=10)
        if not ready.is_set():
            raise RuntimeError("Relay failed to start")
            
        logger.info(f"Relay started on http://{self.host}:{self.port}")
        
        if blocking:
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                self.stop()
                
    async def _serve(self, ready: threading.Event):
        """Main async server routine."""
        self.state.app = web.Application(
            client_max_size=10*1024*1024  # 10MB for screenshots
        )
        
        # Routes
        self.state.app.router.add_get("/health", self._health_handler)
        self.state.app.router.add_get("/ws", self._ws_handler)
        self.state.app.router.add_get("/ping", self._ping_handler)
        self.state.app.router.add_route("*", "/{path:.*}", self._proxy_handler)
        
        # State synchronization primitives
        self.state.pending_lock = asyncio.Lock()
        self.state.shutdown_event = asyncio.Event()
        
        self.state.runner = web.AppRunner(self.state.app)
        await self.state.runner.setup()
        self.state.site = web.TCPSite(
            self.state.runner, 
            host=self.state.host, 
            port=self.state.port
        )
        await self.state.site.start()
        self.state.started = True
        ready.set()
        
        # Keep running
        await self.state.shutdown_event.wait()
        
    async def stop(self):
        """Stop the relay."""
        if self.state and self.state.shutdown_event:
            self.state.shutdown_event.set()
        self._running = False
        
    async def _health_handler(self, request: web.Request) -> web.Response:
        return web.json_response({
            "ok": True,
            "phone_connected": self.state and self.state.phone_ws is not None,
            "authenticated": self.state and hasattr(self.state, 'authenticated') and self.state.authenticated,
            "timestamp": time.time()
        })
        
    async def _ping_handler(self, request: web.Request) -> web.Response:
        return web.json_response({
            "status": "ok",
            "phone_connected": self.state and self.state.phone_ws is not None
        })
        
    async def _ws_handler(self, request: web.Request) -> web.WebSocketResponse:
        """Handle WebSocket connections from phone."""
        ws = web.WebSocketResponse(heartbeat=30.0, autoping=True)
        await ws.prepare(request)
        
        # Authenticate with pairing code
        token = request.query.get("token", "")
        if token != self.pairing_code:
            logger.warning(f"Rejected connection with invalid token")
            await ws.close(code=4001, message=b"Invalid pairing code")
            return ws
            
        # Accept connection
        old_ws = self.state.phone_ws
        if old_ws is not None:
            logger.info("Replacing existing phone connection")
            
        self.state.phone_ws = ws
        logger.info(f"Phone connected! Pairing: {self.pairing_code}")
        
        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    await self._handle_phone_message(msg.json())
                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    break
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            if self.state.phone_ws is ws:
                self.state.phone_ws = None
            logger.info("Phone disconnected")
            # Fail pending requests
            for req_id, fut in list(self.state.pending.items()):
                if not fut.done():
                    fut.set_exception(ConnectionError("Phone disconnected"))
                    
        return ws
        
    async def _handle_phone_message(self, data: dict):
        """Process responses from phone."""
        req_id = data.get("request_id")
        if req_id and req_id in self.state.pending:
            fut = self.state.pending.pop(req_id)
            if not fut.done():
                fut.set_result(data)
                
    async def _proxy_handler(self, request: web.Request) -> web.Response:
        """Proxy HTTP requests from tools to phone via WebSocket."""
        if not self.state or not self.state.phone_ws or self.state.phone_ws.closed:
            return web.json_response(
                {"error": "No phone connected"},
                status=503
            )
            
        try:
            # Build command
            body = None
            if request.can_read_body:
                body_text = await request.text()
                if body_text:
                    body = json.loads(body_text)
                    
            command = {
                "request_id": str(uuid.uuid4()),
                "method": request.method,
                "path": str(request.rel_url),
                "headers": dict(request.headers),
                "body": body
            }
            
            # Create response future
            future = asyncio.get_event_loop().create_future()
            self.state.pending[command["request_id"]] = future
            
            # Send to phone
            await self.state.phone_ws.send_json(command)
            
            # Wait for response with timeout
            result = await asyncio.wait_for(future, timeout=30.0)
            
            return web.json_response(result.get("result", {}))
            
        except asyncio.TimeoutError:
            self.state.pending.pop(command.get("request_id"), None)
            return web.json_response({"error": "Request timeout"}, status=504)
        except Exception as e:
            logger.error(f"Proxy error: {e}")
            return web.json_response({"error": str(e)}, status=500)


def start_relay(pairing_code: str = "DEFAULT", port: int = 8766, host: str = "0.0.0.0"):
    """Entry point for plugin."""
    relay = Relay(pairing_code=pairing_code, port=port, host=host)
    relay.start(blocking=True)


if __name__ == "__main__":
    import os
    start_relay(
        pairing_code=os.getenv("PAIRING_CODE", "DEFAULT123"),
        port=int(os.getenv("PORT", 8766)),
        host=os.getenv("HOST", "0.0.0.0")
    )
