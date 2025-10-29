import time
import board
from radio_scanner import RadioScanner
from emf_reader import EMFReader

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
        debug: bool = False,
    ) -> None:
        self.board = board_module
        self.i2c = i2c or self.board.STEMMA_I2C()
        self.debug = debug

        self.radio_scanner = RadioScanner(self.i2c, debug=self.debug)
        self.emf_reader = EMFReader(self.i2c, debug=self.debug)

    def initialize(self) -> None:
        """Apply default configuration for all managed peripherals."""
        if self.debug:
            print("DeviceController: initializing subsystems.")
        
        self.emf_reader.calibrate(time.monotonic(), duration=5.0)

    def loop(self) -> None:
        now = time.monotonic()

        self.radio_scanner.update(now)
        self.emf_reader.update(now)

    def run_forever(self) -> None:
        if self.debug:
            print("DeviceController: entering run loop.")

        while True:
            self.loop()
            time.sleep(0.01)
