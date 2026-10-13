"""Small standards-compatible stdio MCP endpoint with no runtime dependencies."""

import json
import sys

from . import __version__
from .errors import ThingsError
from .protocol import strict_json
from .service import Service

INSTRUCTIONS = (
    "Manage the user's existing Things Cloud account. Every connected tool call syncs first. "
    "Use full IDs returned by reads. Connect through the local terminal, never through chat. "
    "For writes, reuse request_id after uncertainty and run things_sync to reconcile. "
    "Repeating and incomplete legacy tasks are read-only. Delete moves to Trash by default. "
    "Report synced only when the tool returns synced=true; device notification delivery is unverified."
)

STRING = {"type": "string"}
NULL_STRING = {"type": ["string", "null"]}
BOOL = {"type": "boolean"}
ID = {"type": "string", "description": "Full canonical Base58 Things ID from a read tool."}
IDS = {"type": "array", "items": ID}
REQUEST = {"type": "string", "description": "Optional stable operation ID. Reuse this for retries of the same intent."}
WHEN = {"type": "string", "description": "inbox, anytime, someday, today, evening, or YYYY-MM-DD."}
STATUS = {"type": "string", "enum": ["open", "completed", "canceled"]}
BASE_FIELDS = {
    "title": STRING,
    "notes": STRING,
    "when": WHEN,
    "deadline": NULL_STRING,
    "project_id": {**ID, "type": ["string", "null"]},
    "area_id": {**ID, "type": ["string", "null"]},
    "heading_id": {**ID, "type": ["string", "null"]},
    "tag_ids": IDS,
}
CHANGE_FIELDS = {
    **BASE_FIELDS,
    "status": STATUS,
    "reminder": {"type": ["string", "null"], "description": "Local wall-clock HH:MM, or null to clear; requires a scheduled day."},
    "trashed": BOOL,
    "index": {"type": "integer"},
    "today_index": {"type": "integer"},
}


def object_schema(properties, required=()):
    return {"type": "object", "properties": properties, "required": list(required), "additionalProperties": False}


def tool(name, description, schema, readonly=True, destructive=False):
    return {
        "name": name,
        "description": description,
        "inputSchema": schema,
        "annotations": {"readOnlyHint": readonly, "destructiveHint": destructive, "idempotentHint": readonly, "openWorldHint": True},
    }


TOOLS = [
    tool("things_status", "Check connection, cache freshness, and unresolved writes without disclosing credentials.", object_schema({})),
    tool("things_sync", "Download the current Things Cloud history and reconcile uncertain writes.", object_schema({})),
    tool(
        "things_list_tasks",
        "Read current tasks, lists, or search results. Pagination returns total and next_offset.",
        object_schema(
            {
                "view": {"type": "string", "enum": ["all", "inbox", "today", "upcoming", "anytime", "someday", "logbook", "trash"]},
                "query": STRING,
                "project_id": ID,
                "area_id": ID,
                "tag_id": ID,
                "type": {"type": "string", "enum": ["task", "project", "heading"]},
                "limit": {"type": "integer", "minimum": 1, "maximum": 500},
                "offset": {"type": "integer", "minimum": 0},
            }
        ),
    ),
    tool(
        "things_get_task",
        "Read one task including notes, dates, reminder, tags, and checklist.",
        object_schema({"task_id": ID}, ["task_id"]),
    ),
    tool(
        "things_list_entities",
        "Read projects, headings, areas, or tags and their IDs.",
        object_schema({"kind": {"type": "string", "enum": ["projects", "headings", "areas", "tags"]}}),
    ),
    tool(
        "things_create_task",
        "Create an ordinary task, project, or heading in the existing Things Cloud account.",
        object_schema(
            {**BASE_FIELDS, "type": {"type": "string", "enum": ["task", "project", "heading"]}, "request_id": REQUEST}, ["title"]
        ),
        False,
    ),
    tool(
        "things_update_task",
        "Patch title, notes, status, dates, reminder time, placement, tags, order, or Trash state. Null clears optional fields. Repeating tasks are read-only.",
        object_schema({"task_id": ID, "changes": object_schema(CHANGE_FIELDS), "request_id": REQUEST}, ["task_id", "changes"]),
        False,
        True,
    ),
    tool(
        "things_complete_task",
        "Complete, cancel, or reopen an ordinary task or project.",
        object_schema({"task_id": ID, "status": STATUS, "request_id": REQUEST}, ["task_id"]),
        False,
        True,
    ),
    tool(
        "things_delete_task",
        "Move an ordinary task to Trash. permanent=true purges a leaf task irreversibly; containers with children cannot be purged.",
        object_schema({"task_id": ID, "permanent": BOOL, "request_id": REQUEST}, ["task_id"]),
        False,
        True,
    ),
    tool(
        "things_create_entity",
        "Create an area, tag, project, or heading. parent_id is a parent tag, project for a heading, or area for a project.",
        object_schema(
            {
                "kind": {"type": "string", "enum": ["area", "tag", "project", "heading"]},
                "title": STRING,
                "parent_id": ID,
                "request_id": REQUEST,
            },
            ["kind", "title"],
        ),
        False,
    ),
    tool(
        "things_update_entity",
        "Update an area's title, order, tags, or a tag's title, order, parent, and shortcut. For projects/headings use things_update_task.",
        object_schema(
            {
                "entity_id": ID,
                "changes": object_schema(
                    {"title": STRING, "index": {"type": "integer"}, "tag_ids": IDS, "parent_id": NULL_STRING, "shortcut": NULL_STRING}
                ),
                "request_id": REQUEST,
            },
            ["entity_id", "changes"],
        ),
        False,
    ),
    tool(
        "things_delete_entity",
        "Permanently delete an empty area or unused leaf tag. Assignments and children must be removed first.",
        object_schema({"entity_id": ID, "request_id": REQUEST}, ["entity_id"]),
        False,
        True,
    ),
    tool(
        "things_checklist",
        "Create, update, reorder, complete, reopen, or delete checklist items belonging to an ordinary task.",
        object_schema(
            {
                "action": {"type": "string", "enum": ["create", "update", "delete"]},
                "task_id": ID,
                "checklist_id": ID,
                "title": STRING,
                "status": STATUS,
                "index": {"type": "integer"},
                "request_id": REQUEST,
            },
            ["action"],
        ),
        False,
        True,
    ),
]
TOOL_MAP = {item["name"]: item for item in TOOLS}


