# Fix Screen Recording on Android 14+ (SDK 34+)

## Problem

On Android 16 (Samsung A24), tapping the "Screen Recording" toggle in Hermes Bridge crashes the app:

```
SecurityException: Media projections require a foreground service of type 
ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION
```

**Root cause:** Since Android 14 (API 34), `MediaProjectionManager.getMediaProjection()` requires a running foreground service with type `FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION`. The current code calls `getMediaProjection()` in `MainActivity.onActivityResult()` with no such service.

**Also:** `PROJECT_MEDIA` appop was rejected by the user earlier, and the fallback for screenshots via `takeScreenshot()` in `ActionExecutor` also uses MediaProjection (will fix too).

## Scope

4 files total. Nothing else is touched.

## Changes

### 1. CREATE: `app/src/main/kotlin/com/hermesandroid/bridge/media/MediaProjectionService.kt`

A minimal Android foreground service that:
- Declares `foregroundServiceType="mediaProjection"` in manifest
- Starts as foreground service with a notification before capture consent
- Holds the `MediaProjection` object so `ScreenRecorder` can access it
- Has companion object `instance` pattern (same as `BridgeAccessibilityService`)

```kotlin
package com.hermesandroid.bridge.media

import android.app.*
import android.content.Intent
import android.content.pm.ServiceInfo
import android.media.projection.MediaProjection
import android.os.Binder
import android.os.Build
import android.os.IBinder

class MediaProjectionService : Service() {

    companion object {
        private const val CHANNEL_ID = "media_projection_channel"
        private const val NOTIFICATION_ID = 2

        @Volatile
        var instance: MediaProjectionService? = null
            private set

        var projection: MediaProjection? = null
            private set

        fun hasProjection(): Boolean = projection != null

        fun setProjection(p: MediaProjection?) {
            projection?.stop()
            projection = p
        }
    }

    inner class LocalBinder : Binder() {
        fun getService(): MediaProjectionService = this@MediaProjectionService
    }

    private val binder = LocalBinder()

    override fun onBind(intent: Intent?): IBinder = binder

    override fun onCreate() {
        super.onCreate()
        instance = this
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val notification = buildNotification()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(
                NOTIFICATION_ID,
                notification,
                ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION
            )
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }
        return START_NOT_STICKY
    }

    private fun buildNotification(): Notification {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "Screen Recording",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Required for screen capture"
            }
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(channel)
        }

        val builder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            Notification.Builder(this, CHANNEL_ID)
        } else {
            @Suppress("DEPRECATION")
            Notification.Builder(this)
        }

        return builder
            .setContentTitle("Hermes Bridge")
            .setContentText("Screen recording ready")
            .setSmallIcon(android.R.drawable.ic_menu_camera)
            .setOngoing(true)
            .build()
    }

    override fun onDestroy() {
        instance = null
        super.onDestroy()
    }
}
```

**Key points:**
- `FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION` in `startForeground()` — this is what Android 14+ checks
- Companion object `projection` field — `ScreenRecorder` and `ActionExecutor` can access it without binding
- `START_NOT_STICKY` — if killed, don't auto-restart (user re-grants permission)
- Minimal notification — just enough to satisfy foreground service requirement

### 2. MODIFY: `app/src/main/AndroidManifest.xml`

Add one service declaration after the notification listener:

```xml
        <!-- Media projection foreground service (Android 14+) -->
        <service
            android:name=".media.MediaProjectionService"
            android:exported="false"
            android:foregroundServiceType="mediaProjection" />
```

The `foregroundServiceType="mediaProjection"` attribute is what Android checks at runtime. `exported="false"` — this service is only started from within the app.

**Nothing else changes in the manifest.** `BridgeAccessibilityService` stays `specialUse`.

### 3. MODIFY: `app/src/main/kotlin/com/hermesandroid/bridge/MainActivity.kt`

Two changes:

**Change A — `setupPermissions()` switchScreenRecord handler (lines 145-150):**

