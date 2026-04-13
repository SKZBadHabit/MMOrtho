# code.py - MMOrtho Keyboard Main Entry Point
# Modular Firmware for CircuitPython
#
# Version: 5.0
# Hardware: Raspberry Pi Pico2 W (RP2350)
# Author: Michael Mörtenhuber
#
# v5.0 Changes:
#   - Modern Dashboard UI with 3 switchable panels
#   - Redesigned Splash Screen
#   - Performance optimizations in main loop

import asyncio
import time
import traceback
import usb_hid
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.mouse import Mouse
from adafruit_hid.consumer_control import ConsumerControl

# Config & Keymap
from config import KEYBOARD_NAME, CODE_VERSION, WeatherConfig
from keymap import KC

# Features
from features.keyboard import KeyboardEngine
from features.display import DisplayFeature, MODE_NETWORK
from features.storage import StorageFeature
from features.wifi import WiFiFeature
from features.mouse import MouseFeature
from features.power import PowerFeature
from features.webserver import WebServerFeature
from features.macros import MacroEngine


# =============================================================================
# HID SETUP
# =============================================================================

kbd = Keyboard(usb_hid.devices)
hid_mouse = Mouse(usb_hid.devices)
cc = ConsumerControl(usb_hid.devices)


# =============================================================================
# FEATURE INITIALIZATION
# =============================================================================

# Core Features
keyboard = KeyboardEngine(kbd)
display = DisplayFeature()
storage = StorageFeature()

# Optional Features
wifi = WiFiFeature()
mouse = MouseFeature(hid_mouse, cc)
power = PowerFeature(display, storage, wifi)
macro_engine = MacroEngine(kbd, hid_mouse)
webserver = WebServerFeature(wifi, storage, macro_engine)


# =============================================================================
# FEATURE WIRING (Connect Features Together)
# =============================================================================

def on_keypress():
    """Callback bei jedem Tastendruck"""
    storage.increment_keypress()
    power.activity()

    # Display State aktualisieren
    display.set_state("current_keypress", storage.current_keypress)


def on_layer_change(layer, toggled=False):
    """Callback bei Layer-Wechsel"""
    display.update_layer(layer, toggled)


def on_autoclicker_change(enabled):
    """Callback bei Autoclicker Toggle"""
    display.set_state("autoclicker", enabled)


def on_caps_change():
    """Callback bei Caps Lock Toggle"""
    display.update_caps(keyboard.caps_on)


# Wire up Callbacks
keyboard.on_keypress = on_keypress
keyboard.on_layer_change = on_layer_change
mouse.on_autoclicker_change = on_autoclicker_change


# =============================================================================
# CUSTOM KEY HANDLERS
# =============================================================================

def handle_mouse_left():
    """Handler für Mausklick links (Hold)"""
    mouse.left_press()


def handle_mouse_right():
    """Handler für Mausklick rechts (Hold)"""
    mouse.right_press()


def handle_show_stats():
    """Handler für Statistik-Anzeige"""
    storage.force_save()
    wifi.refresh_device_status()
    display.show_statistics(
        storage.alltime_keypress,
        storage.alltime_runtime,
        wifi.get_ip_address()
    )


def handle_display_mode():
    """Handler für Display-Modus Toggle"""
    display.toggle_mode()


def handle_wifi_toggle():
    """Handler für WiFi Toggle"""
    wifi.toggle()
    # Status an Display weitergeben
    status = wifi.get_status_dict()
    for key, value in status.items():
        display.set_state(key, value)


def handle_wifi_setup():
    """Handler für WiFi Setup Wizard (FN+,)"""
    if wifi.setup_active:
        return  # Wizard läuft bereits
    wifi.start_setup()
    keyboard.key_interceptor = wifi.handle_setup_key


def handle_config_mode():
    """
    Handler für FN + Right Shift → Configuration Mode Toggle.
    Im Config Mode zeigt das Display 'Configuration Mode' + IP-Adresse.
    Tastatur arbeitet normal weiter, nur das Display ändert sich.
    Zweiter Druck auf FN + Right Shift kehrt zum normalen Dashboard zurück.

    KEIN wifi.start_ap() hier — AP-Init blockiert 3-10s und friert die
    Tastatur ein. Config Mode setzt WiFi voraus (Setup-Wizard: FN+,).
    """
    if display.config_mode_active:
        # Config Mode beenden
        display.exit_config_mode()
        webserver.stop()
    else:
        # Config Mode aktivieren — nur wenn WiFi verbunden
        ip = wifi.get_ip_address()
        if ip == "Not connected":
            # Kein WiFi → Display-Hinweis aber kein Freeze durch AP-Init
            display.show_config_mode(None)
        else:
            display.show_config_mode(ip)
            webserver.start()


