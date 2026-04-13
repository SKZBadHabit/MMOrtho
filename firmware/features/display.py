# features/display.py - OLED Display Feature v5.1
# Retro Terminal UI System for MMOrtho
import time
import displayio
import terminalio
import busio
from adafruit_display_text import label
from adafruit_display_shapes.rect import Rect
from adafruit_display_shapes.line import Line
import adafruit_displayio_ssd1306

from config import (
    DISPLAY_SDA, DISPLAY_SCL, DISPLAY_I2C_ADDRESS,
    DISPLAY_WIDTH, DISPLAY_HEIGHT,
    KEYBOARD_NAME, MODEL_NUMBER, CODE_VERSION, Timing
)


# =============================================================================
# DISPLAY CONSTANTS
# =============================================================================

# Character dimensions (terminalio.FONT = 6x8)
CHAR_W = 6
CHAR_H = 8

# Layout - Terminal Grid (21 chars x 8 lines)
MARGIN = 2
LINE_Y = [2, 12, 22, 32, 42, 52, 62]  # Y positions for 7 text lines

# Dashboard Modes
MODE_STATUS = 0
MODE_SYSTEM = 1
MODE_NETWORK = 2
MODE_WEATHER = 3
MODE_COUNT = 4

# Box Drawing Characters (ASCII fallback for compatibility)
BOX_H = "-"      # Horizontal
BOX_V = "|"      # Vertical
BOX_TL = "+"     # Top Left
BOX_TR = "+"     # Top Right
BOX_BL = "+"     # Bottom Left
BOX_BR = "+"     # Bottom Right
BOX_T = "+"      # T-junction
BOX_CROSS = "+"  # Cross


