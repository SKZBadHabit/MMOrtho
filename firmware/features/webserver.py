# features/webserver.py - Web Configuration Interface for MMOrtho
import os
import re
import json
import gc
import asyncio
import socketpool
import wifi
from adafruit_httpserver import Server, Request, Response, POST, GET, JSONResponse, FileResponse

# Helper to load config values via regex (similar to the desktop app)
class ConfigManager:
    def __init__(self, file_path="/config.py"):
        self.file_path = file_path

    def get_all(self):
        """Reads config.py and returns a dict of values."""
        try:
            with open(self.file_path, "r") as f:
                content = f.read()
        except Exception as e:
            print(f"Config Read Error: {e}")
            return {}

        def _find_str(marker, default=""):
            # Find: MARKER = "value"  or  MARKER = 'value'
            idx = content.find(marker + ' = "')
            if idx >= 0:
                s = idx + len(marker) + 4
                e = content.find('"', s)
                return content[s:e] if e >= 0 else default
            idx = content.find(marker + " = '")
            if idx >= 0:
                s = idx + len(marker) + 4
                e = content.find("'", s)
                return content[s:e] if e >= 0 else default
            return default

        def _find_int(marker, default=0):
            idx = content.find(marker + " = ")
            if idx < 0:
                return default
            s = idx + len(marker) + 3
            e = s
            while e < len(content) and (content[e].isdigit()):
                e += 1
            try:
                return int(content[s:e]) if e > s else default
            except Exception:
                return default

        def _find_float(marker, default=0.0):
            idx = content.find(marker + " = ")
            if idx < 0:
                return default
            s = idx + len(marker) + 3
            e = s
            while e < len(content) and (content[e].isdigit() or content[e] == '.'):
                e += 1
            try:
                return float(content[s:e]) if e > s else default
            except Exception:
                return default

        def _find_bool(marker, default=True):
            idx = content.find(marker + " = ")
            if idx < 0:
                return default
            s = idx + len(marker) + 3
            chunk = content[s:s+5]
            if chunk.startswith("True"):
                return True
            if chunk.startswith("False"):
                return False
            return default

        # Parse entities block manually (no regex flags needed)
        entities = {}
        try:
            ent_start = content.find("ENTITIES = {")
            if ent_start >= 0:
                ent_end = content.find("}", ent_start)
                block = content[ent_start + 12:ent_end]
                for line in block.split("\n"):
                    line = line.strip().rstrip(",")
                    if ":" not in line:
                        continue
                    k, v = line.split(":", 1)
                    k = k.strip().strip("\"'")
                    v = v.strip().strip("\"'")
                    if k:
                        entities[k] = v
        except Exception as e:
            print(f"Entity Parse Error: {e}")

        return {
            "timing": {
                "debounce_ms":             round(_find_float("DEBOUNCE", 0.009) * 1000),
                "energy_save_timeout":     _find_int("ENERGY_SAVE_TIMEOUT", 210),
                "deep_idle_timeout":       _find_int("DEEP_IDLE_TIMEOUT", 1800),
                "gc_interval":             _find_int("GC_INTERVAL", 910),
                "display_refresh":         _find_int("DISPLAY_REFRESH", 61),
                "autoclicker_interval_ms": round(_find_float("AUTOCLICKER_INTERVAL", 0.01) * 1000),
                "autoclicker_debounce_ms": round(_find_float("AUTOCLICKER_DEBOUNCE", 0.3) * 1000),
                "voltage_refresh":         _find_int("VOLTAGE_REFRESH", 5),
            },
            "ha": {
                "url":      _find_str("URL", "http://10.0.0.8:8123"),
                "token":    _find_str("TOKEN", ""),
                "entities": entities,
            },
            "weather": {
                "city":             _find_str("CITY", "Sattledt"),
                "enabled":          _find_bool("ENABLED", True),
                "refresh_interval": _find_int("REFRESH_INTERVAL", 600),
                "ntp_tz_offset":    _find_int("NTP_TZ_OFFSET", 1),
            }
        }

    def save_all(self, data):
        """Writes values back to config.py using regex replacements."""
        try:
            with open(self.file_path, "r") as f:
                content = f.read()

            def _sub(pattern, replacement):
                nonlocal content
                content = re.sub(pattern, replacement, content)

            # Timing
            t = data.get("timing", {})
            if t:
                _sub(r'(DEBOUNCE\s*=\s*)[\d.]+', f'DEBOUNCE = {t.get("debounce_ms", 9) / 1000.0:.4f}')
                _sub(r'(ENERGY_SAVE_TIMEOUT\s*=\s*)\d+', f'ENERGY_SAVE_TIMEOUT = {t.get("energy_save_timeout", 210)}')
                _sub(r'(DEEP_IDLE_TIMEOUT\s*=\s*)\d+', f'DEEP_IDLE_TIMEOUT = {t.get("deep_idle_timeout", 1800)}')
                _sub(r'(GC_INTERVAL\s*=\s*)\d+', f'GC_INTERVAL = {t.get("gc_interval", 910)}')
                _sub(r'(DISPLAY_REFRESH\s*=\s*)\d+', f'DISPLAY_REFRESH = {t.get("display_refresh", 61)}')
                _sub(r'(AUTOCLICKER_INTERVAL\s*=\s*)[\d.]+', f'AUTOCLICKER_INTERVAL = {t.get("autoclicker_interval_ms", 10) / 1000.0:.3f}')
                _sub(r'(AUTOCLICKER_DEBOUNCE\s*=\s*)[\d.]+', f'AUTOCLICKER_DEBOUNCE = {t.get("autoclicker_debounce_ms", 300) / 1000.0:.2f}')
                _sub(r'(VOLTAGE_REFRESH\s*=\s*)\d+', f'VOLTAGE_REFRESH = {t.get("voltage_refresh", 5)}')

            # HA
            ha = data.get("ha", {})
            if ha:
                _sub(r'(URL\s*=\s*)["\'].*?["\']', f'URL = "{ha.get("url", "")}"')
                _sub(r'(TOKEN\s*=\s*)["\'].*?["\']', f'TOKEN = "{ha.get("token", "")}"')
                
                entities = ha.get("entities", {})
                ent_str = "{\n"
                for k, v in entities.items():
                    ent_str += f'        "{k}": "{v}",\n'
                ent_str += "    }"
                content = re.sub(r'ENTITIES\s*=\s*\{[^}]*\}', f'ENTITIES = {ent_str}', content, flags=re.DOTALL)

            # Weather
            w = data.get("weather", {})
            if w:
                _sub(r'(CITY\s*=\s*)["\'].*?["\']', f'CITY = "{w.get("city", "")}"')
                _sub(r'(ENABLED\s*=\s*)(True|False)', f'ENABLED = {w.get("enabled", True)}')
                _sub(r'(REFRESH_INTERVAL\s*=\s*)\d+', f'REFRESH_INTERVAL = {w.get("refresh_interval", 600)}')
                _sub(r'(NTP_TZ_OFFSET\s*=\s*)\d+', f'NTP_TZ_OFFSET = {w.get("ntp_tz_offset", 1)}')

            with open(self.file_path, "w") as f:
                f.write(content)
            return True
        except Exception as e:
            print(f"Config Save Error: {e}")
            return False


class KeymapManager:
    def __init__(self, file_path="/keymap.py"):
        self.file_path = file_path

    def get_all(self):
        try:
            with open(self.file_path, 'r') as f:
                content = f.read()
            return {
                "0": self._parse_layer(content, "LAYER_BASE"),
                "1": self._parse_layer(content, "LAYER_FN"),
            }
        except Exception as e:
            print(f"Keymap Load Error: {e}")
            return {"0": {}, "1": {}}

    def _parse_layer(self, content, layer_name):
        start = content.find(layer_name + " = {")
        if start < 0:
            return {}
        end = content.find("\n}", start)
        if end < 0:
            return {}
        block = content[start:end + 2]
        result = {}
        for line in block.split('\n'):
            # Match lines with a quoted key ID like "111":
            idx = line.find('"')
            if idx < 0:
                continue
            end_q = line.find('"', idx + 1)
            if end_q < 0:
                continue
            key_id = line[idx + 1:end_q]
            colon_idx = line.find(':', end_q)
            if colon_idx < 0:
                continue
            val = line[colon_idx + 1:].split('#')[0].strip().rstrip(', \t')
            # Accept numeric-only keys or 3-char keys starting with a digit
            if val and (key_id.isdigit() or (len(key_id) == 3 and key_id[0].isdigit())):
                result[key_id] = val
        return result

    def save_all(self, data):
        # data: {"0": {"111": "Keycode.ESCAPE", ...}, "1": {...}}
        try:
            with open(self.file_path, 'r') as f:
                content = f.read()
            # Process LAYER_FN first (appears later in file), then LAYER_BASE
            for layer_idx, layer_name in [("1", "LAYER_FN"), ("0", "LAYER_BASE")]:
                changes = data.get(layer_idx, {})
                if not changes:
                    continue
                start = content.find(layer_name + " = {")
                if start < 0:
                    continue
                end_block = content.find("\n}", start) + 2
                block = content[start:end_block]
                for key_id, new_value in changes.items():
                    pattern = '"' + key_id + '":'
                    idx = block.find(pattern)
                    if idx < 0:
                        continue
                    val_start = idx + len(pattern)
                    while val_start < len(block) and block[val_start] in ' \t':
                        val_start += 1
                    val_end = val_start
                    while val_end < len(block) and block[val_end] not in ',\n#':
                        val_end += 1
                    while val_end > val_start and block[val_end - 1] in ' \t':
                        val_end -= 1
                    block = block[:val_start] + new_value + block[val_end:]
                content = content[:start] + block + content[end_block:]
            with open(self.file_path, 'w') as f:
                f.write(content)
            return True
        except Exception as e:
            print(f"Keymap Save Error: {e}")
            return False


class MacroManager:
    """Simple CRUD helper for /data/macros.json."""
    FILE = "/data/macros.json"

    def get_all(self):
        try:
            with open(self.FILE, "r") as f:
                return json.load(f)
        except OSError:
            return []
        except Exception as e:
            print(f"Macro Read Error: {e}")
            return []

    def save_all(self, macros):
        try:
            with open(self.FILE, "w") as f:
                json.dump(macros, f)
            return True
        except Exception as e:
            print(f"Macro Save Error: {e}")
            return False


class WebServerFeature:
    def __init__(self, wifi_feat, storage_feat, macro_engine=None):
        self.wifi_feat = wifi_feat
        self.storage_feat = storage_feat
        self.macro_engine = macro_engine   # optional: for reload-after-save
        self.config_mgr = ConfigManager()
        self.keymap_mgr = KeymapManager()
        self.macro_mgr  = MacroManager()
        self.server = None
        self.active = False
        self._port = 80
        # Deferred writes: Handler antwortet sofort, Datei wird nach dem nächsten await geschrieben
        self._pending_keymap = None
        self._pending_config = None
        self._pending_macros = None

    def start(self):
        if not wifi.radio.connected:
            print("Webserver: WiFi not connected, cannot start.")
            return False

        # Stop any previous server instance cleanly before creating a new one
        if self.server:
            try:
                self.server.stop()
            except Exception:
                pass
            self.server = None

        try:
            pool = socketpool.SocketPool(wifi.radio)
            self.server = Server(pool, "/web", debug=False)
            self._register_routes()
            self.server.start(str(wifi.radio.ipv4_address), self._port)
            self.active = True
            print(f"Webserver active at http://{wifi.radio.ipv4_address}")
            return True
        except Exception as e:
            print(f"Webserver start error: {e}")
            self.server = None
            self.active = False
            return False

    def stop(self):
        self.active = False
        if self.server:
            try:
                self.server.stop()
            except Exception:
                pass
            self.server = None
        print("Webserver stopped.")

    def _register_routes(self):
        # --- Static Content ---
        @self.server.route("/", GET)
        def index(request: Request):
            return FileResponse(request, "index.html", root_path="/web")

        @self.server.route("/web/logo.png", GET)
        def logo(request: Request):
            return FileResponse(request, "logo.png", root_path="/web")

        # --- API Routes ---
        @self.server.route("/api/config", GET)
        def get_config(request: Request):
            return JSONResponse(request, self.config_mgr.get_all())

        @self.server.route("/api/config", POST)
        def post_config(request: Request):
            try:
                self._pending_config = request.json()
                return JSONResponse(request, {"success": True})
            except Exception as e:
                return JSONResponse(request, {"success": False, "error": str(e)}, status=400)

        @self.server.route("/api/stats", GET)
        def get_stats(request: Request):
            stats = {
                "alltime_keypress": self.storage_feat.alltime_keypress,
                "alltime_runtime": self.storage_feat.alltime_runtime,
                "current_keypress": self.storage_feat.current_keypress,
                "live_runtime": self.storage_feat.get_live_runtime(),
                "ip": str(wifi.radio.ipv4_address),
            }
            return JSONResponse(request, stats)

        @self.server.route("/api/wifi/scan", GET)
        def wifi_scan(request: Request):
            networks = []
            for n in wifi.radio.start_scanning_networks():
                if n.ssid:
                    networks.append({"ssid": n.ssid, "rssi": n.rssi})
            wifi.radio.stop_scanning_networks()
            networks.sort(key=lambda x: x["rssi"], reverse=True)
            return JSONResponse(request, networks[:10])

        @self.server.route("/api/wifi/connect", POST)
        def wifi_connect(request: Request):
            try:
                data = request.json()
                ssid = data.get("ssid")
                pw = data.get("password")
                # Use wifi_feat to save and connect
                self.wifi_feat._save_credentials(ssid, pw)
                # We return success immediately, the actual connection
                # might take a moment or requires a reboot
                return JSONResponse(request, {"success": True, "message": "Credentials saved. Please reboot to connect."})
            except Exception as e:
                return JSONResponse(request, {"success": False, "error": str(e)})

        @self.server.route("/api/readme", GET)
        def get_readme(request: Request):
            try:
                with open("/README.md", "r") as f:
                    content = f.read()
                return Response(request, content, content_type="text/plain; charset=utf-8")
            except Exception as e:
                return Response(request, f"# MMOrtho\n\nREADME not found: {e}",
                                content_type="text/plain; charset=utf-8")

        @self.server.route("/api/keymap", GET)
        def get_keymap(request: Request):
            return JSONResponse(request, self.keymap_mgr.get_all())

        @self.server.route("/api/keymap", POST)
        def post_keymap(request: Request):
            try:
                self._pending_keymap = request.json()
                return JSONResponse(request, {"success": True})
            except Exception as e:
                return JSONResponse(request, {"success": False, "error": str(e)}, status=400)

        @self.server.route("/api/macros", GET)
        def get_macros(request: Request):
            return JSONResponse(request, self.macro_mgr.get_all())

        @self.server.route("/api/macros", POST)
        def post_macros(request: Request):
            try:
                self._pending_macros = request.json()
                return JSONResponse(request, {"success": True})
            except Exception as e:
                return JSONResponse(request, {"success": False, "error": str(e)}, status=400)

    async def run_async(self):
        """Main loop task for the webserver.
        sleep(0) yields to main loop after every poll so keypresses stay snappy.
        Deferred writes: POST handlers antworten sofort, Datei wird hier nach dem yield geschrieben.
        Only polls when config mode is active (self.active=True).
        """
        while True:
            if self.active and self.server:
                try:
                    self.server.poll()
                except Exception as e:
                    print(f"Webserver Poll Error: {e}")
                await asyncio.sleep(0)   # yield → Keyboard bekommt CPU, Response ist bereits raus

                # Deferred file writes (nach yield, Response bereits gesendet)
                if self._pending_keymap is not None:
                    self.keymap_mgr.save_all(self._pending_keymap)
                    self._pending_keymap = None
                if self._pending_config is not None:
                    self.config_mgr.save_all(self._pending_config)
                    self._pending_config = None
                if self._pending_macros is not None:
                    self.macro_mgr.save_all(self._pending_macros)
                    if self.macro_engine:
                        self.macro_engine.reload()
                    self._pending_macros = None
            else:
                await asyncio.sleep(0.05)  # idle: check every 50ms, minimal overhead
