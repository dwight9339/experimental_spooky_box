import time
import random
import tinkeringtech_rda5807m
from adafruit_bus_device.i2c_device import I2CDevice
from enum import Enum

class ScanMethod(Enum):
  LINEAR = 1
  RANDOM = 2

MIN_FREQ_FM = 8700  # 87.0 MHz
MAX_FREQ_FM = 10800  # 108.0 MHz
MIN_SCAN_RATE = 0.2  # Minimum scan rate in jumps per second
MAX_SCAN_RATE = 100   # Maximum scan rate in jumps per second
MAX_SCAN_STEP = 100  # Maximum step size in 100kHz units
MIN_SCAN_STEP = 1    # Minimum step size in 100kHz units
DEFAULT_SCAN_METHOD =  ScanMethod.LINEAR

class RadioScanner:
  def __init__(self, i2c, address=0x11):
    self.rds = tinkeringtech_rda5807m.RDSParser()
    self.radio_i2c = I2CDevice(i2c, address)
    self.freq = MIN_FREQ_FM
    self.volume = 5
    self.linear_scan_direction = 1  # 1 for up, -1 for down
    self.step = 10  # Default step size in 100kHz units
    self.rate = 0.1  # Default rate in seconds
    self.seek_threshold = 5  # Default seek threshold
    self.scan_method = DEFAULT_SCAN_METHOD
    self.radio = tinkeringtech_rda5807m.Radio(self.radio_i2c, self.rds, self.freq, self.volume)
    self.radio.set_band("FM")
    print("Radio initialized at frequency:", self.freq)

  def set_band(self, band):
    self.radio.set_band(band)

  def set_volume(self, volume):
    self.volume = volume
    self.radio.set_volume(volume)
    time.sleep(0.1)  # Allow time for the volume to set

  def set_step(self, step):
    val = step
    if val < MIN_SCAN_STEP:
      step = MIN_SCAN_STEP
    elif val > MAX_SCAN_STEP:
      step = MAX_SCAN_STEP
    self.step = step

  def set_rate(self, rate):
    val = rate
    if val < MIN_SCAN_RATE:
      rate = MIN_SCAN_RATE
    elif val > MAX_SCAN_RATE:
      rate = MAX_SCAN_RATE
    self.rate = val

  def set_seek_threshold(self, threshold):
    self.seek_threshold = threshold
    self.radio.set_seek_threshold(threshold)

  def linear_scan(self):
    self.freq += self.step * self.linear_scan_direction
    if self.freq > MAX_FREQ_FM:  # Wrap around if exceeding upper limit
      self.freq = MIN_FREQ_FM + (self.freq - MAX_FREQ_FM)
    elif self.freq < MIN_FREQ_FM:  # Wrap around if below lower limit
      self.freq = MAX_FREQ_FM - (MIN_FREQ_FM - self.freq)
    self.radio.set_freq(self.freq)
    return self.freq
  
  def random_scan(self):
    self.freq = random.randint(MIN_FREQ_FM, MAX_FREQ_FM)
    self.radio.set_freq(self.freq)
    return self.freq
    