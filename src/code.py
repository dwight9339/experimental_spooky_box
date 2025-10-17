import board
from radio_scanner import RadioScanner
from adafruit_bus_device.i2c_device import I2CDevice


def main():
    # Initialize i2c bus
    # If your board does not have STEMMA_I2C(), change as appropriate.
    i2c = board.STEMMA_I2C()
    print("I2C bus initialized.")

    scanner = RadioScanner(i2c)
    scanner.set_volume(0)  # Set initial volume
    scanner.set_rate(0.2)  # Set scan rate to 0.2 seconds

    # while True:
    #     freq = scanner.linear_scan()
    #     print("Tuned to frequency:", freq)

if __name__ == "__main__":
    main()