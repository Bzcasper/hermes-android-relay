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
