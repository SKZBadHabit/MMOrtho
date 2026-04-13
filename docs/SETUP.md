# Setup Guide

## Requirements

- Raspberry Pi Pico 2 W (RP2350)
- SSD1306 OLED display (128×64, I2C)
- Custom PCB or hand-wired 5×12 matrix + 2 thumb keys
- USB-C cable for flashing

---

## Step 1 — Flash CircuitPython

1. Download the latest **CircuitPython UF2** for Raspberry Pi Pico 2 W from:
   [circuitpython.org/board/raspberry_pi_pico2_w](https://circuitpython.org/board/raspberry_pi_pico2_w)

2. Hold the **BOOTSEL** button on the Pico 2 W and plug it into USB.
   The device mounts as `RPI-RP2`.

3. Drag & drop the `.uf2` file onto `RPI-RP2`.
   The Pico reboots and mounts as `CIRCUITPY`.

---

## Step 2 — Install Libraries

Copy the entire `libs/` folder from this repository to the `lib/` folder on `CIRCUITPY`:

```
CIRCUITPY/
└── lib/
    ├── adafruit_hid/
    ├── adafruit_httpserver/
    ├── adafruit_display_text/
    ├── adafruit_display_shapes/
    ├── adafruit_displayio_ssd1306.mpy
    ├── adafruit_connection_manager.mpy
    ├── adafruit_matrixkeypad.mpy
    ├── adafruit_requests.mpy
    ├── adafruit_ntp.mpy
    ├── adafruit_ticks.mpy
    └── asyncio/
```

---

## Step 3 — Configure the Firmware

1. Copy `firmware/config.py` to `CIRCUITPY/config.py`.

2. Edit `config.py` and set your values:

   | Setting | Description |
   |---------|-------------|
   | `HomeAssistant.URL` | Your Home Assistant IP and port |
   | `HomeAssistant.TOKEN` | Long-Lived Access Token (HA → Profile → Security) |
   | `HomeAssistant.ENTITIES` | Entity IDs to monitor on the NET tab |
   | `WeatherConfig.CITY` | Your city name for wttr.in weather |
   | `WeatherConfig.NTP_TZ_OFFSET` | UTC offset (e.g. `1` for CET, `2` for CEST) |

   > Home Assistant integration is optional — leave TOKEN empty to disable it.

---

## Step 4 — Copy Firmware Files

Copy these files/folders from `firmware/` to the root of `CIRCUITPY`:

```
CIRCUITPY/
├── boot.py
├── code.py
├── config.py          ← your edited version
├── keymap.py
├── i2cdisplaybus.py
├── features/
└── web/
```

---

## Step 5 — First Boot

Unplug and replug the keyboard (without holding any key).

The keyboard boots in **Production Mode**:
- USB drive is hidden
- USB serial is disabled
- USB HID is active — the keyboard works immediately

---

## Step 6 — WiFi Setup

1. Hold **FN** and press **,** (comma) to start the WiFi Setup Wizard.
2. The OLED display guides you through entering your SSID and password using the keyboard.
3. Credentials are saved encrypted to `/data/wifi.json` on the device.

---

## Step 7 — Web Configurator

1. Make sure WiFi is connected (NET tab shows an IP address).
2. Hold **FN** and press **E18** to start Config Mode.
3. Open a browser on any device on the same network and go to the IP shown on the OLED.
4. The Web Configurator loads — remap keys, create macros, adjust settings.

---

## Development Mode

To edit firmware files after first setup:

1. Hold **E18** and plug the keyboard into USB.
2. The keyboard boots in **Development Mode** — `CIRCUITPY` drive and USB serial are accessible.
3. Edit files normally. CircuitPython auto-restarts on save.
4. Unplug and replug (without holding E18) to return to Production Mode.
