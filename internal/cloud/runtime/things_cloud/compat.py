"""Adapt things-skill's existing CLI flags and output to the shared service."""

from datetime import date, datetime, timedelta, timezone
import re
import uuid

from . import model
from .errors import ThingsError


def period(value):
    match = re.fullmatch(r"([1-9]\d*)([dwmy])", value or "")
    if not match:
        raise ThingsError("Period must be a positive number followed by d, w, m, or y.")
    days = int(match[1]) * {"d": 1, "w": 7, "m": 30, "y": 365}[match[2]]
    try:
        return (datetime.now(timezone.utc) - timedelta(days=days)).timestamp()
    except OverflowError:
        raise ThingsError("Period is too large.") from None


def timestamp(value):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    try:
        return datetime.fromtimestamp(value, timezone.utc).isoformat()
    except (ValueError, OverflowError, OSError):
        return None


def resolve(state, value, kinds, label):
    matches = [
        identity
        for identity, obj in state.items()
        if not obj["p"].get("tr")
        and (
            (obj["e"] in model.TASK_KINDS and obj["p"].get("tp", 0) in kinds)
            or any(str(obj["e"]).startswith(k) for k in kinds if isinstance(k, str))
        )
        and (identity == value or obj["p"].get("tt") == value)
    ]
    if len(matches) != 1:
        raise ThingsError(f"{label} was not found uniquely. Use its full ID.")
    return matches[0]


def legacy_task(identity, obj, state, checks=True):
    task = model.public_task(identity, obj, state)
    p = obj["p"]
    project, area = task["effective_project_id"], task["effective_area_id"]
    headings = task["heading_ids"]
    heading = headings[0] if len(headings) == 1 else None

    def title(i):
        return state.get(i, {}).get("p", {}).get("tt", "")

    result = {
        "uuid": identity,
        "type": {"task": "to-do", "project": "project", "heading": "heading"}.get(task["type"], "unknown"),
        "title": task["title"],
        "status": "incomplete" if task["status"] == "open" else task["status"],
        "notes": task["notes"],
        "start": task["location"],
        "start_date": task["scheduled"],
        "deadline": task["deadline"],
        "created": timestamp(p.get("cd")),
        "modified": timestamp(p.get("md")),
        "stop_date": timestamp(p.get("sp")),
        "reminder_time": task["reminder"],
        "area": area,
        "area_title": title(area),
        "project": project,
        "project_title": title(project),
        "heading": heading,
        "heading_title": title(heading),
        "trashed": task["trashed"],
        "index": task["index"],
        "today_index": task["today_index"],
        "tags": [title(i) for i in task["tag_ids"]],
    }
    if checks:
        result["checklist"] = [
            {
                "uuid": c["id"],
                "type": "checklist-item",
                "title": c["title"],
                "status": "incomplete" if c["status"] == "open" else c["status"],
            }
            for c in task["checklist"]
        ]
    return {k: v for k, v in result.items() if v is not None}


def date_matches(actual, expected):
    if expected in ("true", "false"):
        return bool(actual) == (expected == "true")
    if not actual:
        return False
    today = date.today().isoformat()
    if expected == "past":
        return actual < today
    if expected == "future":
        return actual > today
    model.day_timestamp(expected)
    return actual == expected


