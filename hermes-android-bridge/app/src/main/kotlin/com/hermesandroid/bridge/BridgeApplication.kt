package com.hermesandroid.bridge

import android.app.Application
import com.hermesandroid.bridge.auth.PairingManager
import com.hermesandroid.bridge.client.RelayClient
import com.hermesandroid.bridge.power.WakeLockManager

class BridgeApplication : Application() {
  override fun onCreate() {
    super.onCreate()
    PairingManager.init(applicationContext)
    WakeLockManager.init(applicationContext)
    // BridgeServer.start(port = 8765) // DISABLED — no localhost server needed; all comms go through RelayClient

    // Initialize relay client and auto-connect if previously configured
    RelayClient.init(applicationContext)
    RelayClient.autoConnect()
  }
}