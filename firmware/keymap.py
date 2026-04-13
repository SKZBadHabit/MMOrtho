# keymap.py - Deklarative Keymap-Definition (QMK-Style keymap.c)
# MMOrtho Keyboard Layout
from adafruit_hid.keycode import Keycode

# === MATRIX KEY NAMES ===
# 5 Zeilen x 12 Spalten Matrix-Layout
MATRIX_KEYS = (
    ("111", "112", "113", "114", "115", "116", "211", "212", "213", "214", "215", "216"),
    ("121", "122", "123", "124", "125", "126", "221", "222", "223", "224", "225", "226"),
    ("131", "132", "133", "134", "135", "136", "231", "232", "233", "234", "235", "236"),
    ("141", "142", "143", "144", "145", "146", "241", "242", "243", "244", "245", "246"),
    ("151", "152", "153", "154", "155", "156", "251", "252", "253", "254", "255", "256"),
)

# === CUSTOM KEYCODES (wie QMK Custom Keycodes) ===
class KC:
    """Custom Keycodes für spezielle Funktionen"""
    # Layer Control
    FN = "KC_FN"                    # Momentary Layer 2 (gedrückt halten)
    LAYER_TOGGLE = "KC_LAYER_TG"    # Toggle Layer permanent

    # Mouse Actions
    MOUSE_LEFT = "KC_MS_L"
    MOUSE_RIGHT = "KC_MS_R"
    MOUSE_WHEEL_UP = "KC_MS_WU"
    MOUSE_WHEEL_DOWN = "KC_MS_WD"

    # Feature Toggles
    AUTOCLICKER = "KC_AUTOCLICKER"
    WIFI_TOGGLE = "KC_WIFI"
    WIFI_SETUP = "KC_WIFI_SETUP"
    DISPLAY_MODE = "KC_DISP_MODE"
    SHOW_STATS = "KC_STATS"
    SYSTEM_RESET = "KC_RESET"
    CAPS_TOGGLE = "KC_CAPS_TG"

    # Media / Consumer Control
    MUTE = "KC_MUTE"
    VOL_DOWN = "KC_VOLD"
    VOL_UP = "KC_VOLU"

    # Tasten die von Extra-Keys in die Matrix gewandert sind
    NON_US_KEY = "KC_NON_US"   # < > | (war E19)
    CARET_KEY = "KC_CARET"     # ^ / ° (war E18)

    # Config Mode
    CONFIG_MODE = "KC_CONFIG_MODE"  # FN + Right Shift → Web Konfigurator

    # Macros (1-8, assignable via Web Configurator)
    MACRO_1 = "KC_MACRO_1"
    MACRO_2 = "KC_MACRO_2"
    MACRO_3 = "KC_MACRO_3"
    MACRO_4 = "KC_MACRO_4"
    MACRO_5 = "KC_MACRO_5"
    MACRO_6 = "KC_MACRO_6"
    MACRO_7 = "KC_MACRO_7"
    MACRO_8 = "KC_MACRO_8"

    # Transparent (inherit from lower layer)
    TRANS = "KC_TRNS"

    # No operation
    NO = "KC_NO"


# === LAYER 0 - BASE LAYER (QWERTZ) ===
LAYER_BASE = {
    # Zeile 1: Zahlenreihe
    "111": Keycode.ESCAPE,
    "112": Keycode.ONE,
    "113": Keycode.TWO,
    "114": Keycode.THREE,
    "115": Keycode.FOUR,
    "116": Keycode.FIVE,
    "211": Keycode.BACKSPACE,
    "212": Keycode.ZERO,
    "213": Keycode.NINE,
    "214": Keycode.EIGHT,
    "215": Keycode.SEVEN,
    "216": Keycode.SIX,

    # Zeile 2: QWERTY
    "121": Keycode.TAB,
    "122": Keycode.Q,
    "123": Keycode.W,
    "124": Keycode.E,
    "125": Keycode.R,
    "126": Keycode.T,
    "221": Keycode.BACKSLASH,
    "222": Keycode.P,
    "223": Keycode.O,
    "224": Keycode.I,
    "225": Keycode.U,
    "226": Keycode.Y,

    # Zeile 3: Home Row
    "131": KC.LAYER_TOGGLE,  # Layer Toggle
    "132": Keycode.A,
    "133": Keycode.S,
    "134": Keycode.D,
    "135": Keycode.F,
    "136": Keycode.G,
    "231": Keycode.QUOTE,
    "232": Keycode.SEMICOLON,
    "233": Keycode.L,
    "234": Keycode.K,
    "235": Keycode.J,
    "236": Keycode.H,

    # Zeile 4: Shift Row
    "141": Keycode.LEFT_SHIFT,
    "142": Keycode.Z,
    "143": Keycode.X,
    "144": Keycode.C,
    "145": Keycode.V,
    "146": Keycode.B,
    "241": Keycode.RIGHT_SHIFT,
    "242": Keycode.FORWARD_SLASH,
    "243": Keycode.PERIOD,
    "244": Keycode.COMMA,
    "245": Keycode.M,
    "246": Keycode.N,

    # Zeile 5: Modifier Row
    "151": Keycode.LEFT_CONTROL,
    "152": Keycode.LEFT_GUI,
    "153": Keycode.LEFT_ALT,
    "154": Keycode.RIGHT_ALT,
    "155": KC.NON_US_KEY,   # < > | (war E19)
    "156": Keycode.SPACE,   # Space (war FN, FN liegt jetzt auf E19)
    "251": Keycode.MINUS,
    "252": Keycode.RIGHT_BRACKET,
    "253": Keycode.LEFT_BRACKET,
    "254": Keycode.EQUALS,
    "255": KC.CARET_KEY,    # ^ / ° (war E18)
    "256": Keycode.ENTER,   # Enter (war Space, Space liegt jetzt auf E18)
}

# === LAYER 1 - FUNCTION LAYER ===
LAYER_FN = {
    # Zeile 1: F-Keys
    "111": Keycode.ESCAPE,
    "112": Keycode.F1,
    "113": Keycode.F2,
    "114": Keycode.F3,
    "115": Keycode.F4,
    "116": Keycode.F5,
    "211": Keycode.BACKSPACE,
    "212": Keycode.F10,
    "213": Keycode.F9,
    "214": Keycode.F8,
    "215": Keycode.F7,
    "216": Keycode.F6,

    # Zeile 2: Navigation
    "121": KC.CAPS_TOGGLE,           # Caps Lock Toggle
    "122": Keycode.Q,
    "123": Keycode.W,
    "124": Keycode.E,
    "125": KC.MOUSE_WHEEL_UP,    # Scroll Up
    "126": Keycode.T,
    "221": Keycode.F11,
    "222": KC.SYSTEM_RESET,      # System Reset
    "223": Keycode.PAGE_DOWN,
    "224": Keycode.UP_ARROW,
    "225": Keycode.PAGE_UP,
    "226": Keycode.INSERT,

    # Zeile 3: Home Row + Mouse
    "131": KC.LAYER_TOGGLE,      # Back to Layer 0
    "132": Keycode.A,
    "133": Keycode.S,
    "134": Keycode.D,
    "135": KC.MOUSE_WHEEL_DOWN,  # Scroll Down
    "136": KC.MOUSE_RIGHT,       # Right Click
    "231": Keycode.F12,
    "232": KC.SHOW_STATS,        # Show Statistics
    "233": Keycode.RIGHT_ARROW,
    "234": Keycode.DOWN_ARROW,
    "235": Keycode.LEFT_ARROW,
    "236": Keycode.HOME,

    # Zeile 4: Features
    "141": Keycode.LEFT_SHIFT,
    "142": KC.AUTOCLICKER,       # Autoclicker Toggle
    "143": Keycode.X,
    "144": Keycode.C,
    "145": Keycode.V,
    "146": KC.MOUSE_LEFT,        # Left Click
    "241": Keycode.RIGHT_SHIFT,    
    "242": KC.WIFI_TOGGLE,       # WiFi Toggle
    "243": KC.DISPLAY_MODE,      # Display Mode Toggle
    "244": KC.WIFI_SETUP,        # WiFi Setup Wizard
    "245": KC.CONFIG_MODE,       # Konfig Mode
    "246": Keycode.END,

    # Zeile 5: Media + Modifier
    "151": Keycode.LEFT_CONTROL,
    "152": Keycode.LEFT_GUI,
    "153": Keycode.LEFT_ALT,
    "154": Keycode.RIGHT_ALT,
    "155": KC.NON_US_KEY,        # < > | (war E19)
    "156": Keycode.SPACE,        # Space (war FN)
    "251": Keycode.DELETE,
    "252": KC.VOL_UP,            # Volume Up
    "253": KC.VOL_DOWN,          # Volume Down
    "254": KC.MUTE,              # Mute
    "255": KC.CARET_KEY,         # ^ / ° (war E18)
    "256": Keycode.ENTER,        # Enter (war Space)
}

# === EXTRA KEYS (außerhalb der Matrix) ===
EXTRA_KEYS_CONFIG = {
    "E18": {
        "normal": Keycode.SPACE,            # Space
    },
    "E19": {
        "normal": KC.FN,                    # FN (Momentary Layer)
    },
}

# === LAYER STACK ===
LAYERS = [LAYER_BASE, LAYER_FN]

# === LAYER NAMES (für Display) ===
LAYER_NAMES = ["Base", "FN"]
