import time
import math
import adafruit_lis2mdl
import adafruit_is31fl3741
from adafruit_is31fl3741.adafruit_rgbmatrixqt import Adafruit_RGBMatrixQT

THRESH = [2.5, 5, 10.00, 20.00]
HYST = 0.03  # Hysteresis in µT
LEVEL_COLORS = [0x0044ff, 0x00ff1e, 0xff6f00, 0xFF0000]
ALPHA = 0.2  # EMA smoothing factor

class EMFReader:
  def __init__(
        self,
        i2c,
        enabled: bool = True,
        debug: bool = False,
      ):
      self.mag = adafruit_lis2mdl.LIS2MDL(i2c)
      self.led_matrix = Adafruit_RGBMatrixQT(i2c, allocate=adafruit_is31fl3741.PREFER_BUFFER)
      self.led_matrix.set_led_scaling(0x33)
      self.led_matrix.global_current = 0x11
      self.led_matrix.enable = True
      self.enabled = enabled
      self.debug = debug
      self.frame = 0
      self.frame_rate_hz = 10
      self.prev_frame_tick = time.monotonic()
      self.k2_level = 0
      self.ema = self.mag_abs_uT()
      self.baseline = self.ema
      self.calibrating = False
      self.calibration_start_time = None
      self.calibration_duration_seconds = 0.0
      self.calibration_total = 0.0
      self.calibration_num_samples = 0

  def mag_abs_uT(self):
    x, y, z = self.mag.magnetic  # µT
    return math.sqrt(x*x + y*y + z*z)

  def update_k2_level(self, dev):
    # rising edges use +HYST, falling edges use -HYST
    lvl = self.k2_level
    # go up if we cross the next threshold + HYST
    while lvl < 3 and dev >= THRESH[lvl] + HYST:  # 3 means next is "20+"
        lvl += 1
    # go down if we drop below current threshold - HYST
    while lvl > 0 and dev < THRESH[lvl-1] - HYST:
        lvl -= 1

    self.k2_level = lvl
  
  def calibrate(self, now, duration: float = 10.0) -> None:
    if not self.calibrating:
      if self.debug:
          print("EMFReader: starting calibration for", duration, "seconds.")
      self.calibrating = True
      self.calibration_start_time = time.monotonic()
      self.calibration_duration_seconds = duration
      self.calibration_total = 0.0
      self.calibration_num_samples = 0

    if now - self.calibration_start_time <= self.calibration_duration_seconds:
      reading = self.mag_abs_uT()
      self.calibration_total += reading
      self.calibration_num_samples += 1

    else:
      self.baseline = self.calibration_total / self.calibration_num_samples
      self.calibrating = False 
      if self.debug:
          print("EMFReader: calibration complete. Baseline set to", self.baseline, "µT.")
  
  def draw_square(self) -> None:
    matrix = self.led_matrix

    # Clear the matrix
    matrix.fill(0x000000)

    # First frame is just a solid square
    if self.frame == 0:
        for x in range(5, 8):
            for y in range(3, 6):
                matrix.pixel(x, y, LEVEL_COLORS[self.k2_level])

    # Subsequent frames are expanding square outlines (stroke width 2)
    else:
        for x in range(5 - self.frame, 8 + self.frame):
            matrix.pixel(x, 3 - self.frame, LEVEL_COLORS[self.k2_level])
        for x in range(5 - self.frame, 7 + self.frame):
            matrix.pixel(x, 4 - self.frame, LEVEL_COLORS[self.k2_level])
        for x in range(5 - self.frame, 8 + self.frame):
            matrix.pixel(x, 5 + self.frame, LEVEL_COLORS[self.k2_level])
        for x in range(5 - self.frame, 7 + self.frame):
            matrix.pixel(x, 4 + self.frame, LEVEL_COLORS[self.k2_level])
        for y in range(3 - self.frame, 6 + self.frame):
            matrix.pixel(5 - self.frame, y, LEVEL_COLORS[self.k2_level])
        for y in range(4 - self.frame, 5 + self.frame):
            matrix.pixel(6 - self.frame, y, LEVEL_COLORS[self.k2_level])
        for y in range(3 - self.frame, 6 + self.frame):
            matrix.pixel(7 + self.frame, y, LEVEL_COLORS[self.k2_level])
        for y in range(4 - self.frame, 5 + self.frame):
            matrix.pixel(6 + self.frame, y, LEVEL_COLORS[self.k2_level])

    matrix.show()

  def update(self, now):
    if not self.enabled:
      return

    reading = self.mag_abs_uT()
    self.ema = ALPHA * reading + (1 - ALPHA) * self.ema
    deviation = max(0.0, self.ema - self.baseline)
    self.update_k2_level(deviation)

    if self.debug:
        print("EMFReader: mag =", reading, "µT, ema =", self.ema, "µT, baseline =", self.baseline, "µT, deviation =", deviation, "µT, K2 level =", self.k2_level)

    if now - self.prev_frame_tick >= 1.0 / self.frame_rate_hz:
      self.draw_square()
      self.frame = (self.frame + 1) % 7
      self.prev_frame_tick = now
