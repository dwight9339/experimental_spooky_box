import time, math, array, struct
import board, sdcardio, storage, analogbufio, digitalio # type: ignore
try:
    import displayio
except Exception:
    displayio = None

# ===== CONFIG (tune these) =====
SAMPLE_RATE_HZ       = 16_000         # start at 12 kHz; raise to 16 kHz after stable
DURATION_SEC         = 5               # short test capture
GAIN                 = 3.0             # reduce if you see clipping
ADC_PIN              = board.A5        # your ADC pin
WAV_FILENAME         = "radio_capture.wav"
SD_MOUNT_POINT       = "/sd"
SD_CS_PIN            = board.D10       # your SD CS pin
SD_SPI_BAUDRATE      = 16_000_000       # start at 4 MHz; raise to 8–24 MHz if stable
BLOCK_SAMPLES        = 2048            # larger block => fewer SD writes
WRITE_GROUP_BLOCKS   = 2               # batch writes (8 * 4096 samples per write)
UPDATE_HEADER_RATE   = True            # correct header to measured effective rate
PRINT_PROGRESS       = True            # light progress only
# ===============================

# Keep a global guard so TFT CS stays deasserted (prevents GC from re-enabling TFT mid-capture)
_TFT_CS_GUARD = None


def _remount_sd(
    path,
    *,
    readonly,
    debug=False,
    disable_concurrent_write_protection=False,
):
    try:
        storage.remount(
            path,
            readonly=readonly,
            disable_concurrent_write_protection=disable_concurrent_write_protection,
        )
        if debug:
            mode = "RO" if readonly else "RW"
            print(f"SD remounted {mode} at {path}")
        return True
    except Exception as exc:
        if debug:
            print("SD remount failed:", exc)
        return False


def prepare_sd_for_writes(*, mount_point=SD_MOUNT_POINT, debug=False):
    return _remount_sd(mount_point, readonly=False, debug=debug)


def handoff_sd_to_usb(
    *,
    mount_point=SD_MOUNT_POINT,
    settle_time=1.0,
    debug=False,
    disable_write_protection=False,
):
    ok = _remount_sd(
        mount_point,
        readonly=True,
        debug=debug,
        disable_concurrent_write_protection=disable_write_protection,
    )
    if ok and settle_time > 0:
        time.sleep(settle_time)
    return ok


def _force_deassert(pin):
    """Drive a device CS HIGH so it releases the shared SPI bus."""
    if pin is None:
        return None
    cs = digitalio.DigitalInOut(pin)
    cs.direction = digitalio.Direction.OUTPUT
    cs.value = True
    return cs

def mount_sd_on_shared_spi(
    *,
    cs_pin=SD_CS_PIN,
    mount_point=SD_MOUNT_POINT,
    baudrate=SD_SPI_BAUDRATE,
    pause_display=True,
    force_deassert_tft=True,
):
    """Robust mount: pause TFT refresh, hard-deassert TFT CS, mount SD at low SPI speed."""
    global _TFT_CS_GUARD
    try:
        storage.getmount(mount_point)
    except (ValueError, OSError):
        pass
    else:
        return mount_point
    display = getattr(board, "DISPLAY", None)
    prev_auto = False
    if pause_display and display is not None:
        try:
            prev_auto = getattr(display, "auto_refresh", False)
            display.auto_refresh = False
        except Exception:
            pass

    if force_deassert_tft:
        try:
            _TFT_CS_GUARD = _force_deassert(getattr(board, "TFT_CS", None))
        except Exception:
            _TFT_CS_GUARD = None

    # Optional: release displays to clear any lingering bus claims (safe no-op if none)
    if displayio is not None:
        try:
            displayio.release_displays()
        except Exception:
            pass

    try:
        spi = board.SPI()  # reuse shared bus
        sd = sdcardio.SDCard(spi, cs_pin, baudrate=baudrate)
        vfs = storage.VfsFat(sd)
        storage.mount(vfs, mount_point)
        return mount_point
    finally:
        if pause_display and display is not None:
            try:
                display.auto_refresh = prev_auto
            except Exception:
                pass

def _write_wav_header(file_obj, *, sample_rate, sample_count, num_channels=1, bits_per_sample=16):
    byte_rate = sample_rate * num_channels * bits_per_sample // 8
    block_align = num_channels * bits_per_sample // 8
    data_bytes = sample_count * block_align
    riff_size = 36 + data_bytes
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", riff_size, b"WAVE",
        b"fmt ", 16, 1, num_channels,
        sample_rate, byte_rate, block_align, bits_per_sample,
        b"data", data_bytes
    )
    file_obj.write(header)

def _u16_to_s16_centered(raw_u16, out_i16, gain):
    s = 0
    for v in raw_u16:
        s += v
    avg_dc = s // len(raw_u16)
    out_min, out_max = 32767, -32768
    for i in range(len(raw_u16)):
        centered = int(raw_u16[i]) - int(avg_dc)
        scaled = int(centered * gain)
        if scaled < -32768: scaled = -32768
        elif scaled > 32767: scaled = 32767
        out_i16[i] = scaled
        if scaled < out_min: out_min = scaled
        if scaled > out_max: out_max = scaled
    return avg_dc, out_min, out_max

