
# Hermes Android Relay - Complete Setup Guide

## Quick Start (5 minutes)

### 1. Fork/Push to GitHub

```bash
cd /home/bc/hermes-android-relay-deploy

# Set your GitHub username
export GITHUB_USER="yourusername"

# Option A: Using GitHub CLI (recommended)
gh auth login
gh repo create hermes-android-relay --public --source=. --push

# Option B: Manual
git remote add origin https://github.com/$GITHUB_USER/hermes-android-relay.git
git push -u origin main
```

### 2. Deploy to Render

#### Option A: Dashboard (Easiest)
1. Go to https://dashboard.render.com
2. Click **New** → **Web Service**
3. Select **Build and deploy from a Git repository**
4. Connect GitHub → Select `hermes-android-relay`
5. Render auto-detects `render.yaml` - click **Create Web Service**
6. Wait for deployment (2-3 min)
7. Copy your URL: `https://hermes-android-relay-xxx.onrender.com`

#### Option B: Render CLI
```bash
# Install render CLI
curl https://render.com/install.sh | bash

# Login
render login

# Deploy from render.yaml
render deploy
```

### 3. Get APK

#### Option A: Download from GitHub Releases
1. Go to your repo → **Actions** tab
2. Click **Build Android APK** workflow
3. Download artifact: `app-debug-apk.zip`
4. Extract to get `app-debug.apk`
5. Install to phone via ADB:
   ```bash
   adb install -r -t app-debug.apk
   ```

#### Option B: Manual Build
```bash
# Clone source
git clone --depth 1 https://github.com/raulvidis/hermes-android.git
cd hermes-android/hermes-android-bridge

# Build
./gradlew assembleDebug

# Install
adb install app/build/outputs/apk/debug/app-debug.apk
```

### 4. Configure Phone

1. Open **Hermes Bridge** app on Samsung
2. Grant **Accessibility Service** permission
3. Tap **Connect to Server**
4. Enter your Render URL:
   ```
   wss://hermes-android-relay-xxx.onrender.com/ws
   ```
5. Enter pairing code: `DIWF4P`
6. Tap **Connect**

### 5. Verify in Termux

```bash
# In Termux, install plugin
curl -sSL https://raw.githubusercontent.com/raulvidis/hermes-android/main/install.sh | bash

# Set relay URL (optional - uses localhost:8766 by default)
echo "ANDROID_BRIDGE_URL=http://localhost:8766" >> ~/.hermes/.env

# Restart gateway
hermes gateway stop
hermes gateway

# Test from Telegram
android_ping
```

## Architecture

```
┌─────────────────┐      WebSocket      ┌─────────────────────┐      HTTP      ┌──────────────────┐
│   Samsung A24   │ ◄─────────────────► │  Render Free Tier   │ ◄─────────────►│   Hermes in      │
│  (hermes-       │    wss://...       │  (hermes-android-   │  localhost:8766│   Termux         │
│   android-      │    ?token=...     │   relay)            │                │                  │
│   bridge.apk)   │                    │                     │                │                  │
└─────────────────┘                    └─────────────────────┘                └──────────────────┘
                                                                                         │
                                                                                         │ Telegram
                                                                                         ▼
                                                                               ┌──────────────────┐
                                                                               │  You (anywhere)  │
                                                                               └──────────────────┘
```

## GitHub Actions Workflows

### 1. Build APK (`.github/workflows/build-apk.yml`)
- Triggers: Push to main affecting bridge code, manual dispatch
- Installs Android SDK, builds APK with gradle
- Uploads as artifact + creates release
- Downloads available at: `https://github.com/YOURUSER/hermes-android-relay/releases`

### 2. Deploy Render (`.github/workflows/deploy-render.yml`)
- Triggers: Push to main affecting relay code
- Deploys to Render using Render API
- Requires `RENDER_SERVICE_ID` and `RENDER_API_KEY` secrets

### 3. Test Python (`.github/workflows/test-python.yml`)
- Triggers: All pushes and PRs
- Lints with flake8
- Runs pytest (if tests exist)
- Matrix: Python 3.10, 3.11, 3.12

## Files Summary

| File | Purpose |
|------|---------|
| `render.yaml` | Render service configuration (blueprint) |
| `render.json` | Render deploy button metadata |
| `hermes_android_relay/relay.py` | WebSocket relay server |
| `requirements.txt` | Python dependencies (aiohttp only) |
| `.github/workflows/build-apk.yml` | Auto-build APK on push |
| `.github/workflows/deploy-render.yml` | Auto-deploy to Render |
| `.github/workflows/test-python.yml` | Python tests & lint |

## Environment Variables (Render)

| Variable | Default | Description |
|----------|---------|-------------|
| `PAIRING_CODE` | `DEFAULT` | 6-char auth code |
| `PORT` | `8766` | Server port |
| `HOST` | `0.0.0.0` | Bind address |
| `WS_PING_INTERVAL` | `25` | Keepalive ping (seconds) |
| `CONNECTION_TIMEOUT` | `60` | Request timeout |

## Troubleshooting

### "No phone connected"
- Check phone app shows "Connected"
- Verify pairing code matches `PAIRING_CODE` in Render env vars
- Check Render logs: Dashboard → Logs

### WebSocket connection fails
- Render free tier: Service may be spinning up (wait 1 min)
- Check health endpoint: `curl https://YOUR-URL/health`
- Phone needs internet (WebSocket connects OUT)

### APK won't install
- Uninstall old: `adb uninstall com.hermesandroid.bridge`
- Enable "Install from unknown sources"
- Try: `adb install -r -t app-debug.apk`
- Check Android SDK version (minSdk: 26 in build.gradle)

### GitHub Actions failing
- Check Actions logs: Repo → Actions tab
- Ensure `ANDROID_SDK_ROOT` is set in workflow
- Clear cache: Settings → Actions → Clear caches

## Security Notes

- **PAIRING_CODE**: Treat like a password. Regenerate if compromised.
- **Relay**: No TLS on WebSocket (ws:// not wss:// free tier limitation)
  - Use TLS proxy (nginx) for production
- **Phone**: Full device access via Accessibility Service
  - Only connect to trusted relays
  - Revoke Accessibility if compromised

## Costs

| Component | Cost | Notes |
|-----------|------|-------|
| GitHub | Free | Public repo, unlimited Actions minutes |
| Render Free Tier | Free | 750 hrs/month, web services only |
| APK Build | Free | GitHub Actions hosted runners |
| Phone Data | ~1 MB/day | WebSocket is efficient |

**Total: $0/month**

## Next Steps

1. **Backup**: Fork repo to preserve your setup
2. **Monitor**: Add Render uptime monitoring (free tier sleeps after 15min idle)
3. **Scale**: Upgrade to paid Render if you need persistent connections
4. **Secure**: Add TLS with Cloudflare or nginx proxy
5. **Extend**: Add more phone capabilities (see raulevidis/hermes-android docs)

## Links

- Repository: https://github.com/YOURUSER/hermes-android-relay
- Render Dashboard: https://dashboard.render.com
- raulevidis/hermes-android: https://github.com/raulvidis/hermes-android
- Hermes Agent: https://github.com/NousResearch/hermes-agent

---

**Pairing Code**: `DIWF4P`  
**Render URL**: `https://hermes-android-relay-xxx.onrender.com` (yours)
**Health Check**: `https://hermes-android-relay-xxx.onrender.com/health`