def validate(value, schema):
    types = schema.get("type", [])
    if isinstance(types, str):
        types = [types]
    actual = (
        "null"
        if value is None
        else "boolean"
        if type(value) is bool
        else "integer"
        if type(value) is int
        else "string"
        if isinstance(value, str)
        else "object"
        if isinstance(value, dict)
        else "array"
        if isinstance(value, list)
        else "number"
    )
    if actual not in types:
        raise ThingsError("Tool arguments have an invalid type.")
    if "enum" in schema and value not in schema["enum"]:
        raise ThingsError("Tool argument is outside the supported choices.")
    if actual == "integer" and (value < schema.get("minimum", value) or value > schema.get("maximum", value)):
        raise ThingsError("Tool argument is outside the supported range.")
    if actual == "string":
        try:
            value.encode("utf-8")
        except UnicodeError:
            raise ThingsError("Tool arguments must contain valid Unicode.") from None
    if actual == "object":
        if set(schema.get("required", [])) - set(value):
            raise ThingsError("Missing required tool arguments.")
        if schema.get("additionalProperties") is False and set(value) - set(schema.get("properties", {})):
            raise ThingsError("Unknown tool arguments.")
        for key, child in value.items():
            if key in schema.get("properties", {}):
                validate(child, schema["properties"][key])
    if actual == "array":
        for child in value:
            validate(child, schema["items"])


def call(service, name, arguments):
    if name not in TOOL_MAP:
        raise ThingsError("Unknown Things tool.")
    validate(arguments, TOOL_MAP[name]["inputSchema"])
    args = dict(arguments)
    if name == "things_status" and service.store.account_path.exists():
        service.sync()
    if name == "things_create_task":
        request = args.pop("request_id", None)
        return service.create_task(args, request)
    if name == "things_complete_task":
        return service.update_task(args["task_id"], {"status": args.get("status", "completed")}, args.get("request_id"))
    methods = {
        "things_status": "status",
        "things_sync": "sync",
        "things_list_tasks": "list_tasks",
        "things_get_task": "get_task",
        "things_list_entities": "list_entities",
        "things_update_task": "update_task",
        "things_delete_task": "delete_task",
        "things_create_entity": "create_entity",
        "things_update_entity": "update_entity",
        "things_delete_entity": "delete_entity",
        "things_checklist": "checklist",
    }
    return getattr(service, methods[name])(**args)


def handle(service, request):
    identity = request.get("id")
    if request.get("jsonrpc") != "2.0" or not isinstance(request.get("method"), str):
        return {"jsonrpc": "2.0", "id": identity, "error": {"code": -32600, "message": "Invalid request"}}
    if "id" not in request:
        return None
    method, params = request["method"], request.get("params", {})
    if not isinstance(params, dict):
        return {"jsonrpc": "2.0", "id": identity, "error": {"code": -32602, "message": "Invalid params"}}
    if method == "initialize":
        version = params.get("protocolVersion")
        supported = {"2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"}
        result = {
            "protocolVersion": version if version in supported else "2025-11-25",
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "things-cloud-plugin", "version": __version__},
            "instructions": INSTRUCTIONS,
        }
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        try:
            value = call(service, params.get("name"), params.get("arguments", {}))
            result = {
                "content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False, allow_nan=False)}],
                "structuredContent": value,
                "isError": False,
            }
        except ThingsError as error:
            result = {"content": [{"type": "text", "text": str(error)}], "isError": True}
        except Exception:
            # Never forward raw transport/SQLite exceptions containing secrets.
            result = {
                "content": [
                    {
                        "type": "text",
                        "text": "The operation failed locally. No success is confirmed; inspect status and sync before retrying.",
                    }
                ],
                "isError": True,
            }
    else:
        return {"jsonrpc": "2.0", "id": identity, "error": {"code": -32601, "message": "Method not found"}}
    return {"jsonrpc": "2.0", "id": identity, "result": result}


def serve(service=None):
    service = service or Service()
    while True:
        line = sys.stdin.buffer.readline(4 * 1024 * 1024 + 1)
        if not line:
            return
        try:
            if len(line) > 4 * 1024 * 1024:
                raise ValueError("Request too large")
            request = strict_json(line.decode("utf-8"))
            if not isinstance(request, dict):
                raise ValueError("Expected request")
            response = handle(service, request)
        except (ValueError, UnicodeError):
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Invalid JSON request"}}
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False, allow_nan=False) + "\n")
            sys.stdout.flush()
