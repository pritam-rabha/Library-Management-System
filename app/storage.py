"""JSON file storage with atomic writes."""
import copy
import json
import os
import shutil
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path

from .services.errors import StorageError

REQUIRED_LISTS = ("books", "members", "transactions")


class JsonStore:
    """Single-file JSON store.

    Every write goes to a temporary file in the same directory, is flushed and
    fsynced, and then moved over the real file with os.replace(), so a crash
    cannot leave a half-written data file. The previous version is kept as
    ``<name>.bak``. Access is serialised with a lock (use one worker process).
    """

    def __init__(self, path, default_factory):
        self.path = Path(path)
        self._default_factory = default_factory
        self._lock = threading.RLock()

    # -- reading -----------------------------------------------------
    def _load(self):
        if not self.path.exists():
            data = self._default_factory()
            self._write(data)
            return data
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise StorageError(
                "The data file is corrupted and could not be read. Restore a backup or "
                "replace %s with a valid copy (a previous version may exist as %s.bak)."
                % (self.path.name, self.path.name)
            ) from exc
        except OSError as exc:
            raise StorageError("The data file could not be opened: %s" % exc.strerror) from exc
        if not isinstance(data, dict) or not all(isinstance(data.get(k), list) for k in REQUIRED_LISTS) \
                or not isinstance(data.get("settings"), dict):
            raise StorageError("The data file has an unexpected structure and was not loaded.")
        return data

    def read(self):
        """Return a fresh copy of the data (safe to modify)."""
        with self._lock:
            return self._load()

    # -- writing -----------------------------------------------------
    @contextmanager
    def transaction(self):
        """Load data, let the caller modify it, then save atomically.

        If the caller raises, nothing is written."""
        with self._lock:
            data = self._load()
            yield data
            self._write(data)

    def replace(self, data):
        """Replace the full dataset (used by restore)."""
        with self._lock:
            self._write(copy.deepcopy(data))

    def _write(self, data):
        directory = self.path.parent
        tmp_name = None
        try:
            directory.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(dir=str(directory), prefix=self.path.name + ".", suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())
            if self.path.exists():
                shutil.copy2(self.path, str(self.path) + ".bak")
            os.replace(tmp_name, self.path)
            tmp_name = None
        except (OSError, TypeError, ValueError) as exc:
            raise StorageError("The data could not be saved; no changes were made. (%s)" % exc) from exc
        finally:
            if tmp_name and os.path.exists(tmp_name):
                try:
                    os.remove(tmp_name)
                except OSError:
                    pass