class DisplayFeature:
    """
    OLED Display Feature v5.1 - Dashboard Bars UI

    Design:
    - Modern metric bars for system values
    - Clean separator lines
    - Status indicator footer
    - Minimal, monitoring-style aesthetic
    """

    def __init__(self):
        self.display = None
        self.mode = MODE_STATUS
        self.is_on = True
        self.needs_update = True
        self.blink_state = False
        self.last_blink = 0

        # Display Groups
        self._main_group = None
        self._frame_group = None
        self._tab_group = None
        self._content_group = None

        # Labels
        self._tab_labels = []
        self._header_label = None
        self._content_labels = {}
        self._cursor_label = None

        # State Dictionary
        self.state = {
            "current_layer": 0,
            "layer_toggled": False,
            "caps_on": False,
            "autoclicker": False,
            "current_keypress": 0,
            "current_runtime": 0,
            "cpu_temp": 0,
            "voltage": "0.0V",
            "scan_rate": 0,
            "wifi_status": "OFF",
            "d3_status": "---",
            "lc_status": "---",
            "weather_temp": "--",
            "weather_hum":  "--",
            "weather_cond": "------",
            "weather_city": "------",
            "ntp_synced":   False,
            "notifications": 0,
        }

        self.last_refresh = time.monotonic()
        self._last_wtr_minute = -1

        # Configuration Mode State
        self.config_mode_active = False
        self._config_group = None

        self._init_display()

    def _init_display(self):
        """Initialize OLED Display"""
        try:
            displayio.release_displays()
            i2c = busio.I2C(DISPLAY_SCL, DISPLAY_SDA)

            from i2cdisplaybus import I2CDisplayBus
            display_bus = I2CDisplayBus(i2c, device_address=DISPLAY_I2C_ADDRESS)

            self.display = adafruit_displayio_ssd1306.SSD1306(
                display_bus,
                width=DISPLAY_WIDTH,
                height=DISPLAY_HEIGHT
            )
        except Exception as e:
            print(f"Display Init Error: {e}")
            self.display = None

    # =========================================================================
    # HELPER: Draw Box Frame
    # =========================================================================

    def _draw_box(self, group, x, y, w, h):
        """Draws ASCII box frame using lines"""
        # Top line
        top = Line(x, y, x + w, y, color=0xFFFFFF)
        group.append(top)
        # Bottom line
        bot = Line(x, y + h, x + w, y + h, color=0xFFFFFF)
        group.append(bot)
        # Left line
        left = Line(x, y, x, y + h, color=0xFFFFFF)
        group.append(left)
        # Right line
        right = Line(x + w, y, x + w, y + h, color=0xFFFFFF)
        group.append(right)

    # =========================================================================
    # SPLASH SCREEN - Retro Boot Sequence
    # =========================================================================

    def splash_screen(self):
        """Retro terminal boot splash"""
        if not self.display:
            return

        splash = displayio.Group()

        # Terminal header
        header = label.Label(
            terminalio.FONT,
            text="[ SYSTEM BOOT ]",
            color=0xFFFFFF
        )
        header.anchor_point = (0.5, 0)
        header.anchored_position = (DISPLAY_WIDTH // 2, 7)
        splash.append(header)

        # Keyboard name - big blocky style
        name = label.Label(
            terminalio.FONT,
            text=f">> {KEYBOARD_NAME.upper()} <<",
            color=0xFFFFFF,
            scale=1
        )
        name.anchor_point = (0.5, 0.5)
        name.anchored_position = (DISPLAY_WIDTH // 2, 25)
        splash.append(name)

        # Version info line
        ver_line = label.Label(
            terminalio.FONT,
            text=f"VER:{CODE_VERSION}  MTN:{MODEL_NUMBER}",
            color=0xFFFFFF
        )
        ver_line.anchor_point = (0.5, 0)
        ver_line.anchored_position = (DISPLAY_WIDTH // 2, 35)
        splash.append(ver_line)

        # Separator
        sep = Line(10, 46, DISPLAY_WIDTH - 10, 46, color=0xFFFFFF)
        splash.append(sep)

        # Boot prompt with blinking cursor style
        prompt = label.Label(
            terminalio.FONT,
            text="> PRESS ANY KEY_",
            color=0xFFFFFF
        )
        prompt.anchor_point = (0.5, 0)
        prompt.anchored_position = (DISPLAY_WIDTH // 2, 51)
        splash.append(prompt)

        self.display.root_group = splash

    # =========================================================================
    # MAIN SCREEN - Terminal Dashboard
    # =========================================================================

    def main_screen(self):
        """Initialize terminal-style dashboard"""
        if not self.display:
            return

        self._main_group = displayio.Group()
        self._frame_group = displayio.Group()
        self._tab_group = displayio.Group()
        self._content_group = displayio.Group()

        # Build frame
        self._build_frame()

        # Build tab bar
        self._build_tabs()

        # Build content
        self._build_content()

        # Assemble groups
        self._main_group.append(self._frame_group)
        self._main_group.append(self._tab_group)
        self._main_group.append(self._content_group)

        self.display.root_group = self._main_group
        self.needs_update = True

    def _build_frame(self):
        """Build terminal frame"""
        # Tab separator line (below tabs)
        tab_sep = Line(0, 11, DISPLAY_WIDTH, 11, color=0xFFFFFF)
        self._frame_group.append(tab_sep)

    def _build_tabs(self):
        """Build tab bar with mode indicators"""
        # Clear existing
        while len(self._tab_group) > 0:
            self._tab_group.pop()
        self._tab_labels = []

        tab_names = ["STS", "SYS", "NET", "WTR"]
        tab_width = 26  # 4 Tabs * 26px = 104px < 128px; Platz für Layer-Indikator
        start_x = 3

        for i, name in enumerate(tab_names):
            x = start_x + (i * tab_width)
            is_active = (i == self.mode)

            # Aktiver Tab: Inverse Video (schwarzer Text auf weißem Hintergrund)
            # padding_left=1 auf ALLEN Tabs: beim aktiven hebt es die linke
            # Pixelreihe sauber mit aus. Auf inaktiven Tabs (background=None)
            # hat es keinen visuellen Effekt.
            tab_lbl = label.Label(
                terminalio.FONT,
                text=name,
                color=0x000000 if is_active else 0xFFFFFF,
                background_color=0xFFFFFF if is_active else None,
                padding_left=1,
                x=x,
                y=6
            )
            self._tab_group.append(tab_lbl)
            self._tab_labels.append(tab_lbl)

        # Layer indicator on right side (4 Zeichen "L:2+" = 24px)
        layer = self.state.get("current_layer", 0)
        toggled = self.state.get("layer_toggled", False)
        layer_text = self._format_layer(layer, toggled)

        self._header_label = label.Label(
            terminalio.FONT,
            text=layer_text,
            color=0xFFFFFF,
            x=DISPLAY_WIDTH - 24,
            y=6
        )
        self._tab_group.append(self._header_label)

    def _build_content(self):
        """Build content based on current mode"""
        while len(self._content_group) > 0:
            self._content_group.pop()
        self._content_labels = {}

        if self.mode == MODE_STATUS:
            self._build_status_terminal()
        elif self.mode == MODE_SYSTEM:
            self._build_system_terminal()
        elif self.mode == MODE_NETWORK:
            self._build_network_terminal()
        elif self.mode == MODE_WEATHER:
            self._build_weather_terminal()

    def _build_status_terminal(self):
        """Status panel - terminal style"""
        y = 19

        # Line 1: Keypress with prompt
        self._add_line("KEYS >", "current_keypress", y,
                       formatter=lambda v: f"{v:,}".replace(",", "."))
        y += 11

        # Line 2: Runtime
        self._add_line("RUN  >", "current_runtime", y,
                       formatter=lambda v: f"{v}min")
        y += 11

        # Line 3: Caps Lock status
        caps = self.state.get("caps_on", False)
        caps_text = "CAPS:[ON!]" if caps else "CAPS:[OFF]"
        self._content_labels["caps_line"] = label.Label(
            terminalio.FONT,
            text=caps_text,
            color=0xFFFFFF,
            x=4,
            y=y
        )
        self._content_group.append(self._content_labels["caps_line"])

        # Autoclicker on same line
        ac = self.state.get("autoclicker", False)
        ac_text = "AC:[ON!]" if ac else "AC:[OFF]"
        self._content_labels["ac_line"] = label.Label(
            terminalio.FONT,
            text=ac_text,
            color=0xFFFFFF,
            x=70,
            y=y
        )
        self._content_group.append(self._content_labels["ac_line"])
        y += 11

        # Separator line
        sep = Line(0, y, DISPLAY_WIDTH, y, color=0xFFFFFF)
        self._content_group.append(sep)
        y += 6

        # Quick stats line
        cpu = self.state.get("cpu_temp", 0)
        wifi = self.state.get("wifi_status", "OFF")
        notif = self.state.get("notifications", 0)
        quick_text = f"CPU:{cpu}C | WiFi:{wifi}"
        self._content_labels["quick_stats"] = label.Label(
            terminalio.FONT,
            text=quick_text,
            color=0xFFFFFF,
            x=4,
            y=y
        )
        self._content_group.append(self._content_labels["quick_stats"])

    def _build_system_terminal(self):
        """System panel - Dashboard Bars style"""
        y = 18

        # CPU Bar
        cpu = self.state.get("cpu_temp", 0)
        cpu_bar = self._metric_bar(cpu, 20, 80)
        self._content_labels["sys_cpu"] = label.Label(
            terminalio.FONT,
            text=f"CPU [{cpu_bar}] {cpu:>3}C",
            color=0xFFFFFF,
            x=4,
            y=y
        )
        self._content_group.append(self._content_labels["sys_cpu"])
        y += 11

        # Voltage Bar
        voltage = self.state.get("voltage", "0.0V")
        volt_f = self._parse_voltage(voltage)
        vlt_bar = self._metric_bar(volt_f, 2.5, 3.5)
        self._content_labels["sys_vlt"] = label.Label(
            terminalio.FONT,
            text=f"VLT [{vlt_bar}] {voltage:>4}",
            color=0xFFFFFF,
            x=4,
            y=y
        )
        self._content_group.append(self._content_labels["sys_vlt"])
        y += 11

        # Scan Rate Bar
        scan = self.state.get("scan_rate", 0)
        scn_bar = self._metric_bar(scan, 50, 200)
        self._content_labels["sys_scn"] = label.Label(
            terminalio.FONT,
            text=f"SCN [{scn_bar}] {scan:>4}",
            color=0xFFFFFF,
            x=4,
            y=y
        )
        self._content_group.append(self._content_labels["sys_scn"])
        y += 8

        # Separator
        sep = Line(0, y, DISPLAY_WIDTH, y, color=0xFFFFFF)
        self._content_group.append(sep)
        y += 8

        # Status footer
        wifi = self.state.get("wifi_status", "OFF")
        caps = self.state.get("caps_on", False)
        wifi_s = "ON" if wifi == "ON" else "--"
        caps_s = "ON" if caps else "--"
        self._content_labels["sys_footer"] = label.Label(
            terminalio.FONT,
            text=f"WIFI {wifi_s}    CAPS {caps_s}",
            color=0xFFFFFF,
            x=4,
            y=y
        )
        self._content_group.append(self._content_labels["sys_footer"])

    def _build_network_terminal(self):
        """Network panel - terminal style"""
        y = 22

        # 3D Printer
        d3 = self.state.get("d3_status", "---")
        self._content_labels["d3_lbl"] = label.Label(
            terminalio.FONT,
            text=f"3D-Print > {d3}",
            color=0xFFFFFF,
            x=4,
            y=y
        )
        self._content_group.append(self._content_labels["d3_lbl"])
        y += 13

        # Lasercutter
        lc = self.state.get("lc_status", "---")
        self._content_labels["lc_lbl"] = label.Label(
            terminalio.FONT,
            text=f"LASER    > {lc}",
            color=0xFFFFFF,
            x=4,
            y=y
        )
        self._content_group.append(self._content_labels["lc_lbl"])
        y += 13

        # Separator
        sep1 = Line(0, y, DISPLAY_WIDTH, y, color=0xFFFFFF)
        self._content_group.append(sep1)

        # Config Mode Hint (below separator, white = visible on monochrome OLED)
        hint_lbl = label.Label(
            terminalio.FONT,
            text="conf: FN+M",
            color=0xFFFFFF,
        )
        hint_lbl.anchor_point = (0.5, 0)
        hint_lbl.anchored_position = (DISPLAY_WIDTH // 2, y + 5)
        self._content_group.append(hint_lbl)

    def _build_weather_terminal(self):
        """Wetter/Uhrzeit/Datum Panel.

        Layout (128x64px, Content y=12..63):
          y=14  Uhrzeit HH:MM (zentriert)
          y=25  Wochentag + Datum  "Do 17.03.2026" (zentriert)
          y=36  Trennlinie
          y=43  Temp + Luftfeuchtigkeit  "+18C  65%"
          y=54  Wetterbedingung + Stadt  "Cloudy  Wien"
        """
        DAYS_DE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
        t = time.localtime()

        # Uhrzeit HH:MM (keine Sekunden → Update nur einmal pro Minute)
        time_str = "{:02d}:{:02d}".format(t.tm_hour, t.tm_min)
        time_lbl = label.Label(terminalio.FONT, text=time_str, color=0xFFFFFF)
        time_lbl.anchor_point = (0.5, 0)
        time_lbl.anchored_position = (DISPLAY_WIDTH // 2, 14)
        self._content_group.append(time_lbl)
        self._content_labels["wtr_time"] = time_lbl

        # Datum
        wday = DAYS_DE[t.tm_wday] if t.tm_wday < 7 else "--"
        date_str = "{} {:02d}.{:02d}.{:04d}".format(
            wday, t.tm_mday, t.tm_mon, t.tm_year)
        date_lbl = label.Label(terminalio.FONT, text=date_str, color=0xFFFFFF)
        date_lbl.anchor_point = (0.5, 0)
        date_lbl.anchored_position = (DISPLAY_WIDTH // 2, 25)
        self._content_group.append(date_lbl)
        self._content_labels["wtr_date"] = date_lbl

        # Trennlinie
        sep = Line(0, 36, DISPLAY_WIDTH, 36, color=0xFFFFFF)
        self._content_group.append(sep)

        # Temperatur + Luftfeuchtigkeit
        temp = self.state.get("weather_temp", "--")
        hum  = self.state.get("weather_hum",  "--")
        th_str = "{:<7}{}".format(temp[:7], hum[:4])
        th_lbl = label.Label(terminalio.FONT, text=th_str, color=0xFFFFFF, x=4, y=43)
        self._content_group.append(th_lbl)
        self._content_labels["wtr_th"] = th_lbl

        # Wetterbedingung
        cond = self.state.get("weather_cond", "------")
        cond_lbl = label.Label(terminalio.FONT, text=cond[:20], color=0xFFFFFF, x=4, y=54)
        self._content_group.append(cond_lbl)
        self._content_labels["wtr_cond"] = cond_lbl

        # Stadt (eine Zeile höher als Bedingung, einen Buchstaben weiter rechts)
        city = self.state.get("weather_city", "------")
        city_lbl = label.Label(terminalio.FONT, text=city[:8], color=0xFFFFFF, x=70, y=43)
        self._content_group.append(city_lbl)
        self._content_labels["wtr_city"] = city_lbl

    # =========================================================================
    # HELPER FUNCTIONS
    # =========================================================================

    def _add_line(self, prompt, state_key, y, formatter=None):
        """Add a terminal-style line with prompt"""
        value = self.state.get(state_key, 0)
        if formatter:
            value_text = formatter(value)
        else:
            value_text = str(value)

        # Prompt label
        prompt_lbl = label.Label(
            terminalio.FONT,
            text=prompt,
            color=0xFFFFFF,
            x=4,
            y=y
        )
        self._content_group.append(prompt_lbl)

        # Value label
        value_lbl = label.Label(
            terminalio.FONT,
            text=value_text,
            color=0xFFFFFF,
            x=40,
            y=y
        )
        self._content_group.append(value_lbl)
        self._content_labels[state_key] = value_lbl

    def _temp_bar(self, temp):
        """Create ASCII temperature bar"""
        # Scale: 20-80C -> 0-6 blocks
        blocks = min(6, max(0, (temp - 20) // 10))
        return "[" + "#" * blocks + "-" * (6 - blocks) + "]"

    def _metric_bar(self, value, min_val, max_val, width=8):
        """Create text metric bar: ######-- """
        if max_val <= min_val:
            pct = 0.0
        else:
            pct = max(0.0, min(1.0, (value - min_val) / (max_val - min_val)))
        filled = round(pct * width)
        return "#" * filled + "-" * (width - filled)

    def _parse_voltage(self, voltage_str):
        """Parse voltage string to float"""
        try:
            return float(str(voltage_str).replace("V", "").replace("v", ""))
        except (ValueError, AttributeError):
            return 0.0

    def _format_layer(self, layer, toggled):
        """Format layer display"""
        if layer == 0:
            return "L:1"
        elif toggled:
            return "L:2+"
        else:
            return "L:2"

    # =========================================================================
    # STATE UPDATES
    # =========================================================================

    def update_layer(self, layer, toggled=False):
        """Update layer display"""
        self.state["current_layer"] = layer
        self.state["layer_toggled"] = toggled

        if self._header_label:
            self._header_label.text = self._format_layer(layer, toggled)

    def update_caps(self, caps_on):
        """Update caps lock display"""
        self.state["caps_on"] = caps_on
        self.needs_update = True

    def set_state(self, key, value):
        """Set state value and mark for update"""
        self.state[key] = value
        self.needs_update = True

    def toggle_mode(self):
        """Switch to next dashboard mode"""
        self.mode = (self.mode + 1) % MODE_COUNT

        # Tabs neu bauen — garantiert korrekte Farben + padding_left auf allen Tabs
        self._build_tabs()

        self._build_content()
        self.needs_update = True

    # =========================================================================
    # REFRESH LOGIC
    # =========================================================================

    def _update_content_values(self):
        """Update values in current dashboard"""
        if not self._content_labels:
            return

        if self.mode == MODE_STATUS:
            # Keypress
            kp = self.state.get("current_keypress", 0)
            if "current_keypress" in self._content_labels:
                self._content_labels["current_keypress"].text = f" {kp:,}".replace(",", ".")

            # Runtime
            rt = self.state.get("current_runtime", 0)
            if "current_runtime" in self._content_labels:
                self._content_labels["current_runtime"].text = f" {rt} min"

            # Caps
            caps = self.state.get("caps_on", False)
            if "caps_line" in self._content_labels:
                self._content_labels["caps_line"].text = "CAPS:[ON!]" if caps else "CAPS:[OFF]"

            # Autoclicker
            ac = self.state.get("autoclicker", False)
            if "ac_line" in self._content_labels:
                self._content_labels["ac_line"].text = "AC:[ON!]" if ac else "AC:[OFF]"

            # Quick stats
            cpu = self.state.get("cpu_temp", 0)
            wifi = self.state.get("wifi_status", "OFF")
            if "quick_stats" in self._content_labels:
                self._content_labels["quick_stats"].text = f"CPU:{cpu}C | WiFi:{wifi}"
            
            # Notifications
            notif = self.state.get("notifications", 0)
            if "notif_lbl" in self._content_labels:
                self._content_labels["notif_lbl"].text = f"MSG:{notif}"

        elif self.mode == MODE_SYSTEM:
            # CPU bar
            cpu = self.state.get("cpu_temp", 0)
            cpu_bar = self._metric_bar(cpu, 20, 80)
            if "sys_cpu" in self._content_labels:
                self._content_labels["sys_cpu"].text = f"CPU [{cpu_bar}] {cpu:>3}C"

            # Voltage bar
            voltage = self.state.get("voltage", "0.0V")
            volt_f = self._parse_voltage(voltage)
            vlt_bar = self._metric_bar(volt_f, 2.5, 3.5)
            if "sys_vlt" in self._content_labels:
                self._content_labels["sys_vlt"].text = f"VLT [{vlt_bar}] {voltage:>4}"

            # Scan bar
            scan = self.state.get("scan_rate", 0)
            scn_bar = self._metric_bar(scan, 50, 200)
            if "sys_scn" in self._content_labels:
                self._content_labels["sys_scn"].text = f"SCN [{scn_bar}] {scan:>4}"

            # Footer
            wifi = self.state.get("wifi_status", "OFF")
            caps = self.state.get("caps_on", False)
            if "sys_footer" in self._content_labels:
                wifi_s = "ON" if wifi == "ON" else "--"
                caps_s = "ON" if caps else "--"
                self._content_labels["sys_footer"].text = f"WIFI {wifi_s}    CAPS {caps_s}"

        elif self.mode == MODE_NETWORK:
            # 3D Printer
            d3 = self.state.get("d3_status", "---")
            if "d3_lbl" in self._content_labels:
                self._content_labels["d3_lbl"].text = f"3D-Print > {d3}"

            # Lasercutter
            lc = self.state.get("lc_status", "---")
            if "lc_lbl" in self._content_labels:
                self._content_labels["lc_lbl"].text = f"LASER    > {lc}"

        elif self.mode == MODE_WEATHER:
            DAYS_DE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
            t = time.localtime()
            cur_min = t.tm_min

            # Nur updaten wenn sich die Minute geändert hat
            if cur_min == self._last_wtr_minute:
                return
            self._last_wtr_minute = cur_min

            # Uhrzeit HH:MM
            if "wtr_time" in self._content_labels:
                self._content_labels["wtr_time"].text = "{:02d}:{:02d}".format(
                    t.tm_hour, t.tm_min)

            # Datum
            if "wtr_date" in self._content_labels:
                wday = DAYS_DE[t.tm_wday] if t.tm_wday < 7 else "--"
                self._content_labels["wtr_date"].text = "{} {:02d}.{:02d}.{:04d}".format(
                    wday, t.tm_mday, t.tm_mon, t.tm_year)

            # Wetter
            if "wtr_th" in self._content_labels:
                temp = self.state.get("weather_temp", "--")
                hum  = self.state.get("weather_hum",  "--")
                self._content_labels["wtr_th"].text = "{:<7}{}".format(temp[:7], hum[:4])

            if "wtr_cond" in self._content_labels:
                self._content_labels["wtr_cond"].text = self.state.get("weather_cond", "------")[:20]
            if "wtr_city" in self._content_labels:
                self._content_labels["wtr_city"].text = self.state.get("weather_city", "------")[:8]

    def refresh(self):
        """Periodic display refresh"""
        if not self.display or not self.is_on:
            return

        current_time = time.monotonic()

        # WTR: alle 30s prüfen ob Minute gewechselt (kein Sekundentakt nötig)
        if self.mode == MODE_WEATHER:
            if current_time - self.last_refresh >= 30.0:
                self.needs_update = True
                self.last_refresh = current_time
        elif current_time - self.last_refresh >= Timing.DISPLAY_REFRESH:
            self.needs_update = True
            self.last_refresh = current_time

        if self.needs_update:
            if not self.config_mode_active:  # Config Mode Screen nicht überschreiben
                self._update_content_values()
            self.needs_update = False

    # =========================================================================
    # STATISTICS SCREEN - Terminal Style
    # =========================================================================

    def show_statistics(self, alltime_keypress, alltime_runtime, ip_address):
        """Show statistics overlay - terminal style"""
        if not self.display:
            return

        stats = displayio.Group()

        # Header
        header = label.Label(
            terminalio.FONT,
            text="[ SYSTEM STATS ]",
            color=0xFFFFFF
        )
        header.anchor_point = (0.5, 0)
        header.anchored_position = (DISPLAY_WIDTH // 2, 4)
        stats.append(header)

        # Separator
        sep = Line(0, 14, DISPLAY_WIDTH, 14, color=0xFFFFFF)
        stats.append(sep)

        y = 20

        # Model
        model_lbl = label.Label(
            terminalio.FONT,
            text=f"MTN > {MODEL_NUMBER}",
            color=0xFFFFFF,
            x=4,
            y=y
        )
        stats.append(model_lbl)
        y += 11

        # IP
        ip_lbl = label.Label(
            terminalio.FONT,
            text=f"IP  > {ip_address}",
            color=0xFFFFFF,
            x=4,
            y=y
        )
        stats.append(ip_lbl)
        y += 11

        # Keys
        kp_k = alltime_keypress // 1000
        kp_lbl = label.Label(
            terminalio.FONT,
            text=f"KEY > {kp_k}k total",
            color=0xFFFFFF,
            x=4,
            y=y
        )
        stats.append(kp_lbl)
        y += 11

        # Runtime
        rt_h = alltime_runtime // 60
        rt_lbl = label.Label(
            terminalio.FONT,
            text=f"RUN > {rt_h}h total",
            color=0xFFFFFF,
            x=4,
            y=y
        )
        stats.append(rt_lbl)

        self.display.root_group = stats

        try:
            self.display.refresh()
        except Exception:
            pass

        time.sleep(5)

        self.main_screen()
        self._update_content_values()

        try:
            self.display.refresh()
        except Exception:
            pass

    def force_refresh(self):
        """Erzwingt sofortiges Display-Update (vor blockierenden Operationen)"""
        if self.display:
            try:
                self.display.refresh()
            except Exception:
                pass

    # =========================================================================
    # CONFIGURATION MODE SCREEN
    # =========================================================================

    def show_config_mode(self, ip_address):
        """
        Zeigt den Configuration Mode Screen dauerhaft auf dem Display.
        Bleibt aktiv bis exit_config_mode() aufgerufen wird.
        Aktiviert durch FN + Right Shift.

        Layout (128x64 OLED):
          [ CONFIG MODE ]
          ──────────────
          Configuration
          Mode
          ──────────────
          <IP-Adresse>
        """
        if not self.display:
            return

        self.config_mode_active = True

        grp = displayio.Group()

        cx = DISPLAY_WIDTH // 2  # horizontal center = 64

        # Header: [ CONFIG MODE ]
        hdr = label.Label(terminalio.FONT, text="[ CONFIG MODE ]", color=0xFFFFFF)
        hdr.anchor_point = (0.5, 0)
        hdr.anchored_position = (cx, 3)
        grp.append(hdr)

        # Separator 1
        grp.append(Line(0, 13, DISPLAY_WIDTH, 13, color=0xFFFFFF))

        # "Configuration" centered
        conf_lbl = label.Label(terminalio.FONT, text="Configuration", color=0xFFFFFF)
        conf_lbl.anchor_point = (0.5, 0)
        conf_lbl.anchored_position = (cx, 21)
        grp.append(conf_lbl)

        # "Mode" centered
        mode_lbl = label.Label(terminalio.FONT, text="Mode", color=0xFFFFFF)
        mode_lbl.anchor_point = (0.5, 0)
        mode_lbl.anchored_position = (cx, 32)
        grp.append(mode_lbl)

        # Separator 2
        grp.append(Line(0, 44, DISPLAY_WIDTH, 44, color=0xFFFFFF))

        # IP Address centered (max 15 chars for "xxx.xxx.xxx.xxx")
        ip_str = str(ip_address) if ip_address else "not connected"
        ip_lbl = label.Label(terminalio.FONT, text=ip_str[:21], color=0xFFFFFF)
        ip_lbl.anchor_point = (0.5, 0)
        ip_lbl.anchored_position = (cx, 50)
        grp.append(ip_lbl)

        self._config_group = grp
        self.display.root_group = grp

        try:
            self.display.refresh()
        except Exception:
            pass

    def exit_config_mode(self):
        """Beendet Configuration Mode und kehrt zum normalen Dashboard zurück."""
        if not self.config_mode_active:
            return
        self.config_mode_active = False
        self._config_group = None
        self.main_screen()
        self._update_content_values()
        try:
            self.display.refresh()
        except Exception:
            pass

    # =========================================================================
    # WIFI SETUP WIZARD SCREENS
    # =========================================================================

    def _setup_overlay(self, title):
        """Erstellt ein neues Overlay-Group mit Rahmen und Titelzeile"""
        group = displayio.Group()

        title_lbl = label.Label(
            terminalio.FONT,
            text=title,
            color=0xFFFFFF
        )
        title_lbl.anchor_point = (0.5, 0)
        title_lbl.anchored_position = (DISPLAY_WIDTH // 2, 3)
        group.append(title_lbl)

        sep = Line(0, 14, DISPLAY_WIDTH, 14, color=0xFFFFFF)
        group.append(sep)

        return group

    def show_wifi_setup_scanning(self):
        """Zeigt 'Scanning...' Screen während des Netzwerkscans"""
        if not self.display:
            return

        group = self._setup_overlay("[WIFI SETUP]")

        for text, y in [("Scanning for", 25), ("networks...", 37), ("Please wait", 50)]:
            lbl = label.Label(terminalio.FONT, text=text, color=0xFFFFFF, x=18, y=y)
            group.append(lbl)

        self.display.root_group = group

    def show_wifi_setup_select(self, networks, selected_idx, scroll_offset):
        """
        Zeigt scrollbare Netzwerkliste zur Auswahl.

        Steuerung: I=hoch, K=runter, Enter=wählen, Esc=abbrechen
        """
        if not self.display:
            return

        group = self._setup_overlay("[SELECT WIFI]")

        y = 20  # Etwas mehr Abstand nach Separator
        visible = networks[scroll_offset:scroll_offset + 3]  # 3 statt 4

        for i, (ssid, rssi) in enumerate(visible):
            abs_idx = scroll_offset + i
            marker = ">" if abs_idx == selected_idx else " "
            ssid_trunc = ssid[:13] if len(ssid) > 13 else ssid
            line_text = "{} {:<13} {:>4}".format(marker, ssid_trunc, rssi)

            net_lbl = label.Label(
                terminalio.FONT,
                text=line_text,
                color=0xFFFFFF,
                x=2,
                y=y
            )
            group.append(net_lbl)
            y += 13  # 13px Abstand statt 10px

        # Scroll-Indikator (Positionen angepasst)
        if scroll_offset > 0:
            up_ind = label.Label(terminalio.FONT, text="^", color=0xFFFFFF,
                                  x=DISPLAY_WIDTH - 10, y=20)
            group.append(up_ind)
        if scroll_offset + 3 < len(networks):  # 3 statt 4
            dn_ind = label.Label(terminalio.FONT, text="v", color=0xFFFFFF,
                                  x=DISPLAY_WIDTH - 10, y=46)
            group.append(dn_ind)

        # Hinweiszeile
        hint = label.Label(terminalio.FONT, text="[I/K]nav [ENT]sel",
                           color=0xFFFFFF, x=2, y=57)
        group.append(hint)

        self.display.root_group = group

    def show_wifi_setup_password(self, ssid, password):
        """
        Zeigt Passwort-Eingabescreen.

        Steuerung: Tasten tippen, Shift=Großschreibung,
                   Backspace=löschen, Enter=OK, Esc=zurück
        """
        if not self.display:
            return

        group = self._setup_overlay("[WIFI PW]")

        # SSID anzeigen
        ssid_trunc = ssid[:18] if len(ssid) > 18 else ssid
        ssid_lbl = label.Label(terminalio.FONT, text=ssid_trunc,
                               color=0xFFFFFF, x=2, y=20)
        group.append(ssid_lbl)

        # Trennlinie
        sep2 = Line(0, 29, DISPLAY_WIDTH, 29, color=0xFFFFFF)
        group.append(sep2)

        # Passwort-Feld: max 9 sichtbare Zeichen + Cursor
        # 6px/Zeichen: "PW:.." + 7Z + "_" = 13Z = 78px → endet x=80
        # Count startet x=82, "[63/63]" = 42px → endet x=124: kein Overlap
        if len(password) > 9:
            pw_display = ".." + password[-7:]
        else:
            pw_display = password
        pw_text = f"PW:{pw_display}_"

        pw_lbl = label.Label(terminalio.FONT, text=pw_text,
                             color=0xFFFFFF, x=2, y=39)
        group.append(pw_lbl)

        # Zeichenanzahl (rechts, kein Overlap)
        count_lbl = label.Label(terminalio.FONT,
                                text=f"[{len(password)}/63]",
                                color=0xFFFFFF, x=82, y=39)
        group.append(count_lbl)

        # Hinweiszeilen
        hint1 = label.Label(terminalio.FONT, text="SHF=up BSP=del",
                            color=0xFFFFFF, x=2, y=50)
        hint2 = label.Label(terminalio.FONT, text="ENT=ok ESC=back",
                            color=0xFFFFFF, x=2, y=58)
        group.append(hint1)
        group.append(hint2)

        self.display.root_group = group

    def show_wifi_setup_status(self, title, detail=""):
        """Zeigt Status/Connecting/Ergebnis Screen"""
        if not self.display:
            return

        group = self._setup_overlay("[WIFI SETUP]")

        title_lbl = label.Label(terminalio.FONT, text=title[:20],
                                color=0xFFFFFF, x=4, y=28)
        group.append(title_lbl)

        if detail:
            detail_lbl = label.Label(terminalio.FONT, text=detail[:20],
                                     color=0xFFFFFF, x=4, y=42)
            group.append(detail_lbl)

        self.display.root_group = group

    # =========================================================================
    # POWER MANAGEMENT
    # =========================================================================

    def off(self):
        """Turn display off (power save)"""
        self.is_on = False
        if self.display:
            blank = displayio.Group()
            self.display.root_group = blank
            try:
                self.display.refresh()
            except Exception:
                pass

    def on(self):
        """Turn display on"""
        self.is_on = True
        self.main_screen()
        self.needs_update = True