def run(service, request):
    if not isinstance(request, dict) or set(request) - {"command", "args", "flags", "changed"}:
        raise ThingsError("Invalid CLI adapter request.")
    command, args, flags = request.get("command"), request.get("args") or [], request.get("flags") or {}
    changed = set(request.get("changed") or [])
    if not isinstance(command, list) or not all(isinstance(x, str) for x in command) or not isinstance(flags, dict):
        raise ThingsError("Invalid CLI adapter request.")
    name = " ".join(command)
    # One synchronized snapshot supplies names, relationships and read filters.
    state = service.read(lambda state: {"state": state})["state"]
    all_tasks = {i: obj for i, obj in state.items() if obj["e"] in model.TASK_KINDS}
    active = {i: obj for i, obj in all_tasks.items() if not obj["p"].get("tr")}
    selected = list(active)
    kind = "tasks"
    include_checks = flags.get("include-items", True)

    if name == "list" or name == "show" and flags.get("id") in ("inbox", "today", "upcoming", "anytime", "someday", "logbook", "trash"):
        view = (args[0] if args else "inbox") if name == "list" else flags["id"]
        selected, offset = [], 0
        while True:
            page = service.list_tasks(view=view, limit=500, offset=offset, offline=True)
            selected.extend(t["id"] for t in page["tasks"])
            if page["next_offset"] is None:
                break
            offset = page["next_offset"]
        if view == "logbook":
            if flags.get("period"):
                cutoff = period(flags["period"])
                selected = [i for i in selected if (all_tasks[i]["p"].get("sp") or 0) >= cutoff]
            selected.sort(key=lambda i: (all_tasks[i]["p"].get("sp") or 0, i), reverse=True)
            limit = flags.get("limit", 50)
            if type(limit) is not int or limit < 1:
                raise ThingsError("Logbook limit must be positive.")
            selected = selected[:limit]
    elif name in ("todos", "projects", "headings"):
        tp = {"todos": 0, "projects": 1, "headings": 2}[name]
        selected = [i for i in selected if active[i]["p"].get("tp", 0) == tp]
        if flags.get("project"):
            project = resolve(state, flags["project"], [1], "Project")
            selected = [i for i in selected if model.effective_project(active[i]["p"], state) == project]
        if flags.get("heading"):
            heading = resolve(state, flags["heading"], [2], "Heading")
            selected = [i for i in selected if heading in model.as_list(active[i]["p"].get("agr"))]
    elif name in ("areas", "tags"):
        entity_kind = "Area" if name == "areas" else "Tag"
        data = []
        for i, obj in state.items():
            if not str(obj["e"]).startswith(entity_kind) or obj["p"].get("tr"):
                continue
            entity = {"uuid": i, "type": name[:-1], "title": obj["p"].get("tt", "")}
            if name == "tags":
                entity["shortcut"] = obj["p"].get("sh") or ""
            else:
                entity["tags"] = [state.get(tag, {}).get("p", {}).get("tt", "") for tag in model.as_list(obj["p"].get("tg"))]
            if flags.get("include-items"):
                children = [
                    j
                    for j, task in active.items()
                    if (model.effective_area(task["p"], state) == i if name == "areas" else i in model.as_list(task["p"].get("tg")))
                ]
                entity["items"] = [legacy_task(j, active[j], state) for j in children]
            data.append((obj["p"].get("ix") or 0, i, entity))
        return {"kind": name, "data": [item[2] for item in sorted(data)]}
    elif name == "tagged":
        tag = resolve(state, flags.get("tag"), ["Tag"], "Tag")
        selected = [i for i in selected if tag in model.as_list(active[i]["p"].get("tg"))]
    elif name in ("search", "app-search") or name == "show" and flags.get("query"):
        query = model.text(flags.get("query"), "Query", True).casefold()
        selected = [i for i in selected if query in (active[i]["p"].get("tt", "") + "\n" + active[i].get("notes", "")).casefold()]
    elif name == "show":
        identity = flags.get("id")
        if identity not in all_tasks:
            raise ThingsError("Item was not found. Cloud show returns items; it cannot open the macOS app.")
        selected = [identity]
    elif name in ("recent", "search-advanced"):
        cutoff = period(flags.get("period") if name == "recent" else flags["last"]) if name == "recent" or flags.get("last") else None
        status = {"incomplete": 0, "completed": 3, "canceled": 2}
        types = {"to-do": 0, "project": 1, "heading": 2}
        if flags.get("status") and flags["status"] not in status or flags.get("type") and flags["type"] not in types:
            raise ThingsError("Invalid task status or type filter.")
        tag = resolve(state, flags["tag"], ["Tag"], "Tag") if flags.get("tag") else None
        area = resolve(state, flags["area"], ["Area"], "Area") if flags.get("area") else None
        filtered = []
        for i in selected:
            p = active[i]["p"]
            if cutoff is not None and (p.get("cd") or 0) < cutoff:
                continue
            if (
                flags.get("status")
                and p.get("ss", 0) != status[flags["status"]]
                or flags.get("type")
                and p.get("tp", 0) != types[flags["type"]]
            ):
                continue
            if tag and tag not in model.as_list(p.get("tg")) or area and area != model.effective_area(p, state):
                continue
            if any(
                flags.get(flag) and not date_matches(model.day_string(p.get(wire)), flags[flag])
                for flag, wire in (("start-date", "sr"), ("deadline", "dd"))
            ):
                continue
            filtered.append(i)
        selected = filtered
        if name == "recent":
            selected.sort(key=lambda i: (active[i]["p"].get("cd") or 0, i), reverse=True)
    elif name in ("todo add", "todo update", "todo delete", "project add", "project update", "project delete"):
        return write(service, state, name, flags, changed)
    elif name == "json":
        raise ThingsError("Things URL JSON batches require the macOS local backend. Use cloud call with a documented MCP tool.")
    else:
        raise ThingsError("This command has no cloud adapter.")

    for tag_title in flags.get("filter-tags") or []:
        tag = resolve(state, tag_title, ["Tag"], "Tag")
        selected = [i for i in selected if tag in model.as_list(all_tasks[i]["p"].get("tg"))]
    if name not in ("list", "recent", "show"):
        selected.sort(key=lambda i: (all_tasks[i]["p"].get("ix") or 0, i))
    data = [legacy_task(i, all_tasks[i], state, include_checks) for i in selected]
    if name == "projects" and flags.get("include-items"):
        for task in data:
            task["items"] = [
                legacy_task(i, obj, state) for i, obj in active.items() if model.effective_project(obj["p"], state) == task["uuid"]
            ]
    return {"kind": kind, "data": data}


