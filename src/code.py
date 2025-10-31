import board
import time
from device_controller import DeviceController
import asyncio
import tinkeringtech_rda5807m
import adafruit_is31fl3741
from adafruit_is31fl3741.adafruit_rgbmatrixqt import Adafruit_RGBMatrixQT
from adafruit_bus_device.i2c_device import I2CDevice

def main() -> None:
    i2c = board.I2C()
    i2c = board.STEMMA_I2C()
    while not i2c.try_lock():
        time.sleep(0.01)

    try:
        addresses = i2c.scan()
        print("Found addresses:", [hex(addr) for addr in addresses])
    finally:
        i2c.unlock()
    # controller = DeviceController(i2c=i2c, debug=True)
    # controller.initialize()
    # controller.run_forever()

if __name__ == "__main__":
    main()
