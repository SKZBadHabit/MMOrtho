# features/macros.py - Macro Engine for MMOrtho
# Executes user-defined macros: text typing, key combos, mouse clicks, step sequences
import json
import time
from adafruit_hid.keycode import Keycode
from adafruit_hid.mouse import Mouse


MACRO_FILE = "/data/macros.json"

# Maps action name → (button_constant, is_scroll, scroll_direction)
_MOUSE_ACTIONS = {
    "left_click":   (Mouse.LEFT_BUTTON,   False, 0),
    "right_click":  (Mouse.RIGHT_BUTTON,  False, 0),
    "middle_click": (Mouse.MIDDLE_BUTTON, False, 0),
    "scroll_up":    (None,                True,  1),
    "scroll_down":  (None,                True, -1),
}


class MacroEngine:
    """
    Loads macros from /data/macros.json and executes them on demand.

    Macro JSON format:
      [
        {"id": 1, "name": "Hello",      "type": "text",     "content": "Hello World!"},
        {"id": 2, "name": "Save",       "type": "combo",    "keys": ["LEFT_CONTROL","S"]},
        {"id": 3, "name": "Click",      "type": "mouse",    "action": "left_click"},
        {"id": 4, "name": "Seq",        "type": "sequence", "steps": [
          {"type": "text",  "value": "user@example.com"},
          {"type": "delay", "ms": 200},
          {"type": "combo", "keys": ["LEFT_CONTROL","ENTER"]},
          {"type": "mouse", "action": "left_click"}
        ]}
      ]

    Key names in "keys" arrays are Keycode attribute names, e.g. "LEFT_CONTROL", "S".
    Text macros use KeyboardLayoutUS – characters must match the OS keyboard layout.
    Mouse actions: left_click, right_click, middle_click, scroll_up, scroll_down.
    """

    def __init__(self, hid_keyboard, hid_mouse=None):
        self.kbd = hid_keyboard
        self.mouse = hid_mouse        # optional; mouse steps silently skipped if None
        self._layout = None           # lazy-loaded KeyboardLayoutUS
        self.macros = []
        self._load()

    # ── Persistence ──────────────────────────────────────────────────────────

    def _load(self):
        try:
            with open(MACRO_FILE, "r") as f:
                self.macros = json.load(f)
            print(f"Macros: loaded {len(self.macros)} macro(s)")
        except OSError:
            self.macros = []  # file not yet created
        except Exception as e:
            print(f"Macro load error: {e}")
            self.macros = []

    def reload(self):
        """Re-read macros from disk (called after web-config save)."""
        self._load()

    # ── Internals ─────────────────────────────────────────────────────────────

    def _get_layout(self):
        """Lazy-load KeyboardLayoutUS to save memory when unused."""
        if self._layout is None:
            try:
                from adafruit_hid.keyboard_layout_us import KeyboardLayoutUS
                self._layout = KeyboardLayoutUS(self.kbd)
            except Exception as e:
                print(f"Macro: KeyboardLayout unavailable: {e}")
        return self._layout

    @staticmethod
    def _resolve(name):
        """Keycode name string → integer Keycode value, or None if unknown."""
        return getattr(Keycode, name, None)

    def _send_combo(self, keys):
        codes = [self._resolve(k) for k in keys]
        codes = [c for c in codes if c is not None]
        if codes:
            self.kbd.send(*codes)

    def _type_text(self, text):
        layout = self._get_layout()
        if layout and text:
            try:
                layout.write(text)
            except Exception as e:
                print(f"Macro text error: {e}")

    def _do_mouse(self, action, amount=1):
        if self.mouse is None:
            return
        entry = _MOUSE_ACTIONS.get(action)
        if entry is None:
            return
        button, is_scroll, direction = entry
        if is_scroll:
            for _ in range(max(1, amount)):
                self.mouse.move(wheel=direction)
        else:
            self.mouse.click(button)

    # ── Public API ────────────────────────────────────────────────────────────

    def execute(self, macro_id):
        """Execute the macro whose "id" field equals macro_id (int 1-8)."""
        macro = None
        for m in self.macros:
            if m.get("id") == macro_id:
                macro = m
                break
        if macro is None:
            return

        mtype = macro.get("type", "text")

        if mtype == "text":
            self._type_text(macro.get("content", ""))

        elif mtype == "combo":
            self._send_combo(macro.get("keys", []))

        elif mtype == "mouse":
            self._do_mouse(macro.get("action", "left_click"), macro.get("amount", 1))

        elif mtype == "sequence":
            for step in macro.get("steps", []):
                stype = step.get("type")
                if stype == "text":
                    self._type_text(step.get("value", ""))
                elif stype == "combo":
                    self._send_combo(step.get("keys", []))
                elif stype == "mouse":
                    self._do_mouse(step.get("action", "left_click"), step.get("amount", 1))
                elif stype == "delay":
                    ms = max(0, step.get("ms", 100))
                    time.sleep(ms / 1000.0)
