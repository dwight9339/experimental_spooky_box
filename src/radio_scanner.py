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

class RadioScanSettings:
  def __init__(
    self,
    method: str = ScanMethod.LINEAR,
    direction: int = 1,
    step: int = 10,
    rate: float = 0.2,
    seek_threshold: int = 4,
    starting_freq: int = 9000,
    min_scan_freq: int = 8700,
    max_scan_freq: int = 10800,
    volume: int = 10
  ):
    self.method = method
    self.direction = direction
    self.step = step
    self.rate = rate
    self.seek_threshold = seek_threshold
    self.starting_freq = starting_freq
    self.min_scan_freq = min_scan_freq
    self.max_scan_freq = max_scan_freq
    self.volume = volume

    self.sanitize_settings()

  def to_dict(self):
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
  
  def sanitize_value(self, key, value):
    if key == "method" and value not in (ScanMethod.LINEAR, ScanMethod.RANDOM):
      return ScanMethod.LINEAR
    if key == "direction" and value not in (1, -1):
      return 1
    if key == "step":
      if value < MIN_SCAN_STEP:
        return MIN_SCAN_STEP
      elif value > MAX_SCAN_STEP:
        return MAX_SCAN_STEP
    if key == "rate":
      if value < MIN_SCAN_RATE:
        return MIN_SCAN_RATE
      elif value > MAX_SCAN_RATE:
        return MAX_SCAN_RATE
    if key == "starting_freq":
      if value < self.min_scan_freq:
        return self.min_scan_freq
      elif value > self.max_scan_freq:
        return self.max_scan_freq
    if key == "min_scan_freq" and value < MIN_FREQ:
      return MIN_FREQ
    if key == "max_scan_freq" and value > MAX_FREQ:
      return MAX_FREQ
    if key == "volume":
      if value < 0:
        return 0
      elif value > 10:
        return 10
    return value
  
  def sanitize_settings(self):
    for key in self.to_dict().keys():
      value = getattr(self, key)
      sanitized_value = self.sanitize_value(key, value)
      setattr(self, key, sanitized_value)
  
  def set(self, key, value):
    if hasattr(self, key):
      sanitized_value = self.sanitize_value(key, value)
      setattr(self, key, sanitized_value)

  def update_from_dict(self, settings_dict):
    for key, value in settings_dict.items():
      if hasattr(self, key):
        sanitized_value = self.sanitize_value(key, value)
          
        setattr(self, key, sanitized_value)

class RadioScanner:
  def __init__(self, i2c, address=0x11, settings: RadioScanSettings = None):
    if settings is None:
      settings = RadioScanSettings(
        method=ScanMethod.LINEAR,
        direction=1,
        step=10,
        rate=0.2,
        seek_threshold=4,
        min_scan_freq=8700,
        max_scan_freq=10800
      )

    self.rds = tinkeringtech_rda5807m.RDSParser()
    self.radio_i2c = I2CDevice(i2c, address)
    self.freq = settings.starting_freq
    self.radio = tinkeringtech_rda5807m.Radio(self.radio_i2c, self.rds, self.freq, settings.volume)
    self.radio.set_band("FM")
    self.last_scan_tick = time.monotonic()

  def linear_scan(self, settings: RadioScanSettings):
    self.freq += settings.step * settings.direction
    if self.freq > settings.max_scan_freq:  # Wrap around if exceeding upper limit
      self.freq = settings + (self.freq - settings.max_scan_freq)
    elif self.freq < settings.min_scan_freq:  # Wrap around if below lower limit
      self.freq = settings.max_scan_freq - (settings.min_scan_freq - self.freq)
    self.radio.set_freq(self.freq)
    return self.freq
  
  def random_scan(self, settings: RadioScanSettings):
    self.freq = random.randint(settings.min_scan_freq, settings.max_scan_freq)
    self.radio.set_freq(self.freq)
    return self.freq
    
  def update(self, now, settings: RadioScanSettings):
    interval = 60 / settings.rate
    print("Scan interval:", interval)
    print("Time since last scan tick:", now - self.last_scan_tick)
    if (now - self.last_scan_tick) < interval:
      return None

    self.last_scan_tick = now

    if settings.method == ScanMethod.RANDOM:
      frequency = self.random_scan(settings)
    elif settings.method == ScanMethod.LINEAR:
      frequency = self.linear_scan(settings)

    return frequency