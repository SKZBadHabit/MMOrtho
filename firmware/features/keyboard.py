# features/keyboard.py - Keyboard Matrix Scanning & Key Processing
# QMK-Style Keyboard Engine
import time
import digitalio
import adafruit_matrixkeypad
from adafruit_hid.keycode import Keycode

from config import MATRIX_COLS, MATRIX_ROWS, EXTRA_KEYS, Timing
from keymap import LAYERS, MATRIX_KEYS, KC, EXTRA_KEYS_CONFIG


class KeyboardEngine:
    """
    Zentrale Keyboard-Engine für Matrix-Scanning und Key-Processing.
    Inspiriert von QMK's quantum/matrix.c und process_record.
    """

    def __init__(self, hid_keyboard):
        self.kbd = hid_keyboard
        self.current_layer = 0
        self.fn_active = False
        self.pressed_keys = set()
        self.last_scan_time = time.monotonic()

        # Modifier Tracking
        self.shift_active = False
        self.altgr_active = False
        self.caps_on = False
        self.layer_toggled = False  # True wenn Layer per Toggle gewechselt wurde

        # Scan Rate Tracking
        self._scan_count = 0
        self._scan_rate_time = time.monotonic()
        self._scan_rate = 0  # Scans pro Sekunde

        # Custom Key Handlers (registriert von außen)
        self.handlers = {}

        # Key Interceptor (z.B. für WiFi Setup Wizard)
        # Wenn gesetzt: fn(key_str, base_action, shift_active) → alle Keys werden
        # an diesen Callback weitergeleitet, keine HID-Events gesendet.
        self.key_interceptor = None

        # Callbacks für Events
        self.on_keypress = None  # Callback bei jedem Tastendruck
        self.on_layer_change = None  # Callback bei Layer-Wechsel

        # Hardware Init
        self._init_matrix()
        self._init_extra_keys()
        self._init_non_us_keycode()

    def _init_matrix(self):
        """Initialisiert die Tastatur-Matrix"""
        try:
            # Columns als Output
            self.cols = []
            for pin in MATRIX_COLS:
                col = digitalio.DigitalInOut(pin)
                col.direction = digitalio.Direction.OUTPUT
                self.cols.append(col)

            # Rows als Input mit Pull-Down
            self.rows = []
            for pin in MATRIX_ROWS:
                row = digitalio.DigitalInOut(pin)
                row.direction = digitalio.Direction.INPUT
                row.pull = digitalio.Pull.DOWN
                self.rows.append(row)

            # Matrix Keypad erstellen
            self.keypad = adafruit_matrixkeypad.Matrix_Keypad(
                self.rows, self.cols, MATRIX_KEYS
            )
        except Exception as e:
            print(f"Matrix Init Error: {e}")
            raise  # Kritischer Fehler – Keyboard nicht nutzbar ohne Matrix

    def _init_extra_keys(self):
        """Initialisiert Extra-Keys außerhalb der Matrix"""
        self.extra_switches = {}
        for key_name, pin in EXTRA_KEYS.items():
            try:
                switch = digitalio.DigitalInOut(pin)
                switch.direction = digitalio.Direction.INPUT
                switch.pull = digitalio.Pull.UP
                self.extra_switches[key_name] = switch
            except Exception as e:
                print(f"Extra Key Init Error ({key_name}): {e}")

    def _init_non_us_keycode(self):
        """Initialisiert NON_US Keycode mit Fallback"""
        try:
            self.non_us = Keycode.NON_US_BACKSLASH
        except AttributeError:
            try:
                self.non_us = Keycode.NON_US_HASH
            except AttributeError:
                self.non_us = 0x64

    def register_handler(self, key_code, handler_fn):
        """
        Registriert einen Handler für Custom Keycodes.

        Args:
            key_code: Der Custom Keycode (z.B. KC.WIFI_TOGGLE)
            handler_fn: Die aufzurufende Funktion
        """
        self.handlers[key_code] = handler_fn

    def process(self):
        """
        Hauptfunktion - scannt Matrix und verarbeitet Keys.
        Sollte in der Main-Loop aufgerufen werden.
        """
        current_time = time.monotonic()

        # Debounce Check
        if current_time - self.last_scan_time < Timing.DEBOUNCE:
            return

        # Matrix scannen
        matrix_keys = [str(k) for k in self.keypad.pressed_keys]

        # Extra Keys scannen
        extra_keys = []
        for key_name, switch in self.extra_switches.items():
            if not switch.value:  # Pull-Up, also LOW = gedrückt
                extra_keys.append(key_name)

        all_keys = matrix_keys + extra_keys

        # Process Presses (Callback wird dort nur bei NEUEN Keys aufgerufen)
        self._process_presses(all_keys)

        # Process Releases
        self._process_releases(all_keys)

        self.last_scan_time = current_time

        # Scan Rate berechnen (alle 1 Sekunde aktualisieren)
        self._scan_count += 1
        if current_time - self._scan_rate_time >= 1.0:
            self._scan_rate = self._scan_count
            self._scan_count = 0
            self._scan_rate_time = current_time

    def _process_presses(self, current_keys):
        """Verarbeitet neue Tastendrücke"""
        for key in current_keys:
            if key in self.pressed_keys:
                continue  # Bereits gedrückt

            # Keypress Callback NUR bei neuem Tastendruck (nicht bei gehalten)
            if self.on_keypress:
                self.on_keypress()

            # Extra Keys haben spezielle Behandlung
            if key in EXTRA_KEYS_CONFIG:
                self._handle_extra_key_press(key)
                self.pressed_keys.add(key)
                continue

            # Layer bestimmen und Keycode holen
            keymap = LAYERS[self.current_layer]
            if key not in keymap:
                continue

            action = keymap[key]
            self.pressed_keys.add(key)

            # === Key Interceptor (WiFi Setup Mode) ===
            if self.key_interceptor is not None:
                # Modifier-Tracking läuft weiter (für Shift/AltGr in Passworteingabe)
                if isinstance(action, int):
                    self._track_modifier_press(action)
                # Immer Base-Layer-Action weitergeben für Zeichenlookup
                base_action = LAYERS[0].get(key)
                self.key_interceptor(key, base_action, self.shift_active)
                continue

            # Custom Keycode?
            if isinstance(action, str):
                self._handle_custom_key(key, action)
            # Standard Keycode
            elif isinstance(action, int):
                self._track_modifier_press(action)
                self.kbd.press(action)

    def _process_releases(self, current_keys):
        """Verarbeitet Tastenfreigaben"""
        for key in list(self.pressed_keys):
            if key in current_keys:
                continue  # Noch gedrückt

            # Extra Keys
            if key in EXTRA_KEYS_CONFIG:
                # E19 ist FN → Layer zurücksetzen bei Release
                if key == "E19" and self.fn_active:
                    self.fn_active = False
                    if not self.layer_toggled:
                        self._set_layer(0, toggled=False)
                    self.kbd.release_all()
                self.pressed_keys.remove(key)
                continue

            # === Key Interceptor: nur Modifier-Release tracken, kein HID ===
            if self.key_interceptor is not None:
                base_action = LAYERS[0].get(key)
                if base_action is not None and isinstance(base_action, int):
                    self._track_modifier_release(base_action)
                self.pressed_keys.remove(key)
                continue

            # FN auf Matrix-Key (generisch, z.B. v1: FN auf Key 156)
            if self.fn_active and LAYERS[0].get(key) == KC.FN:
                self.fn_active = False
                if not self.layer_toggled:
                    self._set_layer(0, toggled=False)
                self.kbd.release_all()
                self.pressed_keys.remove(key)
                continue

            # Standard Key Release
            keymap = LAYERS[self.current_layer]
            if key in keymap:
                action = keymap[key]
                if isinstance(action, int):
                    self._track_modifier_release(action)
                    self.kbd.release(action)

            self.pressed_keys.remove(key)

    def _handle_extra_key_press(self, key):
        """Behandelt Extra-Key Drücke (E18=Space, E19=FN)"""

        if key == "E19":
            # FN Key (Momentary Layer)
            if not self.fn_active:
                self.fn_active = True
                self._set_layer(1, toggled=False)

        elif key == "E18":
            # Space
            self.kbd.send(Keycode.SPACE)

    def _handle_custom_key(self, key, action):
        """Behandelt Custom Keycodes"""
        # < > | Taste (war E19, jetzt auf Matrix-Key 155)
        if action == KC.NON_US_KEY:
            if self.altgr_active:
                self.kbd.send(Keycode.RIGHT_ALT, self.non_us)
            elif self.shift_active:
                self.kbd.send(Keycode.SHIFT, self.non_us)
            else:
                self.kbd.send(self.non_us)

        # ^ / ° Taste (war E18, jetzt auf Matrix-Key 255)
        elif action == KC.CARET_KEY:
            if self.shift_active:
                self.kbd.send(Keycode.SHIFT, Keycode.GRAVE_ACCENT)
            else:
                self.kbd.send(Keycode.GRAVE_ACCENT)

        # Config Mode (FN + Right Shift)
        elif action == KC.CONFIG_MODE:
            handler = self.handlers.get("KC_CONFIG_MODE")
            if handler:
                handler()

        # FN Key (Momentary Layer) – Matrix-Fallback falls nötig
        elif action == KC.FN:
            if not self.fn_active:
                self.fn_active = True
                self._set_layer(1, toggled=False)

        # Layer Toggle
        elif action == KC.LAYER_TOGGLE:
            new_layer = 0 if self.current_layer == 1 else 1
            self.layer_toggled = (new_layer == 1)
            self._set_layer(new_layer, toggled=self.layer_toggled)

        # Caps Lock Toggle (intern verwaltet)
        elif action == KC.CAPS_TOGGLE:
            self.caps_on = not self.caps_on
            self.kbd.press(Keycode.CAPS_LOCK)
            # Handler aufrufen falls registriert
            if action in self.handlers:
                self.handlers[action]()

        # External Handler
        elif action in self.handlers:
            self.handlers[action]()

    def _set_layer(self, layer, toggled=None):
        """Wechselt den aktiven Layer"""
        if layer != self.current_layer:
            self.current_layer = layer
            if toggled is not None:
                self.layer_toggled = toggled
            if self.on_layer_change:
                self.on_layer_change(layer, self.layer_toggled)

    def _track_modifier_press(self, keycode):
        """Trackt Modifier-Tastendrücke"""
        if keycode in (Keycode.LEFT_SHIFT, Keycode.RIGHT_SHIFT):
            self.shift_active = True
        elif keycode == Keycode.RIGHT_ALT:
            self.altgr_active = True

    def _track_modifier_release(self, keycode):
        """Trackt Modifier-Freigaben"""
        if keycode in (Keycode.LEFT_SHIFT, Keycode.RIGHT_SHIFT):
            self.shift_active = False
        elif keycode == Keycode.RIGHT_ALT:
            self.altgr_active = False

    def wait_for_keypress(self):
        """
        Blockiert bis eine Taste gedrückt wird.
        Nützlich für Splash-Screen.
        """
        while True:
            matrix_keys = self.keypad.pressed_keys
            for switch in self.extra_switches.values():
                if not switch.value:
                    return True
            if matrix_keys:
                return True
            time.sleep(0.01)

    @property
    def layer(self):
        """Gibt den aktuellen Layer zurück"""
        return self.current_layer

    @property
    def scan_rate(self):
        """Gibt die aktuelle Scan-Rate zurück (Scans pro Sekunde)"""
        return self._scan_rate
