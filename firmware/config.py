# config.py - Hardware & Timing Konfiguration (QMK-Style config.h)
# MMOrtho Keyboard Configuration
import board

# === KEYBOARD INFO ===
KEYBOARD_NAME = "MMOrtho"
MODEL_NUMBER = "4-01"
CODE_VERSION = "7.1"

# === MATRIX PINS ===
# Spalten (Columns) - Output
MATRIX_COLS = [
    board.GP21, board.GP20, board.GP19, board.GP18, board.GP17, board.GP16,
    board.GP10, board.GP11, board.GP12, board.GP13, board.GP14, board.GP15
]

# Zeilen (Rows) - Input mit Pull-Down
MATRIX_ROWS = [board.GP0, board.GP1, board.GP2, board.GP3, board.GP4]

# === EXTRA KEYS (außerhalb der Matrix) ===
EXTRA_KEYS = {
    "E18": board.GP9,   # ^ / ° Taste (rechts)
    "E19": board.GP22,  # < > | Taste (links)
}

# === DISPLAY I2C ===
DISPLAY_SDA = board.GP26
DISPLAY_SCL = board.GP27
DISPLAY_I2C_ADDRESS = 0x3C
DISPLAY_WIDTH = 128
DISPLAY_HEIGHT = 64

# === TIMING (in Sekunden) ===
class Timing:
    DEBOUNCE = 0.009              # 9ms Debounce für stabile Erkennung
    ENERGY_SAVE_TIMEOUT = 210     # Display aus nach 210s Inaktivität
    DEEP_IDLE_TIMEOUT = 1800      # Deep Idle nach 30min (WiFi aus, Loop 50ms)
    GC_INTERVAL = 910             # Garbage Collection alle 910s
    DISPLAY_REFRESH = 61          # Display-Refresh alle 61s
    AUTOCLICKER_INTERVAL = 0.01   # 10ms = 100 Klicks/Sekunde
    AUTOCLICKER_DEBOUNCE = 0.3    # 300ms Toggle-Debounce
    VOLTAGE_REFRESH = 5           # Spannung alle 5s messen

# === STORAGE PATHS ===
class Storage:
    DATA_DIR = "/data"
    STATS_FILE = "/data/stats.json"

    # Legacy-Dateien für Migration (werden nicht mehr verwendet)
    RUNTIME_FILE_LEGACY = "/runtime.txt"
    KEYPRESS_FILE_LEGACY = "/keypress.txt"

# === WIFI / HOME ASSISTANT ===
class HomeAssistant:
    URL = "http://YOUR_HA_IP:8123"                   # e.g. "http://192.168.1.100:8123"
    TOKEN = "YOUR_LONG_LIVED_ACCESS_TOKEN"           # HA Profile → Long-Lived Access Tokens
    ENTITIES = {
        # Map a short name to a Home Assistant entity_id
        # These are shown on the NET display tab
        # "laser": "switch.lasercutter",
        # "printer_3d": "switch.3d_strom",
    }

class WeatherConfig:
    """Wetter und NTP Konfiguration"""
    CITY = "Vienna"                  # Stadt fuer wttr.in Abfrage
    ENABLED = True                  # False = kein Wetter-Fetch
    REFRESH_INTERVAL = 600          # Sekunden zwischen Wetter-Updates (10 min)
    NTP_TZ_OFFSET = 1               # Zeitzone: 1 = CET (Oesterreich/Deutschland)

# === WIFI EINSTELLUNGEN ===
class WiFiConfig:
    # Kein Fallback-Netzwerk – Verbindung nur über gespeicherte Credentials
    # (via Setup-Wizard verbinden, wird in /data/wifi.json gespeichert)
    XOR_KEY = 42  # Schlüssel für XOR+Base64-Obfuskierung der gespeicherten Credentials
