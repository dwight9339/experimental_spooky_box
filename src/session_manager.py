import errno
import json
import os
import time

import adafruit_sdcard
import storage


class SessionManagerError(Exception):
    """Raised when session storage operations fail."""


class SessionManager:
    """Handles session lifecycle, directory management, and SD I/O."""

    def __init__(
        self,
        spi,
        cs,
        *,
        mount_point="/sd",
        sessions_dir_name="sessions",
        debug=True,
    ) -> None:
        self.spi = spi
        self.cs = cs
        self.mount_point = mount_point
        self.sessions_dir_name = sessions_dir_name
        self.debug = debug

        self.sdcard = None
        self.vfs = None

        self.session_active = False
        self.session_id = None
        self.session_path = None
        self._audio_path = None
        self._data_path = None
        self._audio_file = None
        self._data_file = None
        self._start_ticks = None
        self._frames_written = 0
        self._audio_bytes = 0
        self._serial = 0

    # -------------------------------------------------------------------------
    # SD card management
    # -------------------------------------------------------------------------
    def ensure_mounted(self) -> bool:
        """Mount the SD card if needed."""
        if self.vfs:
            return True

        try:
            mount = storage.getmount(self.mount_point)
        except ValueError:
            mount = None

        if mount:
            if self.debug:
                print("SessionManager: using existing mount at", self.mount_point)
            self.vfs = mount
            self.sdcard = None
            return True

        try:
            sdcard = adafruit_sdcard.SDCard(self.spi, self.cs)
            vfs = storage.VfsFat(sdcard)
            storage.mount(vfs, self.mount_point)
            self.sdcard = sdcard
            self.vfs = vfs
            if self.debug:
                print("SessionManager: mounted SD card at", self.mount_point)
            return True
        except OSError as exc:
            if self.debug:
                print("SessionManager: failed to mount SD card:", exc)
            self.sdcard = None
            self.vfs = None
            return False

    def unmount(self) -> None:
        """Unmount the SD card when idle."""
        if self.session_active:
            raise SessionManagerError("Cannot unmount while a session is active.")

        if not self.vfs:
            return

        storage.umount(self.mount_point)
        if self.debug:
            print("SessionManager: unmounted SD card.")
        self.sdcard = None
        self.vfs = None

    # -------------------------------------------------------------------------
    # Session lifecycle
    # -------------------------------------------------------------------------
    def start_session(self, session_id=None) -> str:
        """Prepare files for a new session and mark it active."""
        if self.session_active:
            raise SessionManagerError("Session already active.")

        if not self.ensure_mounted():
            raise SessionManagerError("SD card not available.")

        root = self._ensure_sessions_dir()
        session_id = session_id or self._generate_session_id()
        session_path = self._prepare_session_dir(root, session_id)

        audio_path = session_path + "/session.wav"
        data_path = session_path + "/session_data.jsonl"

        try:
            audio_file = open(audio_path, "wb")
        except OSError as exc:
            raise SessionManagerError("Unable to open audio file: {}".format(exc))

        try:
            data_file = open(data_path, "a")
        except OSError as exc:
            audio_file.close()
            raise SessionManagerError("Unable to open data file: {}".format(exc))

        self.session_active = True
        self.session_id = session_id
        self.session_path = session_path
        self._audio_path = audio_path
        self._data_path = data_path
        self._audio_file = audio_file
        self._data_file = data_file
        self._start_ticks = time.monotonic()
        self._frames_written = 0
        self._audio_bytes = 0

        if self.debug:
            print("SessionManager: started session", session_id)

        return session_id

    def stop_session(self, reason=None) -> None:
        """Close session files and write a summary."""
        if not self.session_active:
            return

        summary = {
            "session_id": self.session_id,
            "audio_bytes": self._audio_bytes,
            "frames_written": self._frames_written,
            "duration_s": None,
            "reason": reason,
        }

        if self._start_ticks is not None:
            summary["duration_s"] = time.monotonic() - self._start_ticks

        if self._audio_file:
            try:
                self._audio_file.flush()
            except OSError as exc:
                if self.debug:
                    print("SessionManager: audio flush failed during stop:", exc)
            try:
                self._audio_file.close()
            except OSError as exc:
                if self.debug:
                    print("SessionManager: audio close failed during stop:", exc)
        self._audio_file = None

        if self._data_file:
            try:
                self._data_file.flush()
            except OSError as exc:
                if self.debug:
                    print("SessionManager: data flush failed during stop:", exc)
            try:
                self._data_file.close()
            except OSError as exc:
                if self.debug:
                    print("SessionManager: data close failed during stop:", exc)
        self._data_file = None

        self._write_summary(summary)

        if self.debug:
            print("SessionManager: stopped session", self.session_id)

        self.session_active = False
        self.session_id = None
        self.session_path = None
        self._audio_path = None
        self._data_path = None
        self._start_ticks = None
        self._frames_written = 0
        self._audio_bytes = 0

    # -------------------------------------------------------------------------
    # Data append helpers
    # -------------------------------------------------------------------------
    def append_data_frame(self, payload) -> bool:
        """Append a JSON-serializable payload with a relative timestamp."""
        if not self.session_active or not self._data_file:
            return False

        elapsed = time.monotonic() - self._start_ticks if self._start_ticks else 0.0
        record = {"t": elapsed, "data": payload}

        try:
            line = json.dumps(record)
        except (TypeError, ValueError) as exc:
            raise SessionManagerError("Sensor payload not serializable: {}".format(exc))

        try:
            self._data_file.write(line)
            self._data_file.write("\n")
            self._data_file.flush()
            self._frames_written += 1
            return True
        except OSError as exc:
            self._handle_io_error(exc)
            return False

    def append_audio_chunk(self, chunk) -> bool:
        """Write raw audio bytes for the active session."""
        if not self.session_active or not self._audio_file:
            return False

        if not chunk:
            return True

        if isinstance(chunk, memoryview):
            chunk = chunk.tobytes()

        if not isinstance(chunk, (bytes, bytearray)):
            raise SessionManagerError("Audio chunk must be bytes-like.")

        try:
            written = self._audio_file.write(chunk)
        except OSError as exc:
            self._handle_io_error(exc)
            return False

        try:
            self._audio_file.flush()
        except OSError as exc:
            self._handle_io_error(exc)
            return False

        self._audio_bytes += written if written else len(chunk)
        return True

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------
    def _handle_io_error(self, exc) -> None:
        """Mark the session as faulted after an SD write failure."""
        if self.debug:
            print("SessionManager: SD write failed:", exc)
        self.stop_session(reason="io_error")
        try:
            storage.umount(self.mount_point)
        except Exception:
            pass
        self.sdcard = None
        self.vfs = None

    def _ensure_sessions_dir(self) -> str:
        """Create the root sessions directory if it does not exist."""
        root = "{}/{}".format(self.mount_point, self.sessions_dir_name)
        try:
            os.stat(root)
        except OSError:
            os.mkdir(root)
            if self.debug:
                print("SessionManager: created", root)
        return root

    def _generate_session_id(self) -> str:
        """Return a time-based session identifier with a monotonic suffix."""
        now = time.localtime()
        base = "{:04d}{:02d}{:02d}_{:02d}{:02d}{:02d}".format(
            now.tm_year,
            now.tm_mon,
            now.tm_mday,
            now.tm_hour,
            now.tm_min,
            now.tm_sec,
        )
        self._serial = (self._serial + 1) % 1000
        return "{}_{:03d}".format(base, self._serial)

    def _prepare_session_dir(self, root: str, session_id: str) -> str:
        """Create a unique directory for the session."""
        path = "{}/{}".format(root, session_id)
        suffix = 0

        while True:
            try:
                os.mkdir(path)
                break
            except OSError as exc:
                if exc.args and exc.args[0] != errno.EEXIST:
                    raise SessionManagerError(
                        "Unable to create session directory: {}".format(exc)
                    )
                suffix += 1
                path = "{}/{}_{:02d}".format(root, session_id, suffix)

        return path

    def _write_summary(self, summary) -> None:
        """Persist a JSON summary next to the session data."""
        if not self.session_path:
            return

        meta_path = self.session_path + "/session_summary.json"
        try:
            with open(meta_path, "w") as meta_file:
                meta_file.write(json.dumps(summary))
                meta_file.write("\n")
        except OSError as exc:
            if self.debug:
                print("SessionManager: failed to write summary:", exc)
