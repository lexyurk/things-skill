"""History replay and deliberately bounded write plans for Things entities."""

import copy
from datetime import date, datetime, time, timezone
import hashlib
import re
import uuid
import xml.etree.ElementTree as ET
import zlib

from .errors import ThingsError

ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
TASK_KINDS = {"Task", "Task3", "Task4", "Task6", "Task7"}
LEGACY_KINDS = {"Task", "Task3", "Task4", "Area2", "Tag3", "ChecklistItem", "ChecklistItem2", "Tombstone"}
REFERENCE_FIELDS = {"pr", "ar", "agr", "tg", "rt", "ts", "pn"}
STATUS = {"open": 0, "canceled": 2, "completed": 3}
TYPES = {"task": 0, "project": 1, "heading": 2}


def encode_id(raw):
    zeros = len(raw) - len(raw.lstrip(b"\0"))
    value = int.from_bytes(raw, "big")
    chars = []
    while value:
        value, remainder = divmod(value, 58)
        chars.append(ALPHABET[remainder])
    return "1" * zeros + "".join(reversed(chars))


def valid_id(value):
    if not isinstance(value, str) or not value or len(value) > 22:
        return False
    number = 0
    for char in value:
        if char not in ALPHABET:
            return False
        number = number * 58 + ALPHABET.index(char)
    zeros = len(value) - len(value.lstrip("1"))
    size = (number.bit_length() + 7) // 8
    if zeros + size != 16:
        return False
    return encode_id(number.to_bytes(16, "big")) == value


def new_id():
    return encode_id(uuid.uuid4().bytes)


def canonical_id(value):
    if valid_id(value):
        return value
    if not isinstance(value, str) or not value:
        raise ThingsError("Malformed identifier in cloud history.")
    # Legacy identifiers are hashed byte-exactly, including ACTIONGROUP-.
    raw = value.encode("utf-8")
    if re.fullmatch(r"[0-9A-Fa-f-]{36}-[0-9]{8}", value):
        raw = hashlib.sha1(raw[:36]).digest()[:16] + raw[36:]
    return encode_id(hashlib.sha1(raw).digest()[:16])


def require_id(value):
    if not valid_id(value):
        raise ThingsError("Use the full canonical Things ID returned by list or get.")
    return value