# Register Custom Key Handlers
keyboard.register_handler(KC.MOUSE_LEFT, handle_mouse_left)
keyboard.register_handler(KC.MOUSE_RIGHT, handle_mouse_right)
keyboard.register_handler(KC.MOUSE_WHEEL_UP, mouse.scroll_up)
keyboard.register_handler(KC.MOUSE_WHEEL_DOWN, mouse.scroll_down)
keyboard.register_handler(KC.AUTOCLICKER, mouse.toggle_autoclicker)
keyboard.register_handler(KC.WIFI_TOGGLE, handle_wifi_toggle)
keyboard.register_handler(KC.WIFI_SETUP, handle_wifi_setup)
keyboard.register_handler(KC.DISPLAY_MODE, handle_display_mode)
keyboard.register_handler(KC.SHOW_STATS, handle_show_stats)
keyboard.register_handler(KC.SYSTEM_RESET, storage.save_and_reset)
keyboard.register_handler(KC.CAPS_TOGGLE, on_caps_change)
keyboard.register_handler(KC.MUTE, mouse.mute)
keyboard.register_handler(KC.VOL_DOWN, mouse.volume_down)
keyboard.register_handler(KC.VOL_UP, mouse.volume_up)
keyboard.register_handler("KC_CONFIG_MODE", handle_config_mode)

# Macro Handlers (KC.MACRO_1 .. KC.MACRO_8 → macro IDs 1-8)
keyboard.register_handler(KC.MACRO_1, lambda: macro_engine.execute(1))
keyboard.register_handler(KC.MACRO_2, lambda: macro_engine.execute(2))
keyboard.register_handler(KC.MACRO_3, lambda: macro_engine.execute(3))
keyboard.register_handler(KC.MACRO_4, lambda: macro_engine.execute(4))
keyboard.register_handler(KC.MACRO_5, lambda: macro_engine.execute(5))
keyboard.register_handler(KC.MACRO_6, lambda: macro_engine.execute(6))
keyboard.register_handler(KC.MACRO_7, lambda: macro_engine.execute(7))
keyboard.register_handler(KC.MACRO_8, lambda: macro_engine.execute(8))


# =============================================================================
# DISPLAY STATE SYNC
# =============================================================================

def sync_display_state():
    """Synchronisiert alle State-Werte mit dem Display"""
    display.set_state("cpu_temp", power.get_cpu_temp())
    display.set_state("scan_rate", keyboard.scan_rate)
    display.set_state("autoclicker", mouse.autoclicker_on)
    display.set_state("voltage", power.get_voltage())
    display.set_state("caps_on", keyboard.caps_on)
    display.set_state("current_runtime", storage.get_live_runtime())

    # WiFi Status
    status = wifi.get_status_dict()
    for key, value in status.items():
        display.set_state(key, value)


# =============================================================================
# MAIN LOOP
# =============================================================================