def write(service, state, name, flags, changed):
    task_type, action = name.split()
    identity = flags.get("id")
    expected = 0 if task_type == "todo" else 1
    if action != "add":
        obj = state.get(identity)
        if not obj or obj["e"] not in model.TASK_KINDS or obj["p"].get("tp", 0) != expected:
            raise ThingsError("The ID does not identify the requested task type.")
    request_id = flags.get("request-id") or str(uuid.uuid4())
    if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", request_id):
        raise ThingsError("CLI request-id must use 1..100 letters, digits, dots, underscores, or hyphens.")
    if action == "delete":
        result = service.delete_task(identity, request_id=request_id)
        return {
            "kind": "result",
            "data": result,
            "synced": result["synced"],
            "message": f"Moved {identity} to Trash; synced to Things Cloud."
            if result["synced"]
            else f"Trash action for {identity} awaits cloud confirmation; run sync.",
        }
    fields = {key: flags[key] for key in ("title", "notes", "when", "deadline") if key in changed}
    if action == "add":
        fields.update({"title": flags.get("title"), "type": "task" if expected == 0 else "project"})
    if "deadline" in fields and not fields["deadline"]:
        fields["deadline"] = None
    reminder = None
    if "when" in fields:
        when = fields["when"]
        if "@" in when:
            when, reminder = when.split("@", 1)
            model.reminder(reminder)
        if when == "tomorrow":
            when = (date.today() + timedelta(days=1)).isoformat()
        fields["when"] = when
        model.schedule(when)
    if "tags" in changed:
        fields["tag_ids"] = [resolve(state, tag, ["Tag"], "Tag") for tag in flags.get("tags") or []]
    containers = [
        (flags.get("list-id") or flags.get("list"), [1, "Area"], "List"),
        (flags.get("area-id") or flags.get("area"), ["Area"], "Area"),
    ]
    for value, kinds, label in containers:
        if value:
            container = resolve(state, value, kinds, label)
            fields["area_id" if str(state[container]["e"]).startswith("Area") else "project_id"] = container
    if flags.get("heading-id") or flags.get("heading"):
        value = flags.get("heading-id") or flags["heading"]
        heading_state = state
        if fields.get("project_id"):
            heading_state = {
                i: obj
                for i, obj in state.items()
                if obj["e"] not in model.TASK_KINDS or obj["p"].get("tp") != 2 or fields["project_id"] in model.as_list(obj["p"].get("pr"))
            }
        fields["heading_id"] = resolve(heading_state, value, [2], "Heading")
    if "completed" in changed or "canceled" in changed:
        if flags.get("completed") and flags.get("canceled"):
            raise ThingsError("Choose completed or canceled, not both.")
        fields["status"] = "completed" if flags.get("completed") else "canceled" if flags.get("canceled") else "open"
    if action == "update":
        if reminder is not None:
            fields["reminder"] = reminder
        result = service.update_task(identity, fields, request_id)
    else:
        children = flags.get("checklist-items") or [] if expected == 0 else flags.get("to-dos") or []
        for child in children:
            model.text(child, "Child title", True)
        # Validate every requested field before the first irreversible commit.
        _, planned = model.create_task(state, fields, 0)
        if reminder is not None:
            candidate = next(iter(planned.values()))
            if candidate["p"].get("sr") is None:
                raise ThingsError("Schedule a day before setting a reminder time.")
        result = service.create_task(fields, request_id)
        if not result.get("synced"):
            return {
                "kind": "result",
                "data": result,
                "synced": False,
                "message": "Creation is awaiting cloud confirmation; inspect sync before retrying.",
            }
        identity = result["ids"][0]
        followups = []
        try:
            if reminder is not None:
                followups.append(service.update_task(identity, {"reminder": reminder}, request_id + "-reminder"))
                if not followups[-1].get("synced"):
                    return {
                        "kind": "result",
                        "data": {**result, "followups": followups},
                        "synced": False,
                        "message": "Reminder awaits cloud confirmation; run sync before adding children.",
                    }
            for index, title in enumerate(children):
                child_request = request_id + f"-child-{index}"
                followups.append(
                    service.checklist("create", task_id=identity, title=title, index=index, request_id=child_request)
                    if expected == 0
                    else service.create_task({"title": title, "project_id": identity}, child_request)
                )
                if not followups[-1].get("synced"):
                    break
        except ThingsError:
            raise ThingsError(
                f"Parent {identity} was created. A follow-up failed; inspect sync and its children before retrying with the same request ID."
            ) from None
        if followups:
            result = {**result, "followups": followups, "synced": all(item.get("synced") for item in followups)}
    return {
        "kind": "result",
        "data": result,
        "synced": result["synced"],
        "message": f"{action.capitalize()} {identity}; synced to Things Cloud."
        if result.get("synced")
        else f"{identity} is awaiting cloud confirmation; inspect sync before retrying.",
    }
