import time
import random
import tinkeringtech_rda5807m
from adafruit_bus_device.i2c_device import I2CDevice

# Absolute limits for radio scan settings
MIN_SCAN_RATE = 1  # Minimum scan rate in jumps per minute
MAX_SCAN_RATE = 150   # Maximum scan rate in jumps per minute
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
      step: int = 1,
      rate: float = 100,      # jumps per minute
      seek_threshold: int = 4,
      starting_freq: int = 8700,
      min_scan_freq: int = 8700,
      max_scan_freq: int = 10800,
    ):
    self.radio_i2c = I2CDevice(i2c, address)
    self.freq = starting_freq
    self.rds = tinkeringtech_rda5807m.RDSParser()
    self.radio = tinkeringtech_rda5807m.Radio(self.radio_i2c, self.rds, self.freq)
    self.enabled = enabled
    self.debug = debug
    self.method = method
    self.direction = direction
    self.step = step
    self.rate = rate
    self.seek_threshold = seek_threshold # 0-100 percentage of (max - 1) - min RSSI
    self.starting_freq = starting_freq
    self.min_scan_freq = min_scan_freq
    self.max_scan_freq = max_scan_freq
    self.last_scan_tick = time.monotonic()
    self.signal_strength_vector = [(self.radio.freq_low + (i * 10), 0) for i in range((self.radio.freq_high - self.radio.freq_low)//10 + 1)]  # One entry per 10kHz step
    self.max_signal_strength = 0

    # Full-frequency scan flags
    self.prev_volume = 5
    self.sig_strength_scan_in_progress = False
    self.sig_strength_scan_freqs = []
    self.sig_strength_scan_index = 0
    self.sig_strength_scan_tune_pending = False
    self.sig_strength_scan_rssi_stabilization_start_time = 0.0
    self.sig_strength_scan_start_time = 0.0

  def setup(self):
    self.radio.set_mono(True)
    self.set_volume(5)  # Default volume

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

  def fill_signal_strength_vector(self):
    if not self.sig_strength_scan_in_progress:
      if self.debug:
          print("RadioScanner: starting full spectrum signal strength scan.")
      self.sig_strength_scan_freqs = [freq for freq, strength in self.signal_strength_vector if strength == 0]
      if len(self.sig_strength_scan_freqs) == 0:
        if self.debug:
          print("RadioScanner: signal strength vector already filled. Aborting scan.")
      else:
        if self.debug:
          print("RadioScanner: frequencies to be scanned:", self.sig_strength_scan_freqs)
      self.prev_volume = self.radio.volume
      self.set_volume(0)  # Mute during scan
      self.sig_strength_scan_in_progress = True
      self.sig_strength_scan_scan_index = 0
      self.sig_strength_scan_tune_pending = True
      self.sig_strength_scan_rssi_stabilization_start_time = 0.0
      self.sig_strength_scan_start_time = time.monotonic()
    else:
      if self.sig_strength_scan_index >= len(self.sig_strength_scan_freqs):
        if self.debug:
            elapsed = time.monotonic() - self.sig_strength_scan_start_time
            print("RadioScanner: signal strength scan completed in", elapsed, "seconds")
        self.sig_strength_scan_in_progress = False
        self.set_volume(self.prev_volume)
        return

      if self.sig_strength_scan_tune_pending:
        self.radio.set_freq(self.sig_strength_scan_freqs[self.sig_strength_scan_index])
        self.sig_strength_scan_tune_pending = False

      if self.radio.poll_tune():
        if self.sig_strength_scan_rssi_stabilization_start_time == 0.0:
          self.sig_strength_scan_rssi_stabilization_start_time = time.monotonic()
        if time.monotonic() - self.sig_strength_scan_rssi_stabilization_start_time >= 0.2:
          strength = self.radio.get_rssi()
          freq = self.sig_strength_scan_freqs[self.sig_strength_scan_index]
          self.signal_strength_vector[self.get_freq_index(freq)] = (freq, strength)
          self.sig_strength_scan_index += 1
          self.sig_strength_scan_rssi_stabilization_start_time = 0.0
          self.sig_strength_scan_tune_pending = True
          if self.debug:
            print("RadioScanner: set RSSI for", freq, "to", strength)




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
    if threshold < 0:
      self.seek_threshold = 0
    elif threshold > 15:
      self.seek_threshold = 15
    else:
      self.seek_threshold = threshold
    if self.debug:
        print("RadioScanner: seek threshold set to", self.seek_threshold)

  def set_min_scan_freq(self, freq: int):
    if freq < self.radio.freq_low:
      self.min_scan_freq = self.radio.freq_low
    else:
      self.min_scan_freq = freq

    if self.debug:
        print("RadioScanner: minimum scan frequency set to", self.min_scan_freq)

  def set_max_scan_freq(self, freq: int):
    if freq > self.radio.freq_high:
      self.max_scan_freq = self.radio.freq_high
    else:
      self.max_scan_freq = freq

    if self.debug:
        print("RadioScanner: maximum scan frequency set to", self.max_scan_freq)

  def set_volume(self, volume: int):
    self.radio.set_volume(volume)

    if self.debug:
        print("RadioScanner: volume set to", volume)

  def get_step_size(self):
    return self.step * self.radio.freq_steps
  
  def get_freq_index(self, freq: int):
    return (freq - self.radio.freq_low) // 10
  
  def update_signal_strength(self):
    if self.debug:
        print("RadioScanner: updating signal strength vector.")

    freq_index = self.get_freq_index(self.freq)
    strength = self.radio.get_rssi()
    self.signal_strength_vector[freq_index] = (self.freq, strength)

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
    
    if self.sig_strength_scan_in_progress:
      self.fill_signal_strength_vector()
      return None
    
    if self.debug:
        print("RadioScanner: update called at", now)
    interval = 60 / self.rate

    if (now - self.last_scan_tick) < interval:
      if self.debug:
          print("RadioScanner: skipping scan step; only", now - self.last_scan_tick, "seconds since last scan. (interval is", interval, "seconds)")
      return None

    self.last_scan_tick = now
    self.update_signal_strength()

    print("Signal strength vector:", self.signal_strength_vector)

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
    step_size = self.get_step_size()
    self.freq += step_size * self.direction
    if self.freq > self.max_scan_freq:  # Wrap around if exceeding upper limit
      self.freq = self.min_scan_freq + (self.freq - self.max_scan_freq)
    elif self.freq < self.min_scan_freq:  # Wrap around if below lower limit
      self.freq = self.max_scan_freq - (self.min_scan_freq - self.freq)
    self.radio.set_freq(self.freq)
  
  def random_scan(self):
    self.freq = random.randint(self.min_scan_freq, self.max_scan_freq)
    self.radio.set_freq(self.freq)
    