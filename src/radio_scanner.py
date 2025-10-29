import time
import random
import tinkeringtech_rda5807m
from adafruit_bus_device.i2c_device import I2CDevice

# Absolute limits for radio scan settings
MIN_FREQ = 5000  # Absolute minimum frequency in 100kHz units
MAX_FREQ = 11500  # Absolute maximum frequency in 100kHz units
MIN_SCAN_RATE = 0.2  # Minimum scan rate in jumps per second
MAX_SCAN_RATE = 100   # Maximum scan rate in jumps per second
MAX_SCAN_STEP = 100  # Maximum step size in 100kHz units
MIN_SCAN_STEP = 1    # Minimum step size in 100kHz units

class ScanMethod:
  LINEAR = "linear"
  RANDOM = "random"

class RadioScanner:
  def __init__(
      self,
      i2c,
      address=0x11,
      enabled: bool = True,
      debug: bool = False,
      method: str = ScanMethod.LINEAR,
      direction: int = 1,
      step: int = 100,
      rate: float = 70,      # jumps per minute
      seek_threshold: int = 4,
      starting_freq: int = 9000,
      min_scan_freq: int = 8700,
      max_scan_freq: int = 10800,
      volume: int = 8,
    ):
    self.radio_i2c = I2CDevice(i2c, address)
    self.freq = starting_freq
    self.rds = tinkeringtech_rda5807m.RDSParser()
    self.radio = tinkeringtech_rda5807m.Radio(self.radio_i2c, self.rds, self.freq, volume)
    self.radio.set_band("FM")
    self.radio.set_mono(True)
    self.enabled = enabled
    self.debug = debug
    self.method = method
    self.direction = direction
    self.step = step
    self.rate = rate
    self.seek_threshold = seek_threshold
    self.starting_freq = starting_freq
    self.min_scan_freq = min_scan_freq
    self.max_scan_freq = max_scan_freq
    self.volume = volume
    self.last_scan_tick = time.monotonic()

  # Public methods
  def set_freq(self, freq: int):
    if freq < self.min_scan_freq:
      self.freq = self.min_scan_freq
    elif freq > self.max_scan_freq:
      self.freq = self.max_scan_freq
    else:
      self.freq = freq
    self.radio.set_freq(self.freq)

    if self.debug:
        print("RadioScanner: frequency set to", self.freq)

  def set_method(self, method: str):
    if method in (ScanMethod.LINEAR, ScanMethod.RANDOM):
      self.method = method
    else:
      self.method = ScanMethod.LINEAR

    if self.debug:
        print("RadioScanner: scan method set to", self.method)

  def set_direction(self, direction: int):
    if direction in (1, -1):
      self.direction = direction
    else:
      self.direction = 1

    if self.debug:
        dir = "up" if self.direction == 1 else "down"
        print("RadioScanner: scan direction set to", dir)

  def set_step(self, step: int):
    if step < MIN_SCAN_STEP:
      self.step = MIN_SCAN_STEP
    elif step > MAX_SCAN_STEP:
      self.step = MAX_SCAN_STEP
    else:
      self.step = step

    if self.debug:
        print("RadioScanner: scan step set to", self.step)

  def set_rate(self, rate: float):
    if rate < MIN_SCAN_RATE:
      self.rate = MIN_SCAN_RATE
    elif rate > MAX_SCAN_RATE:
      self.rate = MAX_SCAN_RATE
    else:
      self.rate = rate

    if self.debug:
        print("RadioScanner: scan rate set to", self.rate, "jumps per second")

  def set_seek_threshold(self, threshold: int):
    self.seek_threshold = threshold

    if self.debug:
        print("RadioScanner: seek threshold set to", self.seek_threshold)

  def set_min_scan_freq(self, freq: int):
    if freq < MIN_FREQ:
      self.min_scan_freq = MIN_FREQ
    else:
      self.min_scan_freq = freq

    if self.debug:
        print("RadioScanner: minimum scan frequency set to", self.min_scan_freq)

  def set_max_scan_freq(self, freq: int):
    if freq > MAX_FREQ:
      self.max_scan_freq = MAX_FREQ
    else:
      self.max_scan_freq = freq

    if self.debug:
        print("RadioScanner: maximum scan frequency set to", self.max_scan_freq)

  def set_volume(self, volume: int):
    if volume < 0:
      self.volume = 0
    elif volume > 10:
      self.volume = 10
    else:
      self.volume = volume
    self.radio.set_volume(self.volume)

    if self.debug:
        print("RadioScanner: volume set to", self.volume)

  def get_settings(self):
    return {
      "method": self.method,
      "direction": self.direction,
      "step": self.step,
      "rate": self.rate,
      "seek_threshold": self.seek_threshold,
      "starting_freq": self.starting_freq,
      "min_scan_freq": self.min_scan_freq,
      "max_scan_freq": self.max_scan_freq,
      "volume": self.volume
    }

  def update(self, now):
    if self.enabled == False:
      return None
    
    if self.debug:
        print("RadioScanner: update called at", now)
    interval = 60 / self.rate

    if (now - self.last_scan_tick) < interval:
      if self.debug:
          print("RadioScanner: skipping scan step; only", now - self.last_scan_tick, "seconds since last scan. (interval is", interval, "seconds)")
      return None

    self.last_scan_tick = now

    if self.debug:
        print("RadioScanner: performing scan step.")

    self.scan_step()

    if self.debug:
        print("RadioScanner: scanned to frequency", self.freq)

  def scan_step(self):
    if self.method == ScanMethod.RANDOM:
      self.random_scan()
    elif self.method == ScanMethod.LINEAR:
      self.linear_scan()

  # Private methods
  def linear_scan(self):
    self.freq += self.step * self.direction
    if self.freq > self.max_scan_freq:  # Wrap around if exceeding upper limit
      self.freq = self.min_scan_freq + (self.freq - self.max_scan_freq)
    elif self.freq < self.min_scan_freq:  # Wrap around if below lower limit
      self.freq = self.max_scan_freq - (self.min_scan_freq - self.freq)
    self.radio.set_freq(self.freq)
  
  def random_scan(self):
    self.freq = random.randint(self.min_scan_freq, self.max_scan_freq)
    self.radio.set_freq(self.freq)
    