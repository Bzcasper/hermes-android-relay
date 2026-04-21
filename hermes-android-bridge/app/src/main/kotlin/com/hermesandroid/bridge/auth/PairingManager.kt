package com.hermesandroid.bridge.auth

import android.content.Context
import android.content.SharedPreferences

/**
 * Manages the pairing code used to authenticate requests from the Hermes server.
 *
 * On first launch, generates a random 6-character alphanumeric code.
 * The code persists across app restarts. User can regenerate from the UI.
 */
object PairingManager {

    private const val PREFS_NAME = "hermes_bridge_prefs"
    private const val KEY_PAIRING_CODE = "pairing_code"
    private const val CODE_LENGTH = 6

    private var prefs: SharedPreferences? = null
    private var cachedCode: String? = null

    fun init(context: Context) {
        prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        // Generate code on first launch
        if (getCode().isBlank()) {
            regenerateCode()
        }
    }

    fun getCode(): String {
        cachedCode?.let { return it }
        val code = prefs?.getString(KEY_PAIRING_CODE, "") ?: ""
        cachedCode = code
        return code
    }

    fun regenerateCode(): String {
        val chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789" // no 0/O/1/I to avoid confusion
        val code = (1..CODE_LENGTH).map { chars.random() }.joinToString("")
        prefs?.edit()?.putString(KEY_PAIRING_CODE, code)?.apply()
        cachedCode = code
        return code
    }

    /**
     * Validate an incoming request's Authorization header.
     * Expected format: "Bearer <code>"
     */
    fun validateToken(authHeader: String?): Boolean {
        if (authHeader == null) return false
        val token = authHeader.removePrefix("Bearer ").trim()
        return token == getCode()
    }
}
