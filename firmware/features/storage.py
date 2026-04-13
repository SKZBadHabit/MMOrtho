# features/storage.py - Persistent Storage Feature
# Statistik-Speicherung für Runtime und Keypresses (JSON-basiert)
import time
import microcontroller
import json
import os

from config import Storage


class StorageFeature:
    """
    Verwaltet persistente Speicherung von Statistiken.
    - Runtime (in Minuten)
    - Keypresses (Gesamtanzahl)
    - JSON-basiert für strukturierte Daten
    """

    def __init__(self):
        # Alltime Stats (aus Dateien geladen)
        self.alltime_runtime = 0
        self.alltime_keypress = 0

        # Current Session Stats
        self.current_runtime = 0
        self.current_keypress = 0

        # Tracking für inkrementelles Speichern
        self._last_saved_keypress = 0
        self._last_save_time = time.monotonic()
        self._session_start = time.monotonic()  # Für Echtzeit-Runtime

        # Sicherstellen dass data/ Ordner existiert
        self._ensure_data_dir()

        # Hinweis: load() wird extern in code.py aufgerufen (nach __init__),
        # damit der Aufrufer den Ladevorgang kontrollieren kann.

    def _ensure_data_dir(self):
        """Stellt sicher, dass data/ Ordner existiert"""
        try:
            # Prüfen ob Ordner existiert
            try:
                os.stat(Storage.DATA_DIR)
                print(f"Data directory exists: {Storage.DATA_DIR}")
            except OSError:
                # Ordner existiert nicht, erstellen
                os.mkdir(Storage.DATA_DIR)
                print(f"Created data directory: {Storage.DATA_DIR}")
        except Exception as e:
            print(f"Could not create data directory: {e}")

    def _migrate_legacy_files(self):
        """Migriert alte TXT-Dateien zu neuem JSON-Format"""
        runtime = 0
        keypress = 0

        # Versuche alte runtime.txt zu lesen
        try:
            with open(Storage.RUNTIME_FILE_LEGACY, "r") as f:
                runtime = int(f.read())
            print(f"Migrated runtime from legacy file: {runtime} min")
        except:
            pass

        # Versuche alte keypress.txt zu lesen
        try:
            with open(Storage.KEYPRESS_FILE_LEGACY, "r") as f:
                keypress = int(f.read())
            print(f"Migrated keypress from legacy file: {keypress}")
        except:
            pass

        # Wenn Daten gefunden wurden, speichern und alte Dateien löschen
        if runtime > 0 or keypress > 0:
            self.alltime_runtime = runtime
            self.alltime_keypress = keypress
            self._save_json()
            print("Migration to JSON completed!")

            # Legacy-Dateien löschen (optional)
            try:
                os.remove(Storage.RUNTIME_FILE_LEGACY)
                os.remove(Storage.KEYPRESS_FILE_LEGACY)
                print("Legacy files deleted")
            except:
                pass

    def load(self):
        """Lädt gespeicherte Statistiken aus JSON"""
        try:
            with open(Storage.STATS_FILE, "r") as f:
                data = json.load(f)
                self.alltime_runtime = data.get("runtime", 0)
                self.alltime_keypress = data.get("keypress", 0)
            print(f"Loaded stats: {self.alltime_runtime} min, {self.alltime_keypress} keys")
        except OSError:
            # Datei existiert nicht - versuche Migration von alten Dateien
            print("Stats file not found, checking for legacy files...")
            self._migrate_legacy_files()
        except Exception as e:
            print(f"Could not load stats: {e}")
            self.alltime_runtime = 0
            self.alltime_keypress = 0

    def _save_json(self):
        """Schreibt Statistiken in JSON-Datei"""
        try:
            data = {
                "runtime": self.alltime_runtime,
                "keypress": self.alltime_keypress,
                "version": "4.1"
            }
            with open(Storage.STATS_FILE, "w") as f:
                json.dump(data, f)
            return True
        except OSError as e:
            print(f"Filesystem read-only: {e}")
            return False

    def save(self):
        """
        Speichert Statistiken alle 5 Minuten (300s) um Flash-Writes zu reduzieren.
        Flash-Schreibvorgänge blockieren kurz (~100-500ms).
        """
        current_time = time.monotonic()
        elapsed = current_time - self._last_save_time

        # Nur alle 5 Minuten speichern (reduziert Flash-Wear und Blocking)
        if elapsed < 300:
            return False

        try:
            # Live Runtime für diesen Save-Zeitpunkt
            self.current_runtime = self.get_live_runtime()

            # Minuten seit letztem Save für alltime
            minutes_elapsed = int(elapsed // 60)
            self.alltime_runtime += minutes_elapsed

            # Keypresses delta berechnen
            keypress_delta = self.current_keypress - self._last_saved_keypress

            # Nur schreiben wenn es Änderungen gab
            if minutes_elapsed > 0 or keypress_delta > 0:
                self.alltime_keypress += keypress_delta
                self._last_saved_keypress = self.current_keypress

                # In JSON-Datei schreiben
                if self._save_json():
                    print(f"Saved: {self.alltime_runtime} min, {self.alltime_keypress} keys")

            # Zeit aktualisieren
            self._last_save_time = current_time

            return True

        except Exception as e:
            print(f"Save error: {e}")
            return False

    def force_save(self):
        """Erzwingt sofortiges Speichern (für Power Save / Reset)"""
        self._last_save_time = 0  # Reset timer
        return self.save()

    def increment_keypress(self):
        """Zählt einen Tastendruck"""
        self.current_keypress += 1

    def get_live_runtime(self):
        """Gibt die aktuelle Session-Runtime in Minuten zurück (Echtzeit)"""
        elapsed = time.monotonic() - self._session_start
        return int(elapsed // 60)

    def get_stats(self):
        """Gibt alle Statistiken zurück"""
        return {
            "current_runtime": self.current_runtime,
            "current_keypress": self.current_keypress,
            "alltime_runtime": self.alltime_runtime,
            "alltime_keypress": self.alltime_keypress,
        }

    def save_and_reset(self):
        """Speichert und führt System-Reset durch"""
        self.force_save()
        microcontroller.reset()
