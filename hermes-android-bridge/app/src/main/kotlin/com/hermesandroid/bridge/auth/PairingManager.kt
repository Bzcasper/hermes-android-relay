package com.hermesandroid.bridge.auth

import android.content.Context
import android.content.SharedPreferences
import java.security.SecureRandom

/**
 * Per-install pairing credential. A user must configure the same secret on the
 * relay server. The credential is never hardcoded into the APK.
 */
object PairingManager {
    private const val PREFS_NAME = "hermes_bridge_prefs"
    private const val KEY_PAIRING_CODE = "pairing_code"
    private val random = SecureRandom()
    private var prefs: SharedPreferences? = null

    fun init(context: Context) {
        prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        // Old published static credentials are never reused.
        if (prefs?.getString(KEY_PAIRING_CODE, null).isNullOrBlank() ||
            (prefs?.getString(KEY_PAIRING_CODE, null)?.length ?: 0) < 16) {
            regenerateCode()
        }
    }

    private fun newCode(): String {
        val bytes = ByteArray(24)
        random.nextBytes(bytes)
        return bytes.joinToString("") { "%02x".format(it) }
    }

    fun getCode(): String = prefs?.getString(KEY_PAIRING_CODE, null).orEmpty()

    fun regenerateCode(): String {
        val newCode = newCode()
        val storage = prefs ?: error("PairingManager not initialized")
        check(storage.edit().putString(KEY_PAIRING_CODE, newCode).commit()) {
            "Failed to persist pairing credential"
        }
        return newCode
    }

    fun validateToken(authHeader: String?): Boolean {
        if (authHeader?.startsWith("Bearer ") != true) return false
        val expected = getCode().toByteArray(Charsets.UTF_8)
        val actual = authHeader.removePrefix("Bearer ").trim().toByteArray(Charsets.UTF_8)
        return expected.isNotEmpty() && java.security.MessageDigest.isEqual(expected, actual)
    }
}
