# features/wifi.py - WiFi & Home Assistant Feature + Setup Wizard
# Netzwerk-Integration für MMOrtho
import ssl
import json
import socketpool
import adafruit_requests
import wifi
import time

from config import WiFiConfig, HomeAssistant


# =============================================================================
# SETUP WIZARD CONSTANTS
# =============================================================================

_IDLE = 0
_SCANNING = 1
_SELECT = 2
_PASSWORD = 3
_CONNECTING = 4
_DONE = 5

# QWERTZ physische Tastenpositionen → (normal, shift)
# Schlüssel = Matrix-Key-String aus keymap.py
_CHAR_MAP = {
    # Zahlenreihe
    "112": ("1", "!"),  "113": ("2", '"'), "114": ("3", "#"),
    "115": ("4", "$"),  "116": ("5", "%"), "216": ("6", "&"),
    "215": ("7", "/"),  "214": ("8", "("), "213": ("9", ")"),
    "212": ("0", "="),
    # QWERTZ-Reihe
    "122": ("q", "Q"),  "123": ("w", "W"), "124": ("e", "E"),
    "125": ("r", "R"),  "126": ("t", "T"), "226": ("z", "Z"),
    "225": ("u", "U"),  "224": ("i", "I"), "223": ("o", "O"), "222": ("p", "P"),
    # ASDF-Reihe
    "132": ("a", "A"),  "133": ("s", "S"), "134": ("d", "D"),
    "135": ("f", "F"),  "136": ("g", "G"), "236": ("h", "H"),
    "235": ("j", "J"),  "234": ("k", "K"), "233": ("l", "L"),
    # YXCVBNM-Reihe
    "142": ("y", "Y"),  "143": ("x", "X"), "144": ("c", "C"),
    "145": ("v", "V"),  "146": ("b", "B"), "246": ("n", "N"),
    "245": ("m", "M"),
    # Sonderzeichen
    "251": ("-", "_"),  "254": ("+", "*"), "243": (".", ":"),
    "244": (",", ";"),  "155": (" ", " "), "256": (" ", " "),
    "232": ("o", "O"),  # ö/Ö-Position (vereinfacht für Passwörter)
    "231": ("a", "A"),  # ä/Ä-Position (vereinfacht)
    "252": ("u", "U"),  # ü/Ü-Position (vereinfacht)
}

# Navigation-Tasten (physische Key-IDs, Base-Layer)
_KEY_UP = "224"        # I-Taste → hoch in Liste
_KEY_DOWN = "234"      # K-Taste → runter in Liste
_KEY_ENTER = "255"     # Enter → bestätigen
_KEY_CANCEL = "111"    # Escape → abbrechen / zurück
_KEY_BACKSPACE = "211" # Backspace → letztes Zeichen löschen


class WiFiFeature:
    """
    WiFi Feature mit Home Assistant Integration und Setup Wizard.

    Setup Wizard Ablauf:
      1. FN+, startet den Wizard → Netzwerkscan
      2. Netzwerk auswählen mit I (hoch) / K (runter) / Enter
      3. WPA-Key eintippen (Shift für Großbuchstaben, Backspace löschen)
      4. Enter → Verbindungsversuch, bei Erfolg wird SSID+PW gespeichert
    """

    def __init__(self):
        self.enabled = False
        self.status = "OFF"  # OFF, ON, CON, ERR
        self.pool = None
        self.requests = None
        self.ntp_synced = False

        # Device Status Cache
        self.lc_status = "N/A"
        self.d3_status = "N/A"

        # === Setup Wizard State ===
        self._setup_state = _IDLE
        self._setup_networks = []   # Liste von (ssid, rssi)
        self._setup_sel = 0         # Ausgewählter Index
        self._setup_offset = 0      # Scroll-Offset für Anzeige
        self._setup_ssid = ""       # Gewähltes SSID
        self._setup_pw = ""         # Eingegebenes Passwort
        self._setup_msg = ""        # Status-/Fehlermeldung
        self._setup_dirty = True    # Display-Update nötig

        # WiFi initial deaktiviert
        wifi.radio.enabled = False

    # =========================================================================
    # DEOBFUSKIERUNG
    # =========================================================================

    def _deobfuscate(self, s, key=WiFiConfig.XOR_KEY):
        """Deobfuskiert Base64+XOR verschlüsselte Strings"""
        base64chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
        s = s.rstrip("=")
        buffer = 0
        bits = 0
        result = bytearray()
        for c in s:
            buffer = (buffer << 6) + base64chars.index(c)
            bits += 6
            if bits >= 8:
                bits -= 8
                result.append((buffer >> bits) & 0xFF)
        return "".join([chr(b ^ key) for b in result])

    # =========================================================================
    # CREDENTIALS PERSISTENZ
    # =========================================================================

    def _obfuscate(self, s, key=WiFiConfig.XOR_KEY):
        """Obfuskiert String mit XOR+Base64 (gleiche Methode wie WiFiConfig.PASSWORD_OBFUSCATED).
        Kein echter Verschlüsselungsschutz — verhindert aber Klartext-Lesbarkeit
        beim schnellen Durchblättern der Dateien. SWD-Debug-Readout bleibt möglich.
        """
        base64chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
        xored = bytearray([ord(c) ^ key for c in s])
        result = []
        buf = 0
        bits = 0
        for byte in xored:
            buf = (buf << 8) | byte
            bits += 8
            while bits >= 6:
                bits -= 6
                result.append(base64chars[(buf >> bits) & 0x3F])
        if bits > 0:
            result.append(base64chars[(buf << (6 - bits)) & 0x3F])
        while len(result) % 4:
            result.append("=")
        return "".join(result)

    def _load_credentials(self):
        """Lädt WiFi-Credentials aus /data/wifi.json.
        Unterstützt beide Formate:
          v2 (obfuskiert): {"ssid_ob": ..., "pw_ob": ..., "v": 2}
          v1 (Klartext):   {"ssid": ..., "password": ...}  (Altformat, Fallback)
        """
        try:
            with open("/data/wifi.json", "r") as f:
                data = json.load(f)
            if data.get("v") == 2:
                ssid = self._deobfuscate(data["ssid_ob"])
                pw = self._deobfuscate(data["pw_ob"])
            else:
                # Altformat: Klartext (Migration beim nächsten _save_credentials)
                ssid = data.get("ssid")
                pw = data.get("password")
            return ssid, pw
        except Exception:
            return None, None

    def _save_credentials(self, ssid, password):
        """Speichert WiFi-Credentials obfuskiert in /data/wifi.json (Format v2).
        Verhindert Klartext-Lesbarkeit; kein echter Flash-Ausleseschutz auf RP2350
        ohne Custom-Firmware mit Flash-Encryption (nicht in CircuitPython verfügbar).
        """
        try:
            with open("/data/wifi.json", "w") as f:
                json.dump({
                    "v": 2,
                    "ssid_ob": self._obfuscate(ssid),
                    "pw_ob": self._obfuscate(password),
                }, f)
            print("WiFi Credentials gespeichert (obfuskiert): " + ssid)
        except Exception as e:
            print("Credentials Speicherfehler: " + str(e))

    # =========================================================================
    # TOGGLE (bestehende Funktion)
    # =========================================================================

    def toggle(self):
        """Schaltet WiFi ein/aus"""
        try:
            if self.enabled:
                self._disconnect()
            else:
                self._connect()
        except Exception as e:
            print(f"WiFi Error: {e}")
            self.status = "ERR"

    def _connect(self, ssid=None, password=None):
        """Verbindet mit WiFi"""
        wifi.radio.enabled = True

        if ssid is None:
            saved_ssid, saved_pw = self._load_credentials()
            if not saved_ssid:
                print("Keine gespeicherten WiFi-Credentials. Bitte Setup-Wizard nutzen.")
                self.status = "OFF"
                return
            ssid = saved_ssid
            password = saved_pw
            print(f"Verwende gespeicherte Credentials: {ssid}")

        wifi.radio.connect(ssid, password)
        print(f"WiFi verbunden: {wifi.radio.ipv4_address}")

        self.pool = socketpool.SocketPool(wifi.radio)
        ssl_context = None
        if HomeAssistant.URL.startswith("https://"):
            ssl_context = ssl.create_default_context()
        self.requests = adafruit_requests.Session(self.pool, ssl_context)

        self._ping_gateway()
        self._sync_ntp()
        self.enabled = True
        self.refresh_device_status()

    def _disconnect(self):
        """Trennt WiFi Verbindung"""
        wifi.radio.enabled = False
        self.enabled = False
        self.status = "OFF"
        self.lc_status = "N/A"
        self.d3_status = "N/A"
        print("WiFi deaktiviert")

    def _ping_gateway(self):
        """Pingt das Gateway zur Verbindungsprüfung"""
        try:
            gateway = wifi.radio.ipv4_gateway
            rtt = wifi.radio.ping(gateway)
            if rtt is not None:
                print(f"Ping OK: {round(rtt * 1000)} ms")
                self.status = "CON"
            else:
                print("Ping failed")
                self.status = "ON"
        except Exception as e:
            print(f"Ping error: {e}")
            self.status = "ERR"

    def _get_wday(self, y, m, d):
        """Berechnet Wochentag (0=Mo, 6=So) nach Sakamoto's Algorithmus."""
        t = [0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4]
        if m < 3: y -= 1
        # Sakamoto liefert 0=So, 1=Mo... 6=Sa -> konvertieren zu 0=Mo... 6=So
        return ((y + y // 4 - y // 100 + y // 400 + t[m - 1] + d) + 6) % 7

    def _get_cet_offset(self, t_utc):
        """Berechnet den CET/CEST Offset (+1/+2) für eine UTC-Zeit."""
        y, m, d, h = t_utc.tm_year, t_utc.tm_mon, t_utc.tm_mday, t_utc.tm_hour
        if m < 3 or m > 10:
            return 1
        if m > 3 and m < 10:
            return 2
        # Letzter Sonntag im Monat (Übergang um 01:00 UTC)
        w31 = self._get_wday(y, m, 31)
        last_sun = 31 - ((w31 + 1) % 7)
        if m == 3:
            return 2 if (d > last_sun or (d == last_sun and h >= 1)) else 1
        else: # m == 10
            return 2 if (d < last_sun or (d == last_sun and h < 1)) else 1

    def _sync_ntp(self):
        """Synchronisiert RTC mit NTP (erfordert adafruit_ntp in /lib/).
        Berechnet automatisch Sommer/Winterzeit (CET/CEST).
        """
        for attempt in range(2):
            try:
                import rtc
                import adafruit_ntp
                from config import WeatherConfig
                # Netzwerk-Stack braucht nach radio.connect() kurz bis UDP bereit ist.
                time.sleep(1 if attempt == 0 else 3)

                # 1. UTC holen um Datum für Sommerzeitprüfung zu haben
                ntp = adafruit_ntp.NTP(self.pool, tz_offset=0)
                t_utc = ntp.datetime

                # 2. Offset berechnen (Standard CET = 1, CEST = 2)
                offset = self._get_cet_offset(t_utc)

                # 3. Mit richtigem Offset erneut setzen (neues Objekt für saubere Berechnung)
                ntp_local = adafruit_ntp.NTP(self.pool, tz_offset=offset)
                rtc.RTC().datetime = ntp_local.datetime

                print(f"NTP sync OK (TZ Offset: {offset})")
                self.ntp_synced = True
                return
            except Exception as e:
                print(f"NTP Fehler (Versuch {attempt + 1}): {e}")
        self.ntp_synced = False

    # =========================================================================
    # HOME ASSISTANT
    # =========================================================================

    def get_device_status(self, entity_id):
        """Holt den Status eines Home Assistant Devices"""
        if not self.enabled or not self.requests:
            return "N/A"
        try:
            url = f"{HomeAssistant.URL}/api/states/{entity_id}"
            headers = {
                "Authorization": f"Bearer {HomeAssistant.TOKEN}",
                "Content-Type": "application/json"
            }
            response = self.requests.get(url, headers=headers, timeout=3)
            if response.status_code == 200:
                data = response.json()
                state = data.get("state", "unknown")
                print(f"HA {entity_id} = {state}")
                return state
            else:
                print(f"HA Error {entity_id}: HTTP {response.status_code}")
                return "N/A"
        except Exception as e:
            print(f"HA Exception {entity_id}: {type(e).__name__}: {e}")
            return "N/A"

    def refresh_device_status(self):
        """Aktualisiert alle Device-Status von Home Assistant"""
        self.lc_status = self.get_device_status(HomeAssistant.ENTITIES["laser"])
        self.d3_status = self.get_device_status(HomeAssistant.ENTITIES["printer_3d"])

    def fetch_weather(self):
        """Holt Wetterdaten von wttr.in (kein API-Key nötig)."""
        if not self.enabled or not self.requests:
            return None
        try:
            from config import WeatherConfig
            if not WeatherConfig.ENABLED:
                return None
            url = "http://wttr.in/" + WeatherConfig.CITY + "?format=%t+%h+%C"
            resp = self.requests.get(url, timeout=5)
            if resp.status_code == 200:
                text = resp.text.strip()
                parts = text.split(" ", 2)
                return {
                    "temp": parts[0] if len(parts) > 0 else "--",
                    "hum":  parts[1] if len(parts) > 1 else "--",
                    "cond": parts[2][:12] if len(parts) > 2 else "------",
                    "city": WeatherConfig.CITY[:8],
                }
        except Exception as e:
            print("Wetter Fehler: " + str(e))
        return None

    def fetch_generic_json(self, url, headers=None, key=None):
        """Generische Funktion um einen Wert aus einer JSON-API zu lesen."""
        if not self.enabled or not self.requests:
            return None
        try:
            resp = self.requests.get(url, headers=headers, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if key:
                    # Einfaches Key-Slicing (z.B. data['status']['count'])
                    for k in key.split('.'):
                        data = data[k]
                    return data
                return data
        except Exception as e:
            print(f"Generic API Fehler: {e}")
        return None

    def get_ip_address(self):
        """Gibt die aktuelle IP-Adresse zurück"""
        if wifi.radio.connected:
            return str(wifi.radio.ipv4_address)
        if wifi.radio.ap_active:
            return str(wifi.radio.ipv4_address_ap)
        return "Not connected"

    def start_ap(self):
        """Startet einen Access Point für die Web-Konfiguration"""
        try:
            from config import KEYBOARD_NAME
            wifi.radio.start_ap(f"{KEYBOARD_NAME}_Config", "mmortho123")
            print(f"AP gestartet: {wifi.radio.ipv4_address_ap}")
            return True
        except Exception as e:
            print(f"AP Fehler: {e}")
            return False

    def stop_ap(self):
        """Beendet den Access Point"""
        wifi.radio.stop_ap()
        print("AP beendet")

    def get_status_dict(self):
        """Gibt alle Status-Werte als Dictionary zurück"""
        return {
            "wifi_status": self.status,
            "lc_status": self.lc_status,
            "d3_status": self.d3_status,
        }

    # =========================================================================
    # SETUP WIZARD - Öffentliche API
    # =========================================================================

    @property
    def setup_active(self):
        """True solange der Setup-Wizard läuft"""
        return self._setup_state not in (_IDLE, _DONE)

    def start_setup(self):
        """Startet den WiFi Setup Wizard"""
        self._setup_state = _SCANNING
        self._setup_networks = []
        self._setup_sel = 0
        self._setup_offset = 0
        self._setup_ssid = ""
        self._setup_pw = ""
        self._setup_msg = ""
        self._setup_dirty = True
        print("WiFi Setup: Scan wird gestartet")

    def handle_setup_key(self, key_str, action, shift_active):
        """
        Interceptor-Callback: wird vom KeyboardEngine aufgerufen wenn
        key_interceptor gesetzt ist. Verarbeitet Tasteneingaben im Wizard.
        """
        if self._setup_state == _SELECT:
            self._handle_select_key(key_str)
        elif self._setup_state == _PASSWORD:
            self._handle_password_key(key_str, shift_active)
        self._setup_dirty = True

    def update_setup(self, display_feature):
        """
        Wird in der Main-Loop aufgerufen wenn setup_active True ist.
        Steuert Zustandsübergänge und Display-Updates.
        """
        # Scan-Phase: Screen zeigen, dann scannen
        if self._setup_state == _SCANNING:
            display_feature.show_wifi_setup_scanning()
            display_feature.force_refresh()
            self._do_scan()
            self._setup_dirty = True
            return

        # Verbindungsversuch
        if self._setup_state == _CONNECTING:
            display_feature.show_wifi_setup_status(
                "Connecting...", self._setup_ssid[:16])
            display_feature.force_refresh()
            self._do_connect_setup()
            # Ergebnis anzeigen
            if self._setup_state == _DONE:
                if self.enabled:
                    ip = str(wifi.radio.ipv4_address)
                    display_feature.show_wifi_setup_status("Connected!", ip[:16])
                else:
                    display_feature.show_wifi_setup_status(
                        "Fehler!", self._setup_msg[:16])
                display_feature.force_refresh()
                time.sleep(2)
            return

        # SELECT / PASSWORD: Display bei Bedarf aktualisieren
        if self._setup_dirty:
            if self._setup_state == _SELECT:
                display_feature.show_wifi_setup_select(
                    self._setup_networks,
                    self._setup_sel,
                    self._setup_offset
                )
            elif self._setup_state == _PASSWORD:
                display_feature.show_wifi_setup_password(
                    self._setup_ssid,
                    self._setup_pw
                )
            self._setup_dirty = False

    # =========================================================================
    # SETUP WIZARD - Interne Methoden
    # =========================================================================

    def _do_scan(self):
        """WiFi-Netzwerke scannen (blockierend, wenige Sekunden)"""
        try:
            wifi.radio.enabled = True
            found = {}
            for n in wifi.radio.start_scanning_networks():
                ssid = n.ssid
                if ssid and ssid not in found:
                    found[ssid] = n.rssi
            wifi.radio.stop_scanning_networks()

            # Nach Signalstärke sortieren (stärkstes zuerst)
            sorted_nets = sorted(found.items(), key=lambda x: -x[1])
            self._setup_networks = sorted_nets[:8]
            print(f"WiFi Scan: {len(self._setup_networks)} Netzwerke gefunden")
        except Exception as e:
            self._setup_networks = []
            print(f"WiFi Scan Fehler: {e}")

        if self._setup_networks:
            self._setup_state = _SELECT
        else:
            self._setup_msg = "Keine Netzwerke"
            self._setup_state = _DONE

    def _do_connect_setup(self):
        """Verbindet mit dem gewählten Netzwerk (Setup-Passwort)"""
        try:
            wifi.radio.enabled = True
            wifi.radio.connect(self._setup_ssid, self._setup_pw)
            print(f"Setup: verbunden mit {self._setup_ssid}")

            # Credentials speichern
            self._save_credentials(self._setup_ssid, self._setup_pw)

            # WiFiFeature-State aktualisieren
            self.pool = socketpool.SocketPool(wifi.radio)
            ssl_context = None
            if HomeAssistant.URL.startswith("https://"):
                ssl_context = ssl.create_default_context()
            self.requests = adafruit_requests.Session(self.pool, ssl_context)
            self.enabled = True
            self.status = "CON"
            self._setup_state = _DONE

        except Exception as e:
            err = str(e)
            print(f"Setup Verbindungsfehler: {err}")
            self._setup_msg = err[:18]
            self.status = "ERR"
            # Zurück zur Netzwerkauswahl für erneuten Versuch
            self._setup_state = _SELECT
            self._setup_dirty = True
            return

        # NTP außerhalb des Verbindungs-try: ein NTP-Fehler macht die
        # erfolgreiche WiFi-Verbindung nicht rückgängig (_setup_state bleibt _DONE)
        self._sync_ntp()

    def _handle_select_key(self, key_str):
        """Tasteneingabe in der Netzwerk-Auswahlliste"""
        if key_str == _KEY_UP:
            if self._setup_sel > 0:
                self._setup_sel -= 1
                if self._setup_sel < self._setup_offset:
                    self._setup_offset = self._setup_sel

        elif key_str == _KEY_DOWN:
            if self._setup_sel < len(self._setup_networks) - 1:
                self._setup_sel += 1
                if self._setup_sel >= self._setup_offset + 3:
                    self._setup_offset = self._setup_sel - 2

        elif key_str == _KEY_ENTER:
            self._setup_ssid = self._setup_networks[self._setup_sel][0]
            self._setup_pw = ""
            self._setup_msg = ""
            self._setup_state = _PASSWORD

        elif key_str == _KEY_CANCEL:
            # Abbrechen: Radio abschalten wenn keine aktive Verbindung besteht
            if not self.enabled:
                wifi.radio.enabled = False
                self.status = "OFF"
            self._setup_state = _DONE

    def _handle_password_key(self, key_str, shift_active):
        """Tasteneingabe im Passwort-Feld"""
        if key_str == _KEY_CANCEL:
            # Zurück zur Netzwerkauswahl
            self._setup_state = _SELECT
            return

        if key_str == _KEY_BACKSPACE:
            self._setup_pw = self._setup_pw[:-1]
            return

        if key_str == _KEY_ENTER:
            self._setup_state = _CONNECTING
            return

        # Zeichen einfügen
        if key_str in _CHAR_MAP and len(self._setup_pw) < 63:
            chars = _CHAR_MAP[key_str]
            self._setup_pw += chars[1] if shift_active else chars[0]
