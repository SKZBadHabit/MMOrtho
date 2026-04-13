# Troubleshooting

## Keyboard not recognized as HID device

**Symptom:** PC shows no keyboard after plugging in.

- Make sure you booted in **Production Mode** (no key held at plug-in).
- Verify `boot.py` is on `CIRCUITPY` root.
- Check that `adafruit_hid` library is in `lib/`.

---

## OLED display stays blank

**Symptom:** Display never lights up.

- Verify I2C wiring: SDA → GP26, SCL → GP27.
- Confirm the display address is `0x3C` (scan with `import busio; i2c = busio.I2C(...); i2c.scan()`).
- Check that `adafruit_displayio_ssd1306.mpy` is in `lib/`.

---

## WiFi not connecting

**Symptom:** WiFi icon shows disconnected, no IP on NET tab.

- Run the **WiFi Setup Wizard** again: **FN + ,**
- Ensure the SSID is 2.4 GHz (Pico 2 W does not support 5 GHz).
- Delete `/data/wifi.json` from CIRCUITPY (Development Mode) and re-run the wizard.

---

## Web Configurator not loading

**Symptom:** Browser shows "connection refused" or times out.

- WiFi must be connected first — check NET tab for an IP.
- Make sure `web/index.html` is on `CIRCUITPY/web/index.html`.
- Check `adafruit_httpserver` is in `lib/`.
- Try a different browser or disable browser extensions.

---

## Keys not registering / wrong keys

**Symptom:** Key presses are missed or wrong character appears.

- Check matrix wiring matches the pin assignments in `config.py`.
- Verify the keymap in `keymap.py` matches your physical layout.
- Use the **Web Configurator → Keymap** tab to remap keys without editing code.

---

## Home Assistant entities not showing

**Symptom:** NET tab shows `--` for entity states.

- Verify `HomeAssistant.URL` and `HomeAssistant.TOKEN` in `config.py`.
- Generate a new Long-Lived Access Token in HA: **Profile → Security → Long-Lived Access Tokens**.
- Check that entity IDs in `HomeAssistant.ENTITIES` exactly match those in HA.

---

## Firmware crash / constant reboot loop

**Symptom:** OLED flickers, keyboard constantly resets.

1. Boot into **Development Mode** (hold E18 at plug-in).
2. Open a serial terminal (115200 baud) — e.g. Thonny or `screen /dev/ttyACM0 115200`.
3. Read the traceback printed to serial.
4. Fix the offending file and save — CircuitPython restarts automatically.

---

## Out of memory (MemoryError)

**Symptom:** Serial shows `MemoryError` after boot.

- Make sure all `.py` files in `features/` are not accidentally duplicated.
- Check for runaway string concatenation in macros or display code.
- The GC interval in `config.py` (`Timing.GC_INTERVAL`) can be lowered for more frequent collection.
