# Pairing credential migration (draft, not deployed)

The previous Android bridge and relay used a fixed credential committed to source and exposed in relay status output. Treat that credential as compromised. Do not deploy the new relay by itself until the Android app is rebuilt and its pairing credential configured.

1. Build and install the updated Android bridge APK. The bridge generates a unique 48-character hexadecimal pairing credential on its first launch and displays it in the app.
2. Copy that credential locally into the hosting provider's **secret environment variable** named `PAIRING_CODE`. Do not paste it into source, GitHub issues, build logs, deployment YAML or a public HTTP request.
3. Restart the relay only after its secret is configured. Without `PAIRING_CODE` (minimum 16 characters), the new relay intentionally refuses startup.
4. Enter the trusted relay HTTPS origin in the bridge app and connect. Verify that the authenticated WebSocket connection is established, then verify permitted phone actions with a live device.
5. To rotate the credential: disconnect, use the bridge's Rotate/Refresh action, replace `PAIRING_CODE` in the secret store, restart the relay, and reconnect. Old deployments must be treated as unauthorized until rotated.
6. Confirm that relay `/health` shows neither the pairing credential nor a query-string token; confirm Android logs do not print token-bearing URLs.

## Important architecture boundary

`hermes-android-relay` is an Android **remote-control bridge** plus a separate server. It does not prove that a Hermes Agent gateway process is running on the Ultra itself. It does not provide verified camera video to the ROG. The separate Termux/Android Hermes gateway and camera integration require independent live tests.

## Rollback

Retain the previous source and APK hashes. A rollback to the old relay or APK also restores the known insecure pairing design and should not be exposed to an untrusted network. Prefer restoring the previous service while disabling external access and completing a safe coordinated credential migration.

## Verification status

No production relay restart, Android APK build, ADB install, or Ultra camera access was performed by this PR. Validate with the Python tests and the Android Gradle build before a controlled deployment.

## Transport requirements

The Android bridge accepts only a clean HTTPS relay origin (for example, `https://your-relay.example`). It rejects HTTP/WS plaintext, embedded credentials, URL paths, query strings and fragments before storing the endpoint or replacing its existing connection. The pairing credential is sent in a WebSocket `Authorization: Bearer` header over WSS to `/ws`, never in a URL query string or application log messages. The updated relay rejects query-string-only credentials, so the Android APK and any Python connector must be upgraded together. The server operator must still configure HTTPS and rotate the previously public fixed credential in the secret store.

## CI verification limitation (2026-11-24)

GitHub Actions reports failed Android and Python workflows, but the connected GitHub job records provide no steps or log URLs and the downloadable logs return 404. Do not infer a Kotlin compiler failure or a dependency error without actual job logs. Local Python tests exercise mocked transports only; an Android SDK build, APK artifact inspection, and installation on the Ultra remain required.

## Compatibility note

The updated relay rejects the previous `?token=...` WebSocket handshake. Deploy it only alongside updated Android bridge and `relay_connector.py` clients, with the same rotated secret. Verify these exact client versions and the hosting reverse proxy's support for forwarding the `Authorization` header during WebSocket upgrade.
