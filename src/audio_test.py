# SPDX-FileCopyrightText: 2018 Kattni Rembor for Adafruit Industries
#
# SPDX-License-Identifier: MIT

import time
import array
import math
import audiocore
import board
import audiobusio
import analogbufio


def audio_test():
  """Play a 440 Hz tone on and off every second using I2S."""
  sample_rate = 8000
  tone_volume = .1  # Increase or decrease this to adjust the volume of the tone.
  frequency = 440  # Set this to the Hz of the tone you want to generate.
  length = sample_rate // frequency  # One freqency period
  sine_wave = array.array("H", [0] * length)
  for i in range(length):
      sine_wave[i] = int((math.sin(math.pi * 2 * frequency * i / sample_rate) *
                          tone_volume + 1) * (2 ** 15 - 1))

  audio = audiobusio.I2SOut(board.D6, board.D5, board.D9)

  sine_wave_sample = audiocore.RawSample(sine_wave, sample_rate=sample_rate)

  while True:
      audio.play(sine_wave_sample, loop=True)
      time.sleep(1)
      audio.stop()
      time.sleep(1)

def wave_file_test():
    """Play a wave file using I2S."""
    audio = audiobusio.I2SOut(board.D6, board.D5, board.D9)

    with open("example.wav", "rb") as wave_file:
        wave = audiocore.WaveFile(wave_file)
        audio.play(wave)
        while audio.playing:
            pass
        
def _adc_block_to_audio(
    src,
    dest,
    gain: float,
    *,
    channels: int = 1,
) -> tuple[int, int, int]:
    """Remove DC bias and scale readings into interleaved signed 16-bit samples."""
    length = len(src)
    if length == 0:
        return 0, 0, 0

    average = sum(src) // length
    out_min = 32767
    out_max = -32768
    idx = 0
    for value in src:
        sample = int((value - average) * gain)
        if sample > 32767:
            sample = 32767
        elif sample < -32768:
            sample = -32768
        for _ in range(channels):
            dest[idx] = sample
            idx += 1
        if sample < out_min:
            out_min = sample
        if sample > out_max:
            out_max = sample
    return average, out_min, out_max

def adc_passthrough_test(
    *,
    adc_pin=board.A5,
    sample_rate=16000,
    block_samples=512,
    gain=8.0,
    channel_count=2,
    debug: bool = False,
):
    """Continuously pipe an analog source on adc_pin to the I2S amplifier."""
    adc = analogbufio.BufferedIn(
        adc_pin,
        sample_rate=sample_rate,
    )
    audio = audiobusio.I2SOut(board.D6, board.D5, board.D9)

    raw_buffers = [array.array("H", [0] * block_samples) for _ in range(2)]
    channels = max(1, int(channel_count))
    frame_samples = block_samples * channels
    audio_buffers = [array.array("h", [0] * frame_samples) for _ in range(2)]
    samples = []
    for i in range(2):
        samples.append(
            audiocore.RawSample(
                audio_buffers[i],
                sample_rate=sample_rate,
                channel_count=channels,
                single_buffer=False,
            )
        )

    # Prime the pipeline with the first block before kicking off playback.
    adc.readinto(raw_buffers[0])
    avg_dc, out_min, out_max = _adc_block_to_audio(
        raw_buffers[0],
        audio_buffers[0],
        gain,
        channels=channels,
    )

    if debug:
        print(
            "adc_passthrough: block0 avg=0x{:04X} min={} max={}".format(
                avg_dc, out_min, out_max
            )
        )

    audio.play(samples[0])
    current = 0

    block_count = 0
    try:
        while True:
            next_idx = 1 - current
            adc.readinto(raw_buffers[next_idx])      # Fill the idle buffer.
            avg_dc, out_min, out_max = _adc_block_to_audio(
                raw_buffers[next_idx],
                audio_buffers[next_idx],
                gain,
                channels=channels,
            )

            if debug:
                raw_min = min(raw_buffers[next_idx])
                raw_max = max(raw_buffers[next_idx])
                print(
                    "adc_passthrough: raw_min=0x{:04X} raw_max=0x{:04X} avg=0x{:04X} "
                    "out_min={} out_max={}".format(
                        raw_min, raw_max, avg_dc, out_min, out_max
                    )
                )
                if (block_count % 16) == 0:
                    preview = list(audio_buffers[next_idx][:8])
                    print("adc_passthrough: pcm_head", preview)

            while audio.playing:
                time.sleep(0.0005)                   # Yield so playback can continue.
            audio.play(samples[next_idx])
            current = next_idx
            block_count += 1
    except KeyboardInterrupt:
        if debug:
            print("adc_passthrough: stopping")
    finally:
        try:
            audio.stop()
        except Exception:
            pass
        if hasattr(audio, "deinit"):
            try:
                audio.deinit()
            except Exception:
                pass
        for sample in samples:
            try:
                sample.deinit()
            except Exception:
                pass
        if hasattr(adc, "deinit"):
            try:
                adc.deinit()
            except Exception:
                pass

