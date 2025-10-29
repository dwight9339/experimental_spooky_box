import board
import time
from device_controller import DeviceController
import asyncio
import tinkeringtech_rda5807m
import adafruit_is31fl3741
from adafruit_is31fl3741.adafruit_rgbmatrixqt import Adafruit_RGBMatrixQT
from adafruit_bus_device.i2c_device import I2CDevice

def draw_square(matrix, frame) -> None:
    # Clear the matrix
    matrix.fill(0x000000)

    # First frame is just a solid square
    if frame == 0:
        for x in range(5, 8):
            for y in range(3, 6):
                matrix.pixel(x, y, 0x0044ff)

    # Subsequent frames are expanding square outlines (stroke width 2)
    else:
        for x in range(5 - frame, 8 + frame):
            matrix.pixel(x, 3 - frame, 0x0044ff)
        for x in range(5 - frame, 7 + frame):
            matrix.pixel(x, 4 - frame, 0x0044ff)
        for x in range(5 - frame, 8 + frame):
            matrix.pixel(x, 5 + frame, 0x0044ff)
        for x in range(5 - frame, 7 + frame):
            matrix.pixel(x, 4 + frame, 0x0044ff)
        for y in range(3 - frame, 6 + frame):
            matrix.pixel(5 - frame, y, 0x0044ff)
        for y in range(4 - frame, 5 + frame):
            matrix.pixel(6 - frame, y, 0x0044ff)
        for y in range(3 - frame, 6 + frame):
            matrix.pixel(7 + frame, y, 0x0044ff)
        for y in range(4 - frame, 5 + frame):
            matrix.pixel(6 + frame, y, 0x0044ff)

    matrix.show()

def main() -> None:
    i2c = board.I2C()

    controller = DeviceController(i2c=i2c, debug=True)
    controller.initialize()
    controller.run_forever()

if __name__ == "__main__":
    main()
