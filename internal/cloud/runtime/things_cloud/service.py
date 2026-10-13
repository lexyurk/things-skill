"""Serialized sync and task operations shared by the CLI and MCP server."""

import copy
from datetime import date
import hashlib
import json
import time
import uuid

from .errors import CloudError, ThingsError, UncertainWrite
from . import model
from .protocol import Cloud, strict_json
from .storage import Store, atomic_json, read_private_json


def dump(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))


class Service:
    def __init__(self, directory=None, cloud_factory=Cloud):
        self.store = Store(directory)
        self.cloud_factory = cloud_factory

    def connect(self, email, password):
        cloud = self.cloud_factory(instance_id="things-cloud-plugin-connect")
        key = cloud.authenticate(email, password)
        instance = f"{uuid.uuid4().hex}-com.culturedcode.ThingsMac-{uuid.uuid4().hex}"
        with self.store.locked():
            # Keep only the history capability; the password is never persisted.
            atomic_json(self.store.account_path, {"email": email.strip(), "history_key": key, "instance_id": instance})
        return {"connected": True, "message": "Account connected. Run sync to download tasks."}

    def disconnect(self):
        with self.store.locked():
            self.store.account_path.unlink(missing_ok=True)
            self.store.db_path.unlink(missing_ok=True)
        return {"connected": False, "message": "Local credentials and task cache removed."}

    def cloud(self):
        account = read_private_json(self.store.account_path)
        key = account.get("history_key")
        if not isinstance(key, str) or not key:
            raise ThingsError("Invalid account file. Run connect again.")
        cloud = self.cloud_factory(history_key=key, instance_id=account.get("instance_id", "things-cloud-plugin"))
        return cloud, hashlib.sha256(key.encode()).hexdigest()

    def prepare(self, db, fingerprint):
        previous = Store.get(db, "account")
        if previous != fingerprint:
            with db:
                db.execute("DELETE FROM events")
                db.execute("DELETE FROM operations")
                db.execute("DELETE FROM meta")
                Store.set(db, "account", fingerprint)
        return Store.get(db, "state", {}), Store.get(db, "cursor", 0)

    def sync_locked(self, db, cloud, fingerprint):
        original, start = self.prepare(db, fingerprint)
        state = copy.deepcopy(original)
        target = None
        events = []
        cursor = start
        while True:
            page = cloud.page(cursor)
            head, items = page.get("current-item-index"), page.get("items")
            if type(head) is not int or head < cursor or not isinstance(items, list):
                raise ThingsError("Invalid sync page or regressed history. Local cache was preserved.")
            schema = page.get("schema", 301)
            if type(schema) is not int or schema > 301:
                raise ThingsError("Things Cloud schema is newer than this plugin. Upgrade before syncing.")
            if target is None:
                target = head
            elif head < target:
                raise ThingsError("Cloud history regressed during sync. Local cache was preserved.")
            take = min(len(items), target - cursor)
            for offset, event in enumerate(items[:take]):
                model.fold(state, event)
                events.append((cursor + offset, dump(event)))
            cursor += take
            if cursor >= target:
                break
            if take == 0:
                raise ThingsError("Sync ended before the cloud head. Local cache was preserved.")
        with db:
            db.executemany("INSERT INTO events VALUES (?, ?)", events)
            Store.set(db, "state", state)
            Store.set(db, "cursor", cursor)
            Store.set(db, "last_sync", time.time())
        self.reconcile(db)
        return state, cursor, len(events)

    @staticmethod
    def reconcile(db):
        pending = db.execute("SELECT id, changes, ancestor FROM operations WHERE status IN ('sent','unknown','accepted')").fetchall()
        with db:
            for operation, changes, ancestor in pending:
                wanted = strict_json(changes)
                for idx, body in db.execute("SELECT idx, body FROM events WHERE idx>=? ORDER BY idx", (ancestor,)):
                    event = strict_json(body)
                    if all(event.get(identity) == envelope for identity, envelope in wanted.items()):
                        db.execute("UPDATE operations SET status='synced', head=? WHERE id=?", (idx + 1, operation))
                        break

    def sync(self):
        with self.store.locked():
            cloud, fingerprint = self.cloud()
            with self.store.database() as db:
                state, cursor, count = self.sync_locked(db, cloud, fingerprint)
                unresolved = db.execute("SELECT id FROM operations WHERE status IN ('sent','unknown','accepted')").fetchall()
        return {
            "synced": True,
            "head_index": cursor,
            "changes_downloaded": count,
            "task_count": sum(obj["e"] in model.TASK_KINDS for obj in state.values()),
            "unresolved_writes": [row[0] for row in unresolved],
        }

    def status(self):
        with self.store.locked():
            connected = self.store.account_path.exists()
            with self.store.database() as db:
                state = Store.get(db, "state", {})
                unresolved = db.execute("SELECT id,status FROM operations WHERE status IN ('sent','unknown','accepted')").fetchall()
                return {
                    "connected": connected,
                    "head_index": Store.get(db, "cursor", 0),
                    "last_sync": Store.get(db, "last_sync"),
                    "task_count": sum(obj["e"] in model.TASK_KINDS for obj in state.values()),
                    "unresolved_writes": [{"request_id": row[0], "status": row[1]} for row in unresolved],
                }

    def read(self, function, offline=False):
        with self.store.locked():
            cloud, fingerprint = self.cloud()
            with self.store.database() as db:
                state, cursor = self.prepare(db, fingerprint)
                if not offline:
                    state, cursor, _ = self.sync_locked(db, cloud, fingerprint)
                elif Store.get(db, "last_sync") is None:
                    raise ThingsError("No offline cache yet. Sync once while online.")
                result = function(state)
                return {"head_index": cursor, "offline": offline, "last_sync": Store.get(db, "last_sync"), **result}

    def list_tasks(self, view="all", query=None, project_id=None, area_id=None, tag_id=None, type=None, limit=100, offset=0, offline=False):
        views = {"all", "inbox", "today", "upcoming", "anytime", "someday", "logbook", "trash"}
        if view not in views or (type is not None and type not in model.TYPES):
            raise ThingsError("Invalid list view or task type.")
        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or not 1 <= limit <= 500
            or not isinstance(offset, int)
            or isinstance(offset, bool)
            or offset < 0
        ):
            raise ThingsError("limit must be 1..500 and offset must be nonnegative.")
        if query is not None:
            model.text(query, "Search")
        for value in [project_id, area_id, tag_id]:
            if value is not None:
                model.require_id(value)

        def select(state):
            tasks = []
            today = model.day_timestamp(date.today().isoformat())
            for identity, obj in state.items():
                if obj["e"] not in model.TASK_KINDS:
                    continue
                p = obj["p"]
                effective_project = model.effective_project(p, state)
                project = state.get(effective_project, {}).get("p", {})
                if p.get("tp") == 2 and type != "heading":
                    continue
                if view == "trash":
                    if not p.get("tr"):
                        continue
                elif p.get("tr"):
                    continue
                if view == "logbook":
                    if p.get("ss", 0) not in (2, 3):
                        continue
                elif view not in ("all", "trash") and p.get("ss", 0) != 0:
                    continue
                sr = p.get("sr")
                if view == "inbox" and (p.get("st", 0) != 0 or effective_project or model.effective_area(p, state)):
                    continue
                if view == "today" and not (
                    (sr is not None and sr <= today and p.get("st") in (1, 2)) or (p.get("dd") is not None and p["dd"] <= today)
                ):
                    continue
                if view == "upcoming" and not (sr is not None and sr > today):
                    continue
                if view == "anytime" and not (p.get("st") == 1 and (sr is None or sr <= today)):
                    continue
                if (
                    view == "anytime"
                    and effective_project
                    and (
                        project.get("tr")
                        or project.get("ss", 0) != 0
                        or project.get("st") == 2
                        or (project.get("sr") is not None and project["sr"] > today)
                    )
                ):
                    continue
                if view == "someday" and not (p.get("st") == 2 and sr is None and not effective_project):
                    continue
                if type is not None and p.get("tp", 0) != model.TYPES[type]:
                    continue
                if project_id and project_id != effective_project:
                    continue
                if area_id and area_id != model.effective_area(p, state):
                    continue
                if tag_id and tag_id not in model.as_list(p.get("tg")):
                    continue
                if query and query.casefold() not in (p.get("tt", "") + "\n" + obj.get("notes", "")).casefold():
                    continue
                # Templates are exposed by get_task, but not mixed with actionable lists.
                if view not in ("all", "trash", "logbook") and (p.get("rp") is not None or p.get("rr") is not None):
                    continue
                tasks.append(model.public_task(identity, obj, state))

            def sort(task):
                if view == "upcoming":
                    return (task["scheduled"] or "", task["index"], task["id"])
                if view == "today":
                    return (task["evening"], -(task["today_reference"] or 0), task["today_index"], -task["index"], task["id"])
                return (task["index"], task["id"])

            tasks.sort(key=sort)
            return {
                "tasks": tasks[offset : offset + limit],
                "total": len(tasks),
                "next_offset": offset + limit if offset + limit < len(tasks) else None,
            }

        return self.read(select, offline)

    def get_task(self, task_id, offline=False):
        model.require_id(task_id)

        def select(state):
            obj = state.get(task_id)
            if not obj or obj["e"] not in model.TASK_KINDS:
                raise ThingsError("Task was not found.")
            return {"task": model.public_task(task_id, obj, state)}

        return self.read(select, offline)

    def list_entities(self, kind="projects", offline=False):
        if kind not in ("projects", "headings", "areas", "tags"):
            raise ThingsError("Entity kind must be projects, headings, areas, or tags.")

        def select(state):
            items = []
            for identity, obj in state.items():
                p = obj["p"]
                if p.get("tr"):
                    continue
                if kind in ("projects", "headings") and obj["e"] in model.TASK_KINDS and p.get("tp") == (1 if kind == "projects" else 2):
                    items.append(model.public_task(identity, obj, state))
                elif (kind == "areas" and str(obj["e"]).startswith("Area")) or (kind == "tags" and str(obj["e"]).startswith("Tag")):
                    items.append(
                        {
                            "id": identity,
                            "title": p.get("tt", ""),
                            "index": p.get("ix") or 0,
                            "tag_ids": model.as_list(p.get("tg")),
                            "parent_ids": model.as_list(p.get("pn")),
                            "shortcut": p.get("sh"),
                        }
                    )
            return {"items": sorted(items, key=lambda x: (x["index"], x["id"]))}

        return self.read(select, offline)

    def write(self, intent, planner, request_id=None):
        request_id = request_id or str(uuid.uuid4())
        if not isinstance(request_id, str) or not 1 <= len(request_id) <= 128 or not re_request_id(request_id):
            raise ThingsError("request_id must use 1..128 letters, digits, dots, underscores, or hyphens.")
        with self.store.locked():
            cloud, fingerprint = self.cloud()
            with self.store.database() as db:
                state, ancestor, _ = self.sync_locked(db, cloud, fingerprint)
                previous = db.execute("SELECT intent,changes,status,head FROM operations WHERE id=?", (request_id,)).fetchone()
                if previous:
                    if previous[0] != dump(intent):
                        raise ThingsError("This request_id belongs to a different operation.")
                    if previous[2] == "synced":
                        return {
                            "synced": True,
                            "request_id": request_id,
                            "head_index": previous[3],
                            "ids": list(strict_json(previous[1])),
                            "replayed": True,
                        }
                    raise UncertainWrite(f"Request {request_id} has status {previous[2]}. Sync and inspect status before retrying.")
                pending = db.execute("SELECT id FROM operations WHERE status IN ('sent','unknown','accepted') LIMIT 1").fetchone()
                if pending:
                    raise UncertainWrite(f"Request {pending[0]} is unresolved. Sync to reconcile it before another write.")
                changes = planner(state, time.time())
                if not changes:
                    raise ThingsError("No changes were planned.")
                for identity, envelope in changes.items():
                    model.require_id(identity)
                    if envelope.get("e") == "Task7" and envelope.get("t") == 1:
                        model.writable_task(state, identity)
                with db:
                    db.execute(
                        "INSERT INTO operations VALUES (?,?,?,?,?,NULL)", (request_id, dump(intent), dump(changes), ancestor, "sent")
                    )
                try:
                    head = cloud.commit(changes, ancestor)
                except CloudError:
                    with db:
                        db.execute("UPDATE operations SET status='rejected' WHERE id=?", (request_id,))
                    raise
                except (UncertainWrite, ThingsError):
                    with db:
                        db.execute("UPDATE operations SET status='unknown' WHERE id=?", (request_id,))
                    raise UncertainWrite(
                        f"Write outcome unknown for request {request_id}. Run sync to reconcile; do not repeat the action with a new ID."
                    ) from None
                with db:
                    db.execute("UPDATE operations SET status='accepted', head=? WHERE id=?", (head, request_id))
                try:
                    _, cursor, _ = self.sync_locked(db, cloud, fingerprint)
                except ThingsError:
                    return {
                        "synced": False,
                        "accepted_by_cloud": True,
                        "request_id": request_id,
                        "head_index": head,
                        "ids": list(changes),
                        "message": "Cloud accepted the write; download verification failed. Run sync to verify.",
                    }
                status = db.execute("SELECT status FROM operations WHERE id=?", (request_id,)).fetchone()[0]
                return {
                    "synced": status == "synced",
                    "accepted_by_cloud": True,
                    "request_id": request_id,
                    "head_index": cursor,
                    "ids": list(changes),
                }

    def create_task(self, fields, request_id=None):
        return self.write({"action": "create_task", "fields": fields}, lambda s, now: model.create_task(s, fields, now)[1], request_id)

    def update_task(self, task_id, changes, request_id=None):
        return self.write(
            {"action": "update_task", "id": task_id, "fields": changes},
            lambda s, now: model.update_task(s, task_id, changes, now),
            request_id,
        )

    def delete_task(self, task_id, permanent=False, request_id=None):
        if not isinstance(permanent, bool):
            raise ThingsError("permanent must be a boolean.")

        def plan(state, now):
            model.writable_task(state, task_id)
            if not permanent:
                return model.update_task(state, task_id, {"trashed": True}, now)
            for child in state.values():
                p = child["p"]
                if any(task_id in model.as_list(p.get(field)) for field in ("pr", "agr", "ts")):
                    raise ThingsError(
                        "Permanent deletion of a container with children is unverified. Delete its children first or move it to Trash."
                    )
            identity = model.new_id()
            return {identity: {"e": "Tombstone2", "t": 0, "p": {"dloid": task_id, "dld": now}}}

        return self.write({"action": "delete_task", "id": task_id, "permanent": permanent}, plan, request_id)

    def create_entity(self, kind, title, parent_id=None, request_id=None):
        if kind not in ("area", "tag", "project", "heading"):
            raise ThingsError("Entity kind must be area, tag, project, or heading.")
        if kind in ("project", "heading"):
            fields = {"type": kind, "title": title}
            if parent_id:
                fields["project_id" if kind == "heading" else "area_id"] = parent_id
            return self.create_task(fields, request_id)

        def plan(state, now):
            model.text(title, "Title", True)
            identity = model.new_id()
            p = {"tt": title, "ix": 0, "xx": {"_t": "oo", "sn": {}}}
            if kind == "area":
                if parent_id is not None:
                    raise ThingsError("Areas cannot have a parent.")
                p["tg"] = []
            else:
                p.update({"pn": [model.reference(state, parent_id, "Tag")] if parent_id else [], "sh": None})
            return {identity: {"e": "Area3" if kind == "area" else "Tag4", "t": 0, "p": p}}

        return self.write({"action": "create_entity", "kind": kind, "title": title, "parent_id": parent_id}, plan, request_id)

    def update_entity(self, entity_id, changes, request_id=None):
        def plan(state, now):
            model.require_id(entity_id)
            obj = state.get(entity_id)
            if not obj or obj["e"] not in ("Area3", "Tag4"):
                raise ThingsError("Expected a current area or tag ID. Use update_task for projects/headings.")
            allowed = {"title", "index", "tag_ids"} if obj["e"] == "Area3" else {"title", "index", "parent_id", "shortcut"}
            model.unknown_fields(changes, allowed)
            if not changes:
                raise ThingsError("At least one change is required.")
            p = {"md": now}
            if "title" in changes:
                p["tt"] = model.text(changes["title"], "Title", True)
            if "index" in changes:
                if type(changes["index"]) is not int or not -(2**31) <= changes["index"] < 2**31:
                    raise ThingsError("Index must be a signed 32-bit integer.")
                p["ix"] = changes["index"]
            if "tag_ids" in changes:
                p.update(model.relationships({"tag_ids": changes["tag_ids"]}, state))
            if "shortcut" in changes:
                p["sh"] = None if changes["shortcut"] is None else model.text(changes["shortcut"], "Shortcut")
            if "parent_id" in changes:
                parent = changes["parent_id"]
                p["pn"] = [] if parent is None else [model.reference(state, parent, "Tag")]
                current, seen = parent, {entity_id}
                while current:
                    if current in seen:
                        raise ThingsError("Tag parents cannot form a cycle.")
                    seen.add(current)
                    current = (state[current]["p"].get("pn") or [None])[0]
            return {entity_id: {"e": obj["e"], "t": 1, "p": p}}

        return self.write({"action": "update_entity", "id": entity_id, "changes": changes}, plan, request_id)

    def delete_entity(self, entity_id, request_id=None):
        def plan(state, now):
            model.require_id(entity_id)
            obj = state.get(entity_id)
            if not obj or obj["e"] not in ("Area3", "Tag4"):
                raise ThingsError("Expected an area or tag ID. Use delete_task for tasks/projects/headings.")
            for identity, child in state.items():
                if identity != entity_id and any(entity_id in model.as_list(child["p"].get(field)) for field in ("ar", "tg", "pn")):
                    raise ThingsError("Remove this area's items or this tag's assignments/children before deleting it.")
            return {entity_id: {"e": obj["e"], "t": 2, "p": {}}}

        return self.write({"action": "delete_entity", "id": entity_id}, plan, request_id)

    def checklist(self, action, task_id=None, checklist_id=None, title=None, status=None, index=None, request_id=None):
        if action not in ("create", "update", "delete"):
            raise ThingsError("Checklist action must be create, update, or delete.")

        def plan(state, now):
            if action == "create":
                parent = model.writable_task(state, task_id)
                if parent["p"].get("tp", 0) != 0 or parent["p"].get("tr"):
                    raise ThingsError("Checklists belong to ordinary active tasks.")
                model.text(title, "Title", True)
                identity = model.new_id()
                next_index = (
                    max(
                        (
                            obj["p"].get("ix") or 0
                            for obj in state.values()
                            if str(obj["e"]).startswith("ChecklistItem") and task_id in model.as_list(obj["p"].get("ts"))
                        ),
                        default=-1,
                    )
                    + 1
                )
                if index is not None:
                    if type(index) is not int or not -(2**31) <= index < 2**31:
                        raise ThingsError("Index must be a signed 32-bit integer.")
                    next_index = index
                p = {
                    "cd": now,
                    "md": None,
                    "tt": title,
                    "ss": 0,
                    "sp": None,
                    "ix": next_index,
                    "ts": [task_id],
                    "lt": False,
                    "xx": {"_t": "oo", "sn": {}},
                }
                return {identity: {"e": "ChecklistItem3", "t": 0, "p": p}}
            model.require_id(checklist_id)
            obj = state.get(checklist_id)
            if not obj or obj["e"] not in ("ChecklistItem2", "ChecklistItem3"):
                raise ThingsError("Checklist item was not found or its format is unsupported.")
            parents = model.as_list(obj["p"].get("ts"))
            if len(parents) != 1:
                raise ThingsError("Checklist parent is ambiguous.")
            model.writable_task(state, parents[0])
            if action == "delete":
                return {checklist_id: {"e": "ChecklistItem3", "t": 2, "p": {}}}
            p = {"md": now}
            if title is not None:
                p["tt"] = model.text(title, "Title", True)
            if status is not None:
                if status not in model.STATUS:
                    raise ThingsError("Invalid checklist status.")
                p.update({"ss": model.STATUS[status], "sp": None if status == "open" else now})
            if index is not None:
                if type(index) is not int or not -(2**31) <= index < 2**31:
                    raise ThingsError("Index must be a signed 32-bit integer.")
                p["ix"] = index
            if len(p) == 1:
                raise ThingsError("A checklist change is required.")
            return {checklist_id: {"e": "ChecklistItem3", "t": 1, "p": p}}

        intent = {
            "action": "checklist",
            "operation": action,
            "task_id": task_id,
            "checklist_id": checklist_id,
            "title": title,
            "status": status,
            "index": index,
        }
        return self.write(intent, plan, request_id)

    def abandon_uncertain(self, request_id):
        # Explicit CLI recovery after the user checks their Apple client.
        with self.store.locked():
            with self.store.database() as db:
                row = db.execute("SELECT status FROM operations WHERE id=?", (request_id,)).fetchone()
                if not row or row[0] not in ("sent", "unknown"):
                    raise ThingsError("Only an unknown write can be marked not applied.")
                db.execute("UPDATE operations SET status='abandoned' WHERE id=?", (request_id,))
        return {"request_id": request_id, "status": "abandoned"}


def re_request_id(value):
    return all(char.isascii() and (char.isalnum() or char in "._-") for char in value)