async def main():
    """Haupt-Async-Loop - Optimized for v5.0"""
    print(f"\n{KEYBOARD_NAME} v{CODE_VERSION} starting...")

    # Splash Screen anzeigen
    display.splash_screen()

    # Warten auf Tastendruck
    print("Waiting for keypress...")
    keyboard.wait_for_keypress()

    # Main Screen aktivieren
    display.main_screen()
    sync_display_state()

    # Webserver Task starten
    asyncio.create_task(webserver.run_async())

    print("Keyboard active!")

    # === Timer Initialization ===
    current_time = time.monotonic()
    last_display_update = current_time
    last_runtime_update = current_time
    last_scroll_time = current_time
    last_weather_update = -WeatherConfig.REFRESH_INTERVAL  # Sofort beim ersten Loop holen

    # === Constants (avoid repeated lookups) ===
    SCROLL_REPEAT_INTERVAL = 0.05  # 50ms = 20 scrolls/sec
    DISPLAY_UPDATE_INTERVAL = 30.0
    RUNTIME_UPDATE_INTERVAL = 300.0

    # Cache key strings for faster comparison
    KEY_MOUSE_LEFT = "146"
    KEY_MOUSE_RIGHT = "136"
    KEY_SCROLL_UP = "125"
    KEY_SCROLL_DOWN = "135"

    # Main Loop
    while True:
        # Zeit einmal pro Loop holen (single call per iteration)
        current_time = time.monotonic()

        # === HIGH PRIORITY: Keyboard Processing ===
        keyboard.process()

        # === WiFi Setup Wizard ===
        if wifi.setup_active:
            wifi.update_setup(display)
            # Wizard gerade beendet → aufräumen
            if not wifi.setup_active:
                keyboard.key_interceptor = None
                display.main_screen()
                display.needs_update = True
                for k, v in wifi.get_status_dict().items():
                    display.set_state(k, v)
            continue  # Rest des Loops überspringen während Setup aktiv
        elif keyboard.key_interceptor is not None:
            # Wizard durch ESC-Taste beendet (handle_setup_key setzte _DONE
            # bevor dieser Check läuft → setup_active ist bereits False)
            keyboard.key_interceptor = None
            display.main_screen()
            display.needs_update = True
            for k, v in wifi.get_status_dict().items():
                display.set_state(k, v)

        # === Mouse Release Handling ===
        pressed = keyboard.pressed_keys  # Cache reference
        if mouse.left_held and KEY_MOUSE_LEFT not in pressed:
            mouse.left_release()
        if mouse.right_held and KEY_MOUSE_RIGHT not in pressed:
            mouse.right_release()

        # === Scroll Repeat (Layer 1 only) ===
        if keyboard.current_layer == 1:
            scroll_delta = current_time - last_scroll_time
            if scroll_delta >= SCROLL_REPEAT_INTERVAL:
                if KEY_SCROLL_UP in pressed:
                    mouse.scroll_up()
                    last_scroll_time = current_time
                elif KEY_SCROLL_DOWN in pressed:
                    mouse.scroll_down()
                    last_scroll_time = current_time

        # === Autoclicker ===
        mouse.handle_autoclicker()

        # === Background Tasks ===
        power.check()

        # === Display Updates (throttled) ===
        display_delta = current_time - last_display_update
        if display_delta >= DISPLAY_UPDATE_INTERVAL:
            # Batch state updates to reduce overhead
            display.set_state("cpu_temp", power.get_cpu_temp())
            display.set_state("scan_rate", keyboard.scan_rate)
            display.set_state("voltage", power.get_voltage())

            # WiFi Status (only if enabled)
            if wifi.enabled:
                # HA-Status nur abrufen wenn NET-Tab aktiv (blockierende HTTP-Calls)
                if display.mode == MODE_NETWORK:
                    wifi.refresh_device_status()
                for key, value in wifi.get_status_dict().items():
                    display.set_state(key, value)

            last_display_update = current_time

        # Wetter-Update (alle WeatherConfig.REFRESH_INTERVAL Sekunden, nur wenn WiFi aktiv)
        if wifi.enabled and (current_time - last_weather_update >= WeatherConfig.REFRESH_INTERVAL):
            weather = wifi.fetch_weather()
            if weather:
                display.set_state("weather_temp", weather["temp"])
                display.set_state("weather_hum",  weather["hum"])
                display.set_state("weather_cond", weather["cond"])
                display.set_state("weather_city", weather["city"])
            display.set_state("ntp_synced", wifi.ntp_synced)
            last_weather_update = current_time

        # === Runtime Update (every 5 min) ===
        if current_time - last_runtime_update >= RUNTIME_UPDATE_INTERVAL:
            display.set_state("current_runtime", storage.get_live_runtime())
            last_runtime_update = current_time

        # === Display Refresh ===
        display.refresh()

        # Sleep: 1ms normal, 50ms im Deep Idle (CPU schont sich)
        await asyncio.sleep(power.get_loop_sleep())


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    print("=" * 40)
    print(f"  {KEYBOARD_NAME}")
    print(f"  Firmware v{CODE_VERSION}")
    print("=" * 40)

    # Initial Load
    storage.load()

    # Run Main Loop
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown requested")
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exception(type(e), e, e.__traceback__)
    finally:
        print("Goodbye!")
