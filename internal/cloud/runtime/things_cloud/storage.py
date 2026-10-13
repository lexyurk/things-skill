"""Owner-only local state, atomic credentials, and a process-shared lock."""

import contextlib
import fcntl
import json
import os
from pathlib import Path
import sqlite3
import tempfile

from .errors import ThingsError


def data_directory():
    if os.environ.get("THINGS_CLOUD_DATA_DIR"):
        return Path(os.environ["THINGS_CLOUD_DATA_DIR"]).expanduser().resolve()
    return Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share"))) / "things-cloud-plugin"


def private_directory(path):
    path = Path(path)
    if path.is_symlink():
        raise ThingsError("The data directory must not be a symbolic link.")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.stat().st_uid != os.getuid():
        raise ThingsError("The data directory must belong to the current user.")
    path.chmod(0o700)
    return path


def atomic_json(path, value):
    path = Path(path)
    private_directory(path.parent)
    fd, tmp = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
        dfd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def read_private_json(path):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        raise ThingsError("No account connected. Run: things-cloud connect") from None
    except OSError:
        raise ThingsError("Cannot read the private account file.") from None
    with os.fdopen(fd, encoding="utf-8") as stream:
        stat = os.fstat(stream.fileno())
        if stat.st_uid != os.getuid() or stat.st_mode & 0o077:
            raise ThingsError("Account file must belong to you with permissions 0600.")
        try:
            return json.load(stream)
        except (ValueError, UnicodeError):
            raise ThingsError("The account file is invalid. Run connect again.") from None


class Store:
    def __init__(self, directory=None):
        self.directory = private_directory(directory or data_directory())
        self.account_path = self.directory / "account.json"
        self.db_path = self.directory / "cache.sqlite3"

    @contextlib.contextmanager
    def locked(self):
        fd = os.open(self.directory / "sync.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    @contextlib.contextmanager
    def database(self):
        fd = os.open(self.db_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        os.close(fd)
        self.db_path.chmod(0o600)
        db = sqlite3.connect(self.db_path)
        db.execute("PRAGMA journal_mode=DELETE")
        db.executescript("""
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events (idx INTEGER PRIMARY KEY, body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS operations (
                id TEXT PRIMARY KEY, intent TEXT NOT NULL, changes TEXT NOT NULL,
                ancestor INTEGER NOT NULL, status TEXT NOT NULL, head INTEGER
            );
        """)
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def get(db, key, default=None):
        row = db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    @staticmethod
    def set(db, key, value):
        db.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (key, json.dumps(value, allow_nan=False)))