Before requesting capture consent, start `MediaProjectionService` as foreground service:

```kotlin
        switchScreenRecord.setOnCheckedChangeListener { _, isChecked ->
            if (isChecked && !MediaProjectionService.hasProjection()) {
                // Start the foreground service FIRST (required on Android 14+)
                val serviceIntent = Intent(this, MediaProjectionService::class.java)
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    startForegroundService(serviceIntent)
                } else {
                    startService(serviceIntent)
                }
                // Small delay to let the service start before showing consent dialog
                window.decorView.post {
                    val mpm = getSystemService(MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
                    startActivityForResult(mpm.createScreenCaptureIntent(), REQUEST_CODE_SCREEN_RECORD)
                }
            }
        }
```

**Change B — `onActivityResult()` (lines 87-104):**

Pass the projection to `MediaProjectionService` and add error handling:

```kotlin
    @Deprecated("Deprecated in Java")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        @Suppress("DEPRECATION")
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == REQUEST_CODE_SCREEN_RECORD) {
            if (resultCode == RESULT_OK && data != null) {
                try {
                    val mpm = getSystemService(MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
                    val projection = mpm.getMediaProjection(resultCode, data)
                    if (projection != null) {
                        MediaProjectionService.setProjection(projection)
                        // Also set on ScreenRecorder for compatibility
                        ScreenRecorder.setProjection(projection)
                        Toast.makeText(this, "Screen recording permission granted", Toast.LENGTH_SHORT).show()
                    }
                } catch (e: SecurityException) {
                    Toast.makeText(this, "Screen recording: ${e.message}", Toast.LENGTH_LONG).show()
                }
            } else {
                Toast.makeText(this, "Screen recording permission denied", Toast.LENGTH_SHORT).show()
            }
            updatePermissionSwitches()
        }
    }
```

**Also update `updatePermissionSwitches()`:**

```kotlin
        switchScreenRecord.isChecked = MediaProjectionService.hasProjection()
```

**Also add import at top:**
```kotlin
import android.content.pm.ServiceInfo
import android.os.Build
import com.hermesandroid.bridge.media.MediaProjectionService
```

### 4. MODIFY: `app/src/main/kotlin/com/hermesandroid/bridge/media/ScreenRecorder.kt`

Minor change — use `MediaProjectionService` as the projection source instead of its own field:

```kotlin
    fun hasPermission(): Boolean = MediaProjectionService.hasProjection()

    fun setProjection(p: MediaProjection) {
        MediaProjectionService.setProjection(p)
    }

    fun record(durationMs: Long = 5000): Map<String, Any?> {
        val context = (MediaProjectionService.instance ?: BridgeAccessibilityService.instance)?.applicationContext
            ?: return mapOf("success" to false, "message" to "No service running")
        val proj = MediaProjectionService.projection
            ?: return mapOf("success" to false, "message" to "No MediaProjection. Tap 'Grant Screen Recording' in the app first.")
        // ... rest unchanged, use 'context' instead of 'service' where needed
```

## Verification After Build

After Docker build + install:

1. Enable screen recording toggle
2. Accept capture consent dialog
3. Verify no crash
4. Verify notification appears "Screen recording ready"
5. Test `POST /screen_record` through relay
6. Verify accessibility still works
7. Verify relay connection still works

## Files Changed Summary

| File | Action | Lines Changed |
|------|--------|---------------|
| `MediaProjectionService.kt` | CREATE | ~90 lines new |
| `AndroidManifest.xml` | ADD | +6 lines (one `<service>` block) |
| `MainActivity.kt` | MODIFY | ~25 lines changed, ~4 lines added import |
| `ScreenRecorder.kt` | MODIFY | ~10 lines changed |

## What This Does NOT Touch

- BridgeAccessibilityService — unchanged
- BridgeNotificationListener — unchanged
- BridgeApplication — unchanged
- RelayClient — unchanged
- PairingManager — unchanged
- Any XML layouts — unchanged
- Any Python files — unchanged
- Any docs/skills — unchanged
