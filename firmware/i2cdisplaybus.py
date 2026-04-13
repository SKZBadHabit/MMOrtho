# i2cdisplaybus.py - Display Bus Wrapper
# Kompatibilitäts-Layer für verschiedene CircuitPython Versionen

try:
    # Neuere CircuitPython Versionen (9.x+)
    from i2cdisplaybus import I2CDisplayBus
except ImportError:
    try:
        # Ältere Versionen
        from displayio import I2CDisplay as I2CDisplayBus
    except ImportError:
        # Fallback für sehr alte Versionen
        import displayio

        class I2CDisplayBus:
            def __init__(self, i2c, *, device_address, reset=None):
                self._bus = displayio.I2CDisplay(
                    i2c,
                    device_address=device_address,
                    reset=reset
                )

            def __getattr__(self, name):
                return getattr(self._bus, name)
