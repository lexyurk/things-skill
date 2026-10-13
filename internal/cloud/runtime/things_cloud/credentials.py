"""Read an explicitly selected local credential file without executing it."""

import os
from pathlib import Path
import shlex

from .errors import ThingsError


def read_credentials(path):
    try:
        fd = os.open(Path(path), os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, encoding="utf-8-sig") as stream:
            stat = os.fstat(stream.fileno())
            if stat.st_uid != os.getuid() or stat.st_mode & 0o077:
                raise ThingsError("Credential file must belong to you with permissions 0600.")
            values = {}
            for line in stream:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[7:]
                if "=" not in line:
                    raise ThingsError("Credential file contains an invalid assignment.")
                key, value = line.split("=", 1)
                key = key.strip().upper()
                if key in values:
                    raise ThingsError("Credential file contains duplicate assignments.")
                value = value.strip()
                if value[:1] in ("'", '"'):
                    parts = shlex.split(value, comments=True, posix=True)
                    if len(parts) != 1:
                        raise ThingsError("Credential file contains an invalid quoted value.")
                    value = parts[0]
                else:
                    value = value.split(" #", 1)[0].rstrip()
                values[key] = value
    except ThingsError:
        raise
    except (OSError, UnicodeError, ValueError):
        raise ThingsError("Unable to read credential file. Check its path, permissions, and quoting.") from None
    username = next((values[key] for key in ("THINGS_USERNAME", "THINGS_EMAIL", "USERNAME", "EMAIL") if values.get(key)), None)
    password = next((values[key] for key in ("THINGS_PASSWORD", "PASSWORD") if values.get(key)), None)
    if not username or not password:
        raise ThingsError("Credential file requires THINGS_USERNAME/THINGS_PASSWORD or USERNAME/PASSWORD.")
    return username, password
