import time
import board
from radio_scanner import RadioScanner, ScanMethod, RadioScanSettings

class Settings:
    def __init__(self) -> None:
        self.enable_radio_scanning: bool = True
        self.radio_scan_settings = RadioScanSettings(
            method=ScanMethod.LINEAR,
            direction=1,
            step=10,
            rate=70,
            seek_threshold=4,
            starting_freq=8700,
            min_scan_freq=8700,
            max_scan_freq=10800,
            volume=10
        )

class DeviceController:
    """Coordinates hardware services for the Experimental Spooky Box.

    This initial version wires up the radio scanner and exposes hooks for the
    eventual cooperative scheduler. As the project grows, additional services
    (UI, session logging, sensors, indicators, etc.) can plug into this class.
    """

    def __init__(
        self,
        *,
        board_module=board,
        i2c=None,
        debug: bool = True,
    ) -> None:
        self.board = board_module
        self.i2c = i2c or self.board.STEMMA_I2C()
        self.debug = debug

        self.settings = Settings()

        self.radio_scanner = RadioScanner(self.i2c)

    def initialize(self) -> None:
        """Apply default configuration for all managed peripherals."""
        if self.debug:
            print("DeviceController: initializing subsystems.")


    def enable_radio_scanner(self) -> None:
        self.settings.enable_radio_scanning = True
        if self.debug:
            print("DeviceController: radio scanning enabled.")

    def disable_radio_scanner(self) -> None:
        self.settings.enable_radio_scanning = False
        if self.debug:
            print("DeviceController: radio scanning disabled.")

    def update_radio_scan_settings(self, settings: dict) -> None:
        self.settings.radio_scan_settings.update_from_dict(settings)
        if self.debug:
            print("DeviceController: updated radio scan settings:", settings)

    def loop(self):
        now = time.monotonic()
        frequency = self.radio_scanner.freq

        if self.settings.enable_radio_scanning:
            print("Updating radio scanner...")
            frequency = self.radio_scanner.update(now, self.settings.radio_scan_settings)

        if self.debug:
            print("DeviceController: tuned to frequency:", frequency)

        return

    def run_forever(self) -> None:
        """Blocking convenience runner for simple deployments."""
        if self.debug:
            print("DeviceController: entering run loop.")

        while True:
            self.loop()
            time.sleep(0.01)
