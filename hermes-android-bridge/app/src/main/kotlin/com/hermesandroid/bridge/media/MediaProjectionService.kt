package com.hermesandroid.bridge.media

import android.app.*
import android.content.Intent
import android.content.pm.ServiceInfo
import android.media.projection.MediaProjection
import android.os.Binder
import android.os.Build
import android.os.IBinder

/**
 * Foreground service required by Android 14+ for MediaProjection.
 *
 * Must be running (startForeground with FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION)
 * BEFORE MediaProjectionManager.getMediaProjection() is called.
 *
 * The projection object is held in the companion so ScreenRecorder and
 * ActionExecutor can access it without binding to the service.
 */
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
