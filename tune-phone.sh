#!/bin/bash
# Hermes Phone Tuning Script
# Run from Linux desktop via ADB on Samsung Galaxy A24 (SM-A245M)
# Purpose: Make Termux survive Samsung's aggressive battery killing

set -e
ADB="/tmp/platform-tools/adb"
PHONE_SERIAL="${1:-R58W402BE4E}"

echo "============================================"
echo "HERMES PHONE TUNING - Samsung Galaxy A24"
echo "Serial: $PHONE_SERIAL"
echo "============================================"

adb_cmd() {
    $ADB -s $PHONE_SERIAL shell "$@"
}

# ─── SECTION 1: BATTERY OPTIMIZATION ──────────────────────────────

echo ""
echo "=== SECTION 1: Battery Optimization ==="

echo "[1/8] Disabling battery optimization for Termux..."
adb_cmd "dumpsys deviceidle whitelist +com.termux" 2>/dev/null || true
adb_cmd "settings put global app_standby_enabled 0" 2>/dev/null || true

echo "[2/8] Disabling battery optimization for Termux:Boot..."
adb_cmd "dumpsys deviceidle whitelist +com.termux.boot" 2>/dev/null || true

echo "[3/8] Disabling battery optimization for Hermes Bridge..."
adb_cmd "dumpsys deviceidle whitelist +com.aitoolpool.hermesbridge" 2>/dev/null || true

echo "[4/8] Removing Termux from Samsung sleeping apps..."
# Samsung-specific: remove from "sleeping apps" list
adb_cmd "settings put global sleeping_apps_com.termux 0" 2>/dev/null || true
adb_cmd "settings put global deep_sleeping_apps_com.termux 0" 2>/dev/null || true
adb_cmd "settings put global unused_apps_com.termux 0" 2>/dev/null || true

echo "[5/8] Removing Termux:Boot from Samsung sleeping apps..."
adb_cmd "settings put global sleeping_apps_com.termux.boot 0" 2>/dev/null || true
adb_cmd "settings put global deep_sleeping_apps_com.termux.boot 0" 2>/dev/null || true

echo "[6/8] Removing Hermes Bridge from Samsung sleeping apps..."
adb_cmd "settings put global sleeping_apps_com.aitoolpool.hermesbridge 0" 2>/dev/null || true
adb_cmd "settings put global deep_sleeping_apps_com.aitoolpool.hermesbridge 0" 2>/dev/null || true

echo "[7/8] Setting background process limit to maximum..."
adb_cmd "settings put global always_finish_activities 0"
adb_cmd "settings put global background_process_limit -1" 2>/dev/null || true

echo "[8/8] Disabling Samsung app power monitoring..."
adb_cmd "settings put global app_power_monitoring_enabled 0" 2>/dev/null || true

# ─── SECTION 2: DEVELOPER OPTIONS ─────────────────────────────────

echo ""
echo "=== SECTION 2: Developer Options ==="

echo "Ensuring USB debugging stays on..."
adb_cmd "settings put global adb_enabled 1"

echo "Setting stay awake while charging..."
adb_cmd "settings put global stay_on_while_plugged_in 3" 2>/dev/null || true

# ─── SECTION 3: TERMUX CONFIG ─────────────────────────────────────

echo ""
echo "=== SECTION 3: Termux Configuration ==="

echo "Checking termux.properties..."
PROP_CHECK=$(adb_cmd "run-as com.termux cat /data/data/com.termux/files/home/.termux/termux.properties" 2>/dev/null || echo "NOT_FOUND")

if [ "$PROP_CHECK" = "NOT_FOUND" ]; then
    echo "Creating termux.properties..."
    adb_cmd "run-as com.termux bash -c 'cat > /data/data/com.termux/files/home/.termux/termux.properties << \"PROPEOF\"
allow-external-apps = true
default-working-directory = /data/data/com.termux/files/home
disable-terminal-session-change-toast = true
terminal-transcript-rows = 5000
back-key = escape
enforce-char-based-input = true
PROPEOF'"
    echo "  Created."
else
    echo "  Already exists."
    if echo "$PROP_CHECK" | grep -q "allow-external-apps"; then
        echo "  allow-external-apps: present"
    else
        echo "  WARNING: allow-external-apps not set!"
    fi
fi

# ─── SECTION 4: VERIFY CONNECTION ─────────────────────────────────

echo ""
echo "=== SECTION 4: Verification ==="

echo "Phone model: $(adb_cmd getprop ro.product.model)"
echo "Android: $(adb_cmd getprop ro.build.version.release)"
echo "Battery level: $(adb_cmd shell dumpsys battery | grep level | awk '{print $2}')%"
echo "USB powered: $(adb_cmd shell dumpsys battery | grep 'USB powered' | awk '{print $3}')"

echo ""
echo "Whitelisted apps:"
adb_cmd "dumpsys deviceidle whitelist" 2>/dev/null | grep -E "termux|hermes|bridge" || echo "  (could not read whitelist)"

echo ""
echo "Running Termux processes:"
adb_cmd "ps -A" | grep -i termux | awk '{print "  " $0}'

echo ""
echo "============================================"
echo "PHONE TUNING COMPLETE"
echo "============================================"
echo ""
echo "NEXT STEPS:"
echo "1. On phone: Settings → Battery → set to 'Unrestricted' for Termux and Termux:Boot"
echo "2. On phone: Settings → Apps → Termux → Battery → 'Unrestricted'"
echo "3. On phone: Settings → Apps → Termux:Boot → Battery → 'Unrestricted'"
echo "4. On phone: Settings → Apps → Hermes Bridge → Battery → 'Unrestricted'"
echo "5. On phone: Settings → Battery → Background usage limits → Remove Termux from sleeping/deep sleeping apps"
echo ""
echo "NOTE: Some Samsung settings cannot be changed via ADB."
echo "You must manually verify battery settings on the phone."
