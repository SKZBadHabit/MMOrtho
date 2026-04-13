# features/mouse.py - Mouse & Autoclicker Feature
# Maus-Funktionen für MMOrtho
import time
from adafruit_hid.mouse import Mouse
from adafruit_hid.consumer_control import ConsumerControl
from adafruit_hid.consumer_control_code import ConsumerControlCode

from config import Timing


class MouseFeature:
    """
    Mouse Feature mit Autoclicker.
    - Mausklicks (Links/Rechts)
    - Scrolling
    - Autoclicker Toggle
    - Media Controls
    """

    def __init__(self, hid_mouse, hid_cc):
        self.mouse = hid_mouse
        self.cc = hid_cc

        # Autoclicker State
        self.autoclicker_on = False
        self._last_autoclick = time.monotonic()
        self._last_toggle = time.monotonic()

        # Mouse Button State (für Hold)
        self.left_held = False
        self.right_held = False

        # Callback für Status-Änderungen
        self.on_autoclicker_change = None

    def left_click(self):
        """Einzelner Linksklick"""
        self.mouse.click(Mouse.LEFT_BUTTON)

    def right_click(self):
        """Einzelner Rechtsklick"""
        self.mouse.click(Mouse.RIGHT_BUTTON)

    def left_press(self):
        """Linke Maustaste gedrückt halten"""
        if not self.left_held:
            self.mouse.press(Mouse.LEFT_BUTTON)
            self.left_held = True

    def left_release(self):
        """Linke Maustaste loslassen"""
        if self.left_held:
            self.mouse.release(Mouse.LEFT_BUTTON)
            self.left_held = False

    def right_press(self):
        """Rechte Maustaste gedrückt halten"""
        if not self.right_held:
            self.mouse.press(Mouse.RIGHT_BUTTON)
            self.right_held = True

    def right_release(self):
        """Rechte Maustaste loslassen"""
        if self.right_held:
            self.mouse.release(Mouse.RIGHT_BUTTON)
            self.right_held = False

    def scroll_up(self):
        """Scroll nach oben"""
        self.mouse.move(wheel=1)

    def scroll_down(self):
        """Scroll nach unten"""
        self.mouse.move(wheel=-1)

    def toggle_autoclicker(self):
        """Schaltet den Autoclicker ein/aus mit Debounce"""
        now = time.monotonic()
        if now - self._last_toggle < Timing.AUTOCLICKER_DEBOUNCE:
            return  # Debounce

        self.autoclicker_on = not self.autoclicker_on
        self._last_toggle = now

        print(f"Autoclicker: {'ON' if self.autoclicker_on else 'OFF'}")

        # Callback aufrufen
        if self.on_autoclicker_change:
            self.on_autoclicker_change(self.autoclicker_on)

    def handle_autoclicker(self):
        """
        Führt Autoclicks aus wenn aktiviert.
        Sollte in der Main-Loop aufgerufen werden.
        """
        if not self.autoclicker_on:
            return

        now = time.monotonic()
        if now - self._last_autoclick >= Timing.AUTOCLICKER_INTERVAL:
            self.mouse.click(Mouse.LEFT_BUTTON)
            self._last_autoclick = now

    # === Media Controls ===

    def mute(self):
        """Mute Toggle"""
        self.cc.send(ConsumerControlCode.MUTE)

    def volume_up(self):
        """Lautstärke erhöhen"""
        self.cc.send(ConsumerControlCode.VOLUME_INCREMENT)

    def volume_down(self):
        """Lautstärke verringern"""
        self.cc.send(ConsumerControlCode.VOLUME_DECREMENT)