def day_timestamp(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ThingsError("Dates must be calendar dates in YYYY-MM-DD format.")
    try:
        day = date.fromisoformat(value)
        return int(datetime.combine(day, time(), timezone.utc).timestamp())
    except ValueError:
        raise ThingsError("Invalid calendar date.") from None


def day_string(value):
    return datetime.fromtimestamp(value, timezone.utc).date().isoformat() if value is not None else None


def text(value, label, nonempty=False):
    if not isinstance(value, str) or (nonempty and not value.strip()):
        raise ThingsError(f"{label} must be {'non-empty ' if nonempty else ''}text.")
    try:
        value.encode("utf-8")
    except UnicodeError:
        raise ThingsError(f"{label} must contain valid Unicode.") from None
    return value


def note(value):
    value = text(value, "Notes")
    return {"_t": "tx", "t": 1, "v": value, "ch": zlib.crc32(value.encode("utf-8"))}


def apply_note(current, payload):
    if payload is None:
        return ""
    if isinstance(payload, str):
        if payload.startswith("<note") or payload.startswith("<?xml"):
            try:
                root = ET.fromstring(payload)
                if root.tag == "note":
                    return "".join(root.itertext())
            except ET.ParseError:
                pass
        return payload
    if not isinstance(payload, dict) or payload.get("t") not in (1, 2):
        raise ThingsError("Unsupported notes format; cache was not advanced.")
    if payload["t"] == 1:
        result = text(payload.get("v", ""), "Cloud note").encode("utf-8")
        checksum = payload.get("ch")
        if checksum is not None and checksum != zlib.crc32(result):
            raise ThingsError("Cloud note checksum mismatch; cache was not advanced.")
        return result.decode("utf-8")
    result = (current or "").encode("utf-8")
    patches = payload.get("ps")
    if not isinstance(patches, list):
        raise ThingsError("Malformed note delta; cache was not advanced.")
    for patch in patches:
        position, length = patch.get("p"), patch.get("l")
        if type(position) is not int or type(length) is not int or min(position, length) < 0 or position + length > len(result):
            raise ThingsError("Invalid note delta range; cache was not advanced.")
        replacement = text(patch.get("r", ""), "Cloud note delta").encode("utf-8")
        result = result[:position] + replacement + result[position + length :]
        try:
            result.decode("utf-8")
        except UnicodeError:
            raise ThingsError("Invalid Unicode note delta; cache was not advanced.") from None
        if patch.get("ch") is not None and patch["ch"] != zlib.crc32(result):
            raise ThingsError("Cloud note delta checksum mismatch; cache was not advanced.")
    return result.decode("utf-8")


def fold(state, event):
    if not isinstance(event, dict):
        raise ThingsError("Malformed cloud event; cache was not advanced.")
    seen = set()
    for raw_id, envelope in event.items():
        if not isinstance(envelope, dict):
            raise ThingsError("Malformed cloud envelope; cache was not advanced.")
        entity, action = envelope.get("e"), envelope.get("t")
        identity = canonical_id(raw_id) if entity in LEGACY_KINDS else require_id(raw_id)
        if identity in seen:
            raise ThingsError("Ambiguous migrated identifier; cache was not advanced.")
        seen.add(identity)
        if entity is None:
            entity = state.get(identity, {}).get("e")
        if isinstance(entity, str) and entity.startswith("Task") and entity not in TASK_KINDS:
            raise ThingsError("A newer task format is present. Upgrade this plugin before syncing.")
        if type(action) is not int or action not in (0, 1, 2):
            raise ThingsError("Unknown cloud operation; cache was not advanced.")
        if action == 2:
            state.pop(identity, None)
            continue
        payload = copy.deepcopy(envelope.get("p", {}))
        if not isinstance(payload, dict):
            raise ThingsError("Malformed cloud properties; cache was not advanced.")
        if entity in LEGACY_KINDS:
            for field in REFERENCE_FIELDS:
                if field in payload and payload[field] is not None:
                    values = payload[field]
                    if isinstance(values, str):
                        values = [values]
                    payload[field] = [canonical_id(v) for v in values]
            if "dloid" in payload:
                payload["dloid"] = canonical_id(payload["dloid"])
        if entity in ("Tombstone", "Tombstone2"):
            target = payload.get("dloid")
            if not isinstance(target, str):
                raise ThingsError("Malformed deletion marker; cache was not advanced.")
            state.pop(canonical_id(target), None)
        previous = state.get(identity)
        obj = {"e": entity, "p": {}, "notes": "", "ambiguous": bool(previous)} if action == 0 or previous is None else previous
        if action == 1 and previous is None:
            obj["ambiguous"] = True
        if "nt" in payload:
            obj["notes"] = apply_note(obj.get("notes", ""), payload["nt"])
        obj["p"].update(payload)
        obj["e"] = entity
        state[identity] = obj


def recurring(obj):
    p = obj["p"]
    return p.get("rr") is not None or p.get("rp") is not None or bool(p.get("rt")) or p.get("icsd") is not None or p.get("acrd") is not None


def known_ordinary(obj):
    p = obj["p"]
    return (
        {"rr", "rp", "rt"}.issubset(p)
        and (p["rt"] is None or isinstance(p["rt"], list))
        and not recurring(obj)
        and not obj.get("ambiguous")
    )


def writable_task(state, identity):
    require_id(identity)
    obj = state.get(identity)
    if obj is None or obj["e"] not in TASK_KINDS:
        raise ThingsError("Task was not found in the current cloud history.")
    if obj["e"] not in ("Task6", "Task7") or obj.get("ambiguous"):
        raise ThingsError("This older or incomplete task format cannot be edited safely.")
    if not {"rr", "rp", "rt"}.issubset(obj["p"]) or (obj["p"]["rt"] is not None and not isinstance(obj["p"]["rt"], list)):
        raise ThingsError("Recurrence markers are incomplete. This task is available to read; editing requires verified markers.")
    if recurring(obj):
        raise ThingsError("Repeating tasks require unverified bookkeeping and are currently available to read only.")
    for field in REFERENCE_FIELDS & set(obj["p"]):
        values = obj["p"][field]
        if values is not None and (not isinstance(values, list) or any(not valid_id(value) for value in values)):
            raise ThingsError("Task relationships are malformed and cannot be edited safely.")
    return obj


def reference(state, value, kind, task_type=None):
    require_id(value)
    obj = state.get(value)
    if obj is None or not isinstance(obj["e"], str) or not obj["e"].startswith(kind) or obj["p"].get("tr"):
        raise ThingsError(f"The referenced {kind.lower()} was not found.")
    if task_type is not None and obj["p"].get("tp", 0) != task_type:
        raise ThingsError("The referenced task has the wrong container type.")
    if kind == "Task":
        writable_task(state, value)
    return value


def schedule(value, today=None):
    today = today or date.today().isoformat()
    if value in ("inbox", "anytime", "someday"):
        return {"st": {"inbox": 0, "anytime": 1, "someday": 2}[value], "sr": None, "tir": None, "sb": 0}
    if value in ("today", "evening"):
        timestamp = day_timestamp(today)
        return {"st": 1, "sr": timestamp, "tir": timestamp, "sb": int(value == "evening")}
    timestamp = day_timestamp(value)
    return {"st": 2 if timestamp > day_timestamp(today) else 1, "sr": timestamp, "tir": timestamp, "sb": 0}


def reminder(value):
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
        raise ThingsError("Reminder time must be local wall-clock HH:MM, or null to clear.")
    hours, minutes = map(int, value.split(":"))
    return hours * 3600 + minutes * 60


def relationships(fields, state, previous=None):
    result = {}
    if fields.get("area_id") and (fields.get("project_id") or fields.get("heading_id")):
        raise ThingsError("Choose a project or area as the direct container.")
    for name, wire, kind, task_type in [("project_id", "pr", "Task", 1), ("area_id", "ar", "Area", None), ("heading_id", "agr", "Task", 2)]:
        if name in fields:
            value = fields[name]
            result[wire] = [] if value is None else [reference(state, value, kind, task_type)]
    if "project_id" in fields:
        if fields["project_id"]:
            result["ar"] = []
        if "heading_id" not in fields:
            result["agr"] = []
    if fields.get("area_id"):
        result.update({"pr": [], "agr": []})
    if fields.get("heading_id"):
        heading = state[fields["heading_id"]]["p"]
        parents = as_list(heading.get("pr"))
        if len(parents) != 1:
            raise ThingsError("Heading has no unambiguous project.")
        if fields.get("project_id") and fields["project_id"] != parents[0]:
            raise ThingsError("Heading does not belong to the selected project.")
        reference(state, parents[0], "Task", 1)
        result.update({"pr": parents, "ar": []})
    if "tag_ids" in fields:
        if not isinstance(fields["tag_ids"], list):
            raise ThingsError("tag_ids must be a list of full tag IDs.")
        result["tg"] = list(dict.fromkeys(reference(state, v, "Tag") for v in fields["tag_ids"]))
    return result


CREATE_FIELDS = {"title", "notes", "when", "deadline", "type", "project_id", "area_id", "heading_id", "tag_ids"}
UPDATE_FIELDS = CREATE_FIELDS - {"type"} | {"status", "reminder", "trashed", "index", "today_index"}


def unknown_fields(fields, allowed):
    if not isinstance(fields, dict) or set(fields) - allowed:
        raise ThingsError("Unsupported action fields. Use the documented tool schema.")


def create_task(state, fields, now):
    unknown_fields(fields, CREATE_FIELDS)
    title = text(fields.get("title"), "Title", True)
    kind = fields.get("type", "task")
    if kind not in TYPES:
        raise ThingsError("Task type must be task, project, or heading.")
    # This complete snapshot mirrors the verified Task7 create, including null md.
    p = {key: None for key in "sr dds rmd lai tir md dd ato icsd rp acrd sp rr".split()}
    p.update({key: [] for key in "rt dl ar tg agr pr".split()})
    p.update({key: 0 for key in "do ix icc ti sb".split()})
    p.update(
        {
            "tp": TYPES[kind],
            "ss": 0,
            "tr": False,
            "icp": False,
            "lt": False,
            "st": 0 if kind == "task" else 1,
            "tt": title,
            "cd": now,
            "nt": note(fields.get("notes", "")),
            "xx": {"_t": "oo", "sn": {}},
        }
    )
    p.update(relationships(fields, state))
    if p["pr"] or p["ar"]:
        p["st"] = 1
    if "when" in fields:
        p.update(schedule(fields["when"]))
        if p["st"] == 0 and (p["pr"] or p["ar"] or p["agr"]):
            raise ThingsError("An Inbox task cannot also be placed in a container.")
    if kind != "task" and p["st"] != 1:
        raise ThingsError("Projects and headings use Anytime/Today placement in the verified create format.")
    if kind == "project" and (p["pr"] or p["agr"]):
        raise ThingsError("A project cannot be inside another project or heading.")
    if kind == "heading" and (len(p["pr"]) != 1 or p["agr"] or p["ar"]):
        raise ThingsError("A heading requires a project_id and cannot have an area or heading parent.")
    if "deadline" in fields and fields["deadline"] is not None:
        p["dd"] = day_timestamp(fields["deadline"])
    identity = new_id()
    return identity, {identity: {"e": "Task7", "t": 0, "p": p}}


def update_task(state, identity, fields, now):
    obj = writable_task(state, identity)
    unknown_fields(fields, UPDATE_FIELDS)
    if not fields:
        raise ThingsError("At least one change is required.")
    if obj["p"].get("tp") == 2 and set(fields) - {"title", "project_id", "index"}:
        raise ThingsError("Headings support title, project, and order edits. Schedule and completion apply to tasks/projects.")
    p = {"md": now}
    if "title" in fields:
        p["tt"] = text(fields["title"], "Title", True)
    if "notes" in fields:
        p["nt"] = note(fields["notes"])
    if "when" in fields:
        p.update(schedule(fields["when"]))
    if "deadline" in fields:
        p["dd"] = None if fields["deadline"] is None else day_timestamp(fields["deadline"])
    if "reminder" in fields:
        p["ato"] = reminder(fields["reminder"])
        p["lai"] = None
        if p["ato"] is not None and p.get("sr", obj["p"].get("sr")) is None:
            raise ThingsError("Schedule a day before setting a reminder time.")
    if "status" in fields:
        if fields["status"] not in STATUS:
            raise ThingsError("Status must be open, completed, or canceled.")
        p.update({"ss": STATUS[fields["status"]], "sp": None if fields["status"] == "open" else now})
    if "trashed" in fields:
        if type(fields["trashed"]) is not bool:
            raise ThingsError("trashed must be a boolean.")
        p["tr"] = fields["trashed"]
    for name, wire in [("index", "ix"), ("today_index", "ti")]:
        if name in fields:
            if type(fields[name]) is not int or not -(2**31) <= fields[name] < 2**31:
                raise ThingsError("Ordering indices must be signed 32-bit integers.")
            p[wire] = fields[name]
    p.update(relationships(fields, state, obj["p"]))
    if p.get("st") == 0:
        if any(fields.get(field) for field in ("project_id", "area_id", "heading_id")):
            raise ThingsError("An Inbox task cannot also be placed in a container.")
        p.update({"pr": [], "ar": [], "agr": []})
    elif obj["p"].get("st", 0) == 0 and "when" not in fields and any(p.get(field) for field in ("pr", "ar", "agr")):
        p.update(schedule("anytime"))
    if obj["p"].get("tp") == 1 and p.get("st") == 0:
        raise ThingsError("Projects cannot be moved to Inbox.")
    if obj["p"].get("tp") == 1 and (p.get("pr") or p.get("agr")):
        raise ThingsError("A project cannot be moved under another project or heading.")
    if obj["p"].get("tp") == 2 and (p.get("ar") or p.get("agr") or p.get("pr") == []):
        raise ThingsError("A heading must remain inside a project.")
    return {identity: {"e": "Task7", "t": 1, "p": p}}


def public_task(identity, obj, state):
    p = obj["p"]
    ato = p.get("ato")
    checks = []
    for cid, child in state.items():
        if str(child["e"]).startswith("ChecklistItem") and identity in as_list(child["p"].get("ts")):
            checks.append(
                {
                    "id": cid,
                    "title": child["p"].get("tt", ""),
                    "status": next((k for k, v in STATUS.items() if v == child["p"].get("ss", 0)), "unknown"),
                    "index": child["p"].get("ix") or 0,
                }
            )
    return {
        "id": identity,
        "title": p.get("tt", ""),
        "notes": obj.get("notes", ""),
        "type": next((k for k, v in TYPES.items() if v == p.get("tp", 0)), "unknown"),
        "status": next((k for k, v in STATUS.items() if v == p.get("ss", 0)), "unknown"),
        "scheduled": day_string(p.get("sr")),
        "deadline": day_string(p.get("dd")),
        "location": {0: "inbox", 1: "anytime", 2: "someday"}.get(p.get("st", 0), "unknown"),
        "evening": p.get("sb", 0) == 1,
        "reminder": f"{ato // 3600:02d}:{ato % 3600 // 60:02d}" if isinstance(ato, int) else None,
        "project_ids": as_list(p.get("pr")),
        "area_ids": as_list(p.get("ar")),
        "heading_ids": as_list(p.get("agr")),
        "effective_project_id": effective_project(p, state),
        "effective_area_id": effective_area(p, state),
        "tag_ids": as_list(p.get("tg")),
        "trashed": bool(p.get("tr")),
        "recurring": recurring(obj),
        "editable": obj["e"] in ("Task6", "Task7") and known_ordinary(obj),
        "index": p.get("ix") or 0,
        "today_index": p.get("ti") or 0,
        "today_reference": p.get("tir"),
        "checklist": sorted(checks, key=lambda c: (c["index"], c["id"])),
    }


def as_list(value):
    return value if isinstance(value, list) else [value] if isinstance(value, str) else []


def effective_project(props, state):
    direct = as_list(props.get("pr"))
    if direct:
        return direct[0]
    headings = as_list(props.get("agr"))
    if headings:
        parent = state.get(headings[0], {}).get("p", {})
        projects = as_list(parent.get("pr"))
        if projects:
            return projects[0]
    return None


def effective_area(props, state):
    direct = as_list(props.get("ar"))
    if direct:
        return direct[0]
    project = state.get(effective_project(props, state), {}).get("p", {})
    areas = as_list(project.get("ar"))
    return areas[0] if areas else None
