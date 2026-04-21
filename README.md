# Hermes Android Relay (Render Free Tier)

WebSocket relay for hermes-android. Runs on Render's free tier.

## Architecture

```
Phone ──WebSocket──> Relay (Render) <──HTTP── Hermes (Termux)
```

## Deploy to Render

### Option A: Button Deploy (recommended)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=your-repo-url)

### Option B: Manual Deploy

1. Create new Web Service on [Render Dashboard](https://dashboard.render.com)
2. Connect your GitHub repo containing these files
3. Build command: `pip install -r requirements.txt`
4. Start command: `python hermes_android_relay/relay.py`
5. Set environment variable: `PAIRING_CODE=DIWF4P`
6. Deploy

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PAIRING_CODE` | `DEFAULT` | 6-char code for phone auth |
| `PORT` | `8766` | Server port (Render sets this) |
| `HOST` | `0.0.0.0` | Bind address |
| `WS_PING_INTERVAL` | `25` | WebSocket ping (keeps Render alive) |
| `CONNECTION_TIMEOUT` | `60` | Request timeout seconds |

## Endpoints

| Path | Method | Description |
|------|--------|-------------|
| `/health` | GET | Health check + status info |
| `/ping` | GET | Quick connectivity check |
| `/ws` | WebSocket | Phone connection endpoint |
| `/*` | * | Proxy to phone |

## Phone Connection

1. Install hermes-android-bridge APK
2. Grant Accessibility Service
3. Enter relay URL: `wss://your-service.onrender.com`
4. Enter pairing code: displayed in Render dashboard
5. Tap Connect

## Render Free Tier Notes

- **WebSocket keeps service alive**: After 2026-02-24 update, WebSocket messages count as activity
- **15 min idle timeout**: Phone auto-reconnects if Relay spins down
- **750 hours/month**: ~31 days continuous (sufficient)
- **Ephemeral disk**: State resets on deploy, but phone reconnects automatically

## Troubleshooting

"No phone connected":
- Check phone app shows "Connected"
- Verify pairing code matches
- Check Render logs: `heroku logs --tail`

"Connection refused":
- Service may be spinning up (takes ~1 min on free tier)
- Check Health endpoint in Render dashboard

## Credits

- [hermes-android](https://github.com/raulvidis/hermes-android) by @raulvidis
- [Hermes Agent](https://github.com/NousResearch/hermes-agent) by Nous Research
