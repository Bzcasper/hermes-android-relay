# Hermes Android Relay

WebSocket relay server for hermes-android bridge connections.

## Deployed to Render

- Public endpoint exposes WebSocket at `/ws?token=<PAIRING_CODE>`
- Health check at `/health`
- Proxy all other requests to connected phone

## Phone Setup

1. Install hermes-android-bridge APK
2. Grant Accessibility Service
3. Enter relay URL: `wss://your-app.onrender.com/ws`
4. Enter pairing code: `DIWF4P`
5. Tap Connect

## Environment Variables

- `PAIRING_CODE`: 6-char code for phone authentication
- `PORT`: Port to listen on (Render sets this)
