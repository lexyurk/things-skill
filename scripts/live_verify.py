#!/usr/bin/env python3
"""Authorized live acceptance test using only disposable entities it creates."""

import argparse
from datetime import date, timedelta
import json
from pathlib import Path
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "internal/cloud/runtime"))
from things_cloud.credentials import read_credentials
from things_cloud.errors import ThingsError
from things_cloud.mcp import call
from things_cloud.service import Service
from things_cloud.storage import atomic_json


def verify(env_file, data_dir):
    service = Service(data_dir)
    report_path = service.store.directory / "live-verification.json"
    report = {"run_id": str(uuid.uuid4()), "steps": [], "created": [], "remaining": [], "passed": False}
    label = "Things integration verification " + report["run_id"][:8]
    owned = []

    def record(name):
        report["steps"].append(name)
        atomic_json(report_path, report)
        print("PASS " + name, flush=True)

    def tool(name, arguments):
        result = call(service, name, arguments)
        if result.get("accepted_by_cloud") or "synced" in result:
            if result.get("synced") is not True:
                raise ThingsError("A cloud operation was accepted but read-back verification did not complete.")
        return result

    def create(name, arguments, kind):
        arguments["request_id"] = report["run_id"] + "-" + str(len(owned))
        result = call(service, name, arguments)
        identity = result["ids"][0]
        owned.append((kind, identity))
        report["created"].append({"kind": kind, "id": identity})
        report["remaining"] = list(report["created"])
        atomic_json(report_path, report)
        if result.get("synced") is not True:
            raise ThingsError("A disposable create was accepted but not confirmed; its ID was recorded for cleanup.")
        return identity

    def require(condition, message):
        if not condition:
            raise ThingsError(message)

    try:
        username, password = read_credentials(env_file)
        service.connect(username, password)
        password = None
        record("account authentication")
        tool("things_sync", {})
        tool("things_status", {})
        for view in ("all", "inbox", "today", "upcoming", "anytime", "someday", "logbook", "trash"):
            tool("things_list_tasks", {"view": view, "limit": 1})
        record("all list views and automatic sync")

        area = create("things_create_entity", {"kind": "area", "title": label + " area"}, "area")
        tag = create("things_create_entity", {"kind": "tag", "title": label + " tag"}, "tag")
        project = create("things_create_entity", {"kind": "project", "title": label + " project", "parent_id": area}, "task")
        heading = create("things_create_entity", {"kind": "heading", "title": label + " heading", "parent_id": project}, "task")
        task = create(
            "things_create_task",
            {"title": label, "notes": "Disposable test: café ☕", "project_id": project, "heading_id": heading, "tag_ids": [tag]},
            "task",
        )
        require(tool("things_get_task", {"task_id": task})["task"]["title"] == label, "Created task title did not round-trip.")
        record("area, tag, project, heading, and ordinary task creation")

        day = (date.today() + timedelta(days=3)).isoformat()
        tool(
            "things_update_task",
            {
                "task_id": task,
                "changes": {"title": label + " edited", "notes": "Edited notes: 你好", "when": day, "deadline": day, "reminder": "14:30"},
            },
        )
        current = tool("things_get_task", {"task_id": task})["task"]
        require(
            current["scheduled"] == day
            and current["reminder"] == "14:30"
            and current["deadline"] == day
            and current["notes"] == "Edited notes: 你好",
            "Task edits did not round-trip.",
        )
        tool(
            "things_update_task",
            {"task_id": task, "changes": {"when": "evening", "deadline": None, "reminder": None, "index": 1, "today_index": 1}},
        )
        record("notes, dates, deadlines, reminders, evening, clearing, and ordering")

        checklist = create("things_checklist", {"action": "create", "task_id": task, "title": "Disposable checklist"}, "checklist")
        tool(
            "things_checklist",
            {"action": "update", "checklist_id": checklist, "title": "Edited checklist", "status": "completed", "index": 1},
        )
        current = tool("things_get_task", {"task_id": task})["task"]
        require(
            any(item["id"] == checklist and item["status"] == "completed" for item in current["checklist"]), "Checklist did not round-trip."
        )
        tool("things_checklist", {"action": "update", "checklist_id": checklist, "status": "open"})
        record("checklist create, update, complete, reopen, and order")

        for status in ("completed", "open", "canceled", "open"):
            tool("things_complete_task", {"task_id": task, "status": status})
            require(tool("things_get_task", {"task_id": task})["task"]["status"] == status, "Task status did not round-trip.")
        tool("things_delete_task", {"task_id": task})
        require(tool("things_get_task", {"task_id": task})["task"]["trashed"], "Trash did not round-trip.")
        tool("things_update_task", {"task_id": task, "changes": {"trashed": False, "area_id": area, "tag_ids": []}})
        record("complete, cancel, reopen, Trash, restore, and container moves")
        tool("things_update_entity", {"entity_id": area, "changes": {"title": label + " area edited"}})
        tool("things_update_entity", {"entity_id": tag, "changes": {"title": label + " tag edited", "shortcut": None}})
        for kind in ("areas", "tags", "projects", "headings"):
            tool("things_list_entities", {"kind": kind})
        require(tool("things_list_tasks", {"query": label})["total"] >= 1, "Task search did not find the disposable task.")
        record("entity edits, entity lists, and task search")
        report["passed"] = True
    except ThingsError as error:
        report["error"] = str(error)
    finally:
        # Remove children before containers and only IDs recorded from our own creates.
        for kind, identity in reversed(owned):
            try:
                if kind == "checklist":
                    tool("things_checklist", {"action": "delete", "checklist_id": identity})
                elif kind == "task":
                    tool("things_delete_task", {"task_id": identity, "permanent": True})
                else:
                    tool("things_delete_entity", {"entity_id": identity})
                report["remaining"] = [item for item in report["remaining"] if item["id"] != identity]
            except ThingsError as error:
                report.setdefault("cleanup_errors", []).append({"id": identity, "error": str(error)})
            atomic_json(report_path, report)
        if report["passed"] and not report["remaining"]:
            record("disposable entity cleanup and permanent deletion")
        atomic_json(report_path, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--data-dir", default=".local-state")
    args = parser.parse_args()
    report = verify(args.env_file, args.data_dir)
    print(
        json.dumps(
            {"passed": report["passed"], "steps": report["steps"], "remaining": len(report["remaining"]), "error": report.get("error")},
            indent=2,
        )
    )
    return 0 if report["passed"] and not report["remaining"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
