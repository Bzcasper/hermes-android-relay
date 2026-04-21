# Hermes Android Relay

Consolidated repo: WebSocket relay server + Android bridge app + GitHub Actions CI/CD.

## Architecture

```
Phone (HermesBridge APK) ──WebSocket──> Relay (Render) <──HTTP── Hermes (anywhere)
                                      hermes-android-relay.onrender.com
```

## Repo Structure

```
hermes-android-relay/
├── hermes_android_relay/        # Render relay server (Python/aiohttp)
│   ├── __init__.py
│   └── relay.py
├── hermes-android-bridge/       # Android bridge app (Kotlin)
│   ├── app/src/main/kotlin/com/hermesandroid/bridge/
│   │   ├── client/RelayClient.kt        # WebSocket client
│   │   ├── service/BridgeAccessibilityService.kt  # A11y + foreground
│   │   ├── executor/ActionExecutor.kt   # Tap/type/swipe/scroll
│   │   ├── executor/ScreenReader.kt     # UI tree reader
│   │   └── ...
│   ├── build.gradle.kts
│   └── settings.gradle.kts
├── .github/workflows/
│   ├── build-apk.yml           # Builds bridge APK on push
│   └── deploy-render.yml       # Deploys relay to Render
├── relay_connector.py          # CLI tool for relay interaction
├── phone_controller.py         # Phone automation helpers
├── mobile_operator_flows.py    # Smoke tests and workflows
├── render.yaml                 # Render deployment config
├── requirements.txt            # Python deps for relay
├── Procfile                    # Render start command
└── README.md
```

## Deploy Relay to Render

1. Create new Web Service on [Render Dashboard](https://dashboard.render.com)
2. Connect this GitHub repo
3. Build command: `pip install -r requirements.txt`
4. Start command: `python hermes_android_relay/relay.py`
5. Set environment variable: `PAIRING_CODE=86NHU2`
6. Deploy

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PAIRING_CODE` | `86NHU2` | 6-char code for phone auth |
| `PORT` | auto | Server port (Render sets this) |
| `HOST` | `0.0.0.0` | Bind address |
| `WS_PING_INTERVAL` | `25` | WebSocket ping (keeps Render alive) |
| `CONNECTION_TIMEOUT` | `60` | Request timeout seconds |

## Endpoints

| Path | Method | Description |
|------|--------|-------------|
| `/health` | GET | Health check + phone status |
| `/ping` | GET | Quick phone connectivity check |
| `/screen` | GET | UI accessibility tree |
| `/current_app` | GET | Foreground app package |
| `/apps` | GET | Installed packages list |
| `/tap` | POST | Tap at coordinates or node ID |
| `/tap_text` | POST | Tap element by visible text |
| `/type` | POST | Type text into focused field |
| `/swipe` | POST | Swipe gesture |
| `/scroll` | POST | Scroll screen |
| `/open_app` | POST | Launch app by package name |
| `/press_key` | POST | Press home/back/recents |
| `/screenshot` | GET | Capture screen |
| `/wait` | POST | Wait N seconds or for element |

## Build Bridge APK

GitHub Actions builds automatically on push to `hermes-android-bridge/**`.

Manual trigger: Go to Actions > Build Android APK > Run workflow.

Download: Actions run > Artifacts > app-debug-apk.

## Bridge App Setup on Phone

1. Download APK from GitHub Releases or Actions artifacts
2. `adb install hermes-bridge.apk`
3. Open app, enter:
   - Server URL: `https://hermes-android-relay.onrender.com`
   - Pairing code: `86NHU2`
4. Tap Connect
5. Enable Accessibility: Settings > Accessibility > Hermes Bridge > ON

## Known Issues

- Android 14+: Bridge uses `FOREGROUND_SERVICE_TYPE_SPECIAL_USE` only (mediaProjection requires user consent grant first)
- Render free tier sleeps after 15min idle — phone auto-reconnects
- First request after idle takes ~30s to wake
