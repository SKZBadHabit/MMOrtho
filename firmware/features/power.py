# features/power.py - Power Management Feature
# Energie-Sparmodus für MMOrtho
import time
import gc
import analogio
import board
import microcontroller

from config import Timing


class PowerFeature:
    """
    Power Management Feature.
    - Energy Save Level 1: Display aus nach Inaktivität (210s)
    - Energy Save Level 2: Deep Idle nach 30min (WiFi aus, Loop 50ms)
    - Garbage Collection
    - Spannungsmessung (VSYS)
    """

    def __init__(self, display_feature, storage_feature, wifi_feature=None):
        self.display = display_feature
        self.storage = storage_feature
        self.wifi = wifi_feature

        # Timing
        self._last_activity = time.monotonic()
        self._last_gc = time.monotonic()
        self._last_voltage_read = time.monotonic()

        # State
        self.energy_save_active = False
        self.deep_idle_active = False
        self._wifi_was_enabled = False  # WiFi-Status vor Deep Idle
        self._cached_voltage = "N/A"

        # VSYS ADC Init
        self._init_voltage_monitor()

    def _init_voltage_monitor(self):
        """Initialisiert die Spannungsmessung"""
        try:
            self.vsys_adc = analogio.AnalogIn(board.VOLTAGE_MONITOR)
        except AttributeError:
            try:
                self.vsys_adc = analogio.AnalogIn(board.A3)
            except:
                self.vsys_adc = None
                print("Voltage monitor not available")

    def activity(self):
        """Registriert Benutzer-Aktivität (z.B. Tastendruck)"""
        self._last_activity = time.monotonic()

        if self.deep_idle_active:
            self._wake_up_deep_idle()
        elif self.energy_save_active:
            self._wake_up()

    def _wake_up(self):
        """Weckt das System aus Level-1 Energy Save (Display an)"""
        self.energy_save_active = False
        self.display.on()
        print("Woke up from energy save")

    def _wake_up_deep_idle(self):
        """Weckt das System aus Deep Idle (Level 2): Loop normal.
        Display bleibt aus — Level-1 Energy Save bleibt aktiv.
        WiFi bleibt getrennt — muss manuell reaktiviert werden."""
        self.deep_idle_active = False
        # energy_save_active bleibt True → Display bleibt aus
        # WiFi bleibt aus → Benutzer reaktiviert manuell per FN+WiFi

        print("Woke up from deep idle (display and WiFi stay off)")

    def get_loop_sleep(self):
        """
        Gibt die gewünschte Loop-Schlafzeit zurück.
        Deep Idle: 50ms (CPU fast idle, ~98% weniger Last)
        Normal:    1ms
        """
        return 0.05 if self.deep_idle_active else 0.001

    def check(self):
        """
        Prüft Energy Save, Deep Idle und Garbage Collection.
        Sollte in der Main-Loop aufgerufen werden.
        """
        current_time = time.monotonic()
        idle_time = current_time - self._last_activity

        # Level 1: Display aus
        if not self.energy_save_active and not self.deep_idle_active:
            if idle_time >= Timing.ENERGY_SAVE_TIMEOUT:
                self._enter_energy_save()

        # Level 2: Deep Idle nach 30min
        if self.energy_save_active and not self.deep_idle_active:
            if idle_time >= Timing.DEEP_IDLE_TIMEOUT:
                self._enter_deep_idle()

        # Garbage Collection Check
        if current_time - self._last_gc >= Timing.GC_INTERVAL:
            self._run_gc()

    def _enter_energy_save(self):
        """Level 1: Display ausschalten"""
        print("Entering energy save mode")

        # Statistiken speichern
        self.storage.force_save()

        # WiFi Status aktualisieren (für nächstes Aufwachen)
        if self.wifi and self.wifi.enabled:
            self.wifi.refresh_device_status()

        # Display ausschalten
        self.display.off()

        self.energy_save_active = True

    def _enter_deep_idle(self):
        """Level 2: Deep Idle — WiFi trennen, Loop verlangsamen"""
        print("Entering deep idle (30min inactive)")

        # WiFi-Status merken und trennen
        self._wifi_was_enabled = bool(self.wifi and self.wifi.enabled)
        if self._wifi_was_enabled:
            self.wifi.toggle()  # WiFi aus

        self.deep_idle_active = True

    def _run_gc(self):
        """Führt Garbage Collection durch"""
        free_before = gc.mem_free()
        gc.collect()
        free_after = gc.mem_free()
        print(f"GC: {free_before} -> {free_after} bytes free")
        self._last_gc = time.monotonic()

    def get_voltage(self):
        """
        Gibt die VSYS Spannung zurück (mit Caching).

        Returns:
            Spannung als String (z.B. "4.85V") oder "N/A"
        """
        current_time = time.monotonic()

        # Cache Check
        if current_time - self._last_voltage_read < Timing.VOLTAGE_REFRESH:
            return self._cached_voltage

        if self.vsys_adc is None:
            self._cached_voltage = "N/A"
            return "N/A"

        try:
            # VSYS über 3:1 Spannungsteiler
            # ADC Referenz 3.3V: VSYS = ADC * 3.3 * 3 / 65535
            adc_value = self.vsys_adc.value
            voltage = (adc_value * 3.3 * 3) / 65535
            self._cached_voltage = f"{voltage:.2f}V"
            self._last_voltage_read = current_time
            return self._cached_voltage
        except Exception as e:
            print(f"Voltage read error: {e}")
            self._cached_voltage = "ERR"
            return "ERR"

    def get_cpu_temp(self):
        """
        Gibt die CPU Temperatur zurück.

        Returns:
            Temperatur als int in Celsius
        """
        try:
            return int(microcontroller.cpu.temperature)
        except Exception:
            return 0
