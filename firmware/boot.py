import digitalio
import board
import storage
import usb_cdc
import usb_hid

switch = digitalio.DigitalInOut(board.GP9)
switch.direction = digitalio.Direction.INPUT
switch.pull = digitalio.Pull.UP

# Pull-Up Logik: switch.value = True (nicht gedrückt), False (gedrückt)
# Production Mode: Schalter NICHT gedrückt → kein USB-Laufwerk
# Dev Mode: Schalter gedrückt → USB-Laufwerk bleibt
if switch.value:
    storage.disable_usb_drive()
    usb_cdc.enable(console=False)
    usb_hid.enable(
    (usb_hid.Device.KEYBOARD,
     usb_hid.Device.MOUSE,
     usb_hid.Device.CONSUMER_CONTROL))