def autotune_sample_rate(requested_hz, target_hz, measure_seconds=1.0):
    """
    Do a short capture to measure the effective ADC rate for 'requested_hz',
    then return a nudged request so the *effective* rate lands near target_hz.
    """
    block_samples = 2048
    blocks = max(1, int((target_hz * measure_seconds) // block_samples))
    total_samples = blocks * block_samples

    adc = analogbufio.BufferedIn(ADC_PIN, sample_rate=requested_hz)
    raw = array.array("H", [0] * block_samples)

    start_ns = time.monotonic_ns()
    for _ in range(blocks):
        adc.readinto(raw)
    elapsed = (time.monotonic_ns() - start_ns) / 1_000_000_000.0
    if hasattr(adc, "deinit"):
        adc.deinit()

    eff = total_samples / elapsed
    # If we asked for R and got eff, to hit T we should ask for R * (T/eff)
    nudged = int(round(requested_hz * (target_hz / eff)))
    print("Autotune: requested {}, measured {:.1f}, target {}, new request {}".format(
        requested_hz, eff, target_hz, nudged
    ))
    return max(1000, nudged)  # clamp to something sane

def capture_adc_to_sd(
    *,
    adc_pin=ADC_PIN,
    sample_rate=SAMPLE_RATE_HZ,
    duration_sec=DURATION_SEC,
    block_samples=BLOCK_SAMPLES,
    write_group_blocks=WRITE_GROUP_BLOCKS,
    gain=GAIN,
    filename=WAV_FILENAME,
    mount_point=SD_MOUNT_POINT,
    cs_pin=SD_CS_PIN,
    as_wav=True,
    correct_sample_rate=UPDATE_HEADER_RATE,
    debug=PRINT_PROGRESS,
    handoff_to_usb=True,
    usb_settle_time=1.0,
    disable_usb_write_protection=False,
):
    mp = mount_sd_on_shared_spi(cs_pin=cs_pin, mount_point=mount_point, baudrate=SD_SPI_BAUDRATE)
    if not prepare_sd_for_writes(mount_point=mp, debug=debug):
        raise RuntimeError("Unable to remount SD card read/write. Close host apps and try again.")
    full_path = "{}/{}".format(mp.rstrip("/"), filename)

    # Quick RW probe
    try:
        with open(full_path, "wb") as _:
            pass
    except OSError as e:
        raise OSError(
            "SD appears READ-ONLY or unwriteable. Ensure FAT/FAT32 and run a disk check."
        ) from e

    total_samples_target = int(sample_rate * duration_sec)
    blocks = math.ceil(total_samples_target / block_samples)
    total_samples = blocks * block_samples

    if debug:
        print("Mount:", mp)
        print("Saving to:", full_path)
        print(f"Plan: {duration_sec}s @ {sample_rate} Hz = {total_samples_target} samples (rounded to {total_samples})")
        print(f"Block: {block_samples} samples, grouped {write_group_blocks} per write")

    adc = analogbufio.BufferedIn(adc_pin, sample_rate=sample_rate)

    raw_buffer   = array.array("H", [0] * block_samples)
    audio_buffer = array.array("h", [0] * block_samples)
    audio_bytes  = memoryview(audio_buffer).cast("B")

    block_bytes  = block_samples * 2
    batch_bytes  = bytearray(block_bytes * write_group_blocks)
    batch_mv     = memoryview(batch_bytes)
    batch_fill   = 0
    written_samples = 0

    with open(full_path, "wb") as f:
        if as_wav:
            _write_wav_header(f, sample_rate=sample_rate, sample_count=total_samples)

        start_ns = time.monotonic_ns()

        for b in range(blocks):
            adc.readinto(raw_buffer)
            avg_dc, out_min, out_max = _u16_to_s16_centered(raw_u16=raw_buffer, out_i16=audio_buffer, gain=gain)

            # Stage into batch buffer
            batch_mv[batch_fill:batch_fill + block_bytes] = audio_bytes
            batch_fill += block_bytes
            written_samples += block_samples

            # Write once per group
            if (b + 1) % write_group_blocks == 0:
                f.write(batch_mv[:batch_fill])
                batch_fill = 0

            if debug and ((b + 1) % (write_group_blocks * 2) == 0 or (b + 1) == blocks):
                clipped = (out_min <= -32768) or (out_max >= 32767)
                print(f"block {b+1}/{blocks} avg=0x{avg_dc:04X} range=({out_min},{out_max})" + (" [CLIP]" if clipped else ""))

        # Flush remainder
        if batch_fill:
            f.write(batch_mv[:batch_fill])

        elapsed_ns = max(time.monotonic_ns() - start_ns, 1)   # ns
        elapsed = elapsed_ns / 1_000_000_000.0                # seconds as float
        effective_rate = round(written_samples / elapsed)

        if debug:
            drift = (effective_rate - sample_rate) / sample_rate
            print(
                "Done. Expected {:.2f}s, elapsed {:.5f}s -> {} Hz effective (drift {:+.3%})".format(
                    written_samples / sample_rate, elapsed, effective_rate, drift
                )
            )

        # Always keep the header honest so pitch matches what you actually captured
        if as_wav and correct_sample_rate and effective_rate != sample_rate:
            if debug:
                print("Updating WAV header to measured rate:", effective_rate)
            f.flush()
            f.seek(0)
            _write_wav_header(f, sample_rate=effective_rate, sample_count=written_samples)
            f.flush()

    if hasattr(adc, "deinit"):
        adc.deinit()

    print("Capture saved to:", full_path)
    if handoff_to_usb:
        handoff_sd_to_usb(
            mount_point=mp,
            settle_time=usb_settle_time,
            debug=debug,
            disable_write_protection=disable_usb_write_protection,
        )
    return full_path