def _adc_block_to_pcm_u16(src_u16, dest_u16_view, gain):
    """
    src_u16: array('H') ADC block
    dest_u16_view: memoryview('H') into the half of the playback buffer to fill
    Converts to centered signed, applies gain, then biases to unsigned 16-bit (0..65535).
    Returns (avg_dc, out_min, out_max) in signed domain for debugging.
    """
    n = len(src_u16)
    if n == 0:
        return 0, 0, 0
    avg = sum(src_u16) // n

    out_min =  32767
    out_max = -32768
    for i in range(n):
        # center around 0, apply gain in signed space
        s = int((int(src_u16[i]) - avg) * gain)
        if s < -32768: s = -32768
        if s >  32767: s =  32767
        if s < out_min: out_min = s
        if s > out_max: out_max = s
        # bias to unsigned for RawSample('H')
        dest_u16_view[i] = (s + 0x8000) & 0xFFFF

    return avg, out_min, out_max

def adc_passthrough_looping(
    *,
    adc_pin=board.A5,
    sample_rate=16000,
    block_samples=512,      # this is the HALF buffer size (one refill quantum)
    gain=6.0,
    debug: bool = True,
):
    """
    Continuous ADC -> I2S passthrough using ONE looping RawSample and double-buffer updates.
    Keeps I2S clocks alive so MAX98357 stays awake and you hear audio.
    """
    # --- devices ---
    adc = analogbufio.BufferedIn(adc_pin, sample_rate=sample_rate)
    audio = audiobusio.I2SOut(bit_clock=board.D6, word_select=board.D5, data=board.D9)

    # --- playback buffer: two halves we alternate writing into ---
    # RawSample('H') is unsigned 16-bit; total length = 2 * block_samples (mono)
    total_samples = block_samples * 2
    playback = array.array("H", [0] * total_samples)
    # views into the lower and upper halves as unsigned 16-bit
    half0 = memoryview(playback).cast("H")[:block_samples]
    half1 = memoryview(playback).cast("H")[block_samples:]

    # working ADC buffer (one half worth of samples)
    adc_block = array.array("H", [0] * block_samples)

    # create a single RawSample, tell it we’ll mutate the buffer (double-buffered)
    sample = audiocore.RawSample(playback, sample_rate=sample_rate, single_buffer=False, channel_count=1)

    # ---- prime: fill both halves before starting I2S so the amp has clean startup data ----
    adc.readinto(adc_block)
    avg, mn, mx = _adc_block_to_pcm_u16(adc_block, half0, gain)
    adc.readinto(adc_block)
    avg, mn, mx = _adc_block_to_pcm_u16(adc_block, half1, gain)

    if debug:
        print(f"adc_passthrough(loop): primed; first samples (u16) = {list(half0[:8])}")

    # start continuous playback; I2S clocks stay running
    audio.play(sample, loop=True)

    t_half = block_samples / float(sample_rate)
    fill_lower = True
    block_count = 0

    try:
        while True:
            t0 = time.monotonic_ns()

            # 1) pull a block from ADC
            adc.readinto(adc_block)

            # 2) write it into the non-playing half
            if fill_lower:
                avg_dc, out_min, out_max = _adc_block_to_pcm_u16(adc_block, half0, gain)
            else:
                avg_dc, out_min, out_max = _adc_block_to_pcm_u16(adc_block, half1, gain)
            fill_lower = not fill_lower
            block_count += 1

            if debug and (block_count % 16 == 0):
                peek = list((half1 if fill_lower else half0)[:8])
                print(f"adc_passthrough: peek(u16)={peek}  signed_range=({out_min},{out_max})")

            # 3) pace roughly to the half-buffer duration
            elapsed = (time.monotonic_ns() - t0) / 1_000_000_000.0
            sleep_left = t_half - elapsed
            if sleep_left > 0:
                time.sleep(sleep_left * 0.9)
    except KeyboardInterrupt:
        if debug:
            print("adc_passthrough: stopping")
    finally:
        try:
            audio.stop()
        except Exception:
            pass
        for obj in (sample, audio, adc):
            if hasattr(obj, "deinit"):
                try: obj.deinit()
                except Exception: pass
