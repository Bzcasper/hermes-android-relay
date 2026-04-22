package com.hermesandroid.bridge.auth

import android.content.Context
import android.content.SharedPreferences

/**
 * Manages the pairing code used to authenticate requests from the Hermes server.
 *
 * LOCKED at 86NHU2 — no random generation. This ensures the bridge app always
 * uses the same code the Render relay expects, preventing restart loops.
 */
object PairingManager {

    private const val PREFS_NAME = "hermes_bridge_prefs"
    private const val KEY_PAIRING_CODE = "pairing_code"

    /** The locked pairing code. Must match PAIRING_CODE on the Render relay. */
    const val LOCKED_CODE = "86NHU2"

    private var prefs: SharedPreferences? = null

    fun init(context: Context) {
        prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        // Always force the locked code — overwrites any stale/random code
        prefs?.edit()?.putString(KEY_PAIRING_CODE, LOCKED_CODE)?.apply()
    }

    fun getCode(): String = LOCKED_CODE

    /**
     * Regenerate is a no-op now — code is locked.
     * Returns the locked code for UI display.
     */
    fun regenerateCode(): String = LOCKED_CODE

    /**
     * Validate an incoming request's Authorization header.
     * Expected format: "Bearer <code>"
     */
    fun validateToken(authHeader: String?): Boolean {
        if (authHeader == null) return false
        val token = authHeader.removePrefix("Bearer ").trim()
        return token == LOCKED_CODE
    }
}
