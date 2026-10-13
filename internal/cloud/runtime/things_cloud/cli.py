import argparse
import getpass
import json
import sys
import time

from . import __version__
from .credentials import read_credentials
from .errors import ThingsError
from .mcp import TOOLS, call, serve
from .protocol import strict_json
from .service import Service


def parser():
    root = argparse.ArgumentParser(description="Manage Things Cloud from Linux, Codex, Claude Code, or any stdio MCP host.")
    root.add_argument("--version", action="version", version=__version__)
    root.add_argument("--data-dir", help="Private state directory; defaults to XDG_DATA_HOME/things-cloud-plugin.")
    sub = root.add_subparsers(dest="command", required=True)
    connect = sub.add_parser("connect", help="Authenticate locally; password is hidden and never stored.")
    connect.add_argument("--email")
    connect.add_argument("--env-file", help="Explicit owner-only .env file; password stays out of arguments and logs.")
    for name in ("disconnect", "status", "sync", "serve", "tools"):
        sub.add_parser(name)
    listing = sub.add_parser("list")
    listing.add_argument("--view", default="all")
    listing.add_argument("--query")
    listing.add_argument("--limit", type=int, default=100)
    listing.add_argument("--offset", type=int, default=0)
    listing.add_argument("--offline", action="store_true")
    get = sub.add_parser("get")
    get.add_argument("task_id")
    get.add_argument("--offline", action="store_true")
    create = sub.add_parser("create")
    create.add_argument("title")
    create.add_argument("--notes", default="")
    create.add_argument("--when")
    create.add_argument("--deadline")
    create.add_argument("--type", choices=["task", "project", "heading"], default="task")
    create.add_argument("--project-id")
    create.add_argument("--area-id")
    create.add_argument("--heading-id")
    create.add_argument("--request-id")
    update = sub.add_parser("update", help='Patch a task using JSON, e.g. \'{"when":"today","reminder":"14:30"}\'.')
    update.add_argument("task_id")
    update.add_argument("changes", help="JSON object; '-' reads stdin.")
    update.add_argument("--request-id")
    complete = sub.add_parser("complete")
    complete.add_argument("task_id")
    complete.add_argument("--status", choices=["open", "completed", "canceled"], default="completed")
    complete.add_argument("--request-id")
    delete = sub.add_parser("delete")
    delete.add_argument("task_id")
    delete.add_argument("--permanent", action="store_true")
    delete.add_argument("--request-id")
    invoke = sub.add_parser("call", help="Invoke any MCP tool by name with JSON arguments.")
    invoke.add_argument("tool")
    invoke.add_argument("arguments", nargs="?", default="{}")
    watch = sub.add_parser("watch", help="Poll cloud changes until interrupted.")
    watch.add_argument("--interval", type=int, default=30)
    recover = sub.add_parser("mark-not-applied", help="Release an unknown write after checking your Apple client; never retries it.")
    recover.add_argument("request_id")
    recover.add_argument("--checked-in-things", action="store_true", required=True)
    return root


def json_argument(value):
    if value == "-":
        value = sys.stdin.read(1024 * 1024 + 1)
    try:
        result = strict_json(value)
        if not isinstance(result, dict):
            raise ValueError("Expected object")
        return result
    except (ValueError, UnicodeError):
        raise ThingsError("Arguments must be a valid JSON object without duplicate keys.") from None


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        service = Service(args.data_dir)
        cmd = args.command
        if cmd == "serve":
            serve(service)
            return 0
        if cmd == "connect":
            if args.env_file:
                if args.email:
                    raise ThingsError("Use either --env-file or --email, not both.")
                email, password = read_credentials(args.env_file)
            else:
                if not sys.stdin.isatty():
                    raise ThingsError("Run connect in your own terminal, or explicitly provide an owner-only --env-file.")
                email = args.email or input("Things Cloud email: ")
                password = getpass.getpass("Things Cloud password: ")
            result = service.connect(email, password)
            password = None
        elif cmd in ("disconnect", "status", "sync"):
            result = getattr(service, cmd)()
        elif cmd == "tools":
            result = {"tools": TOOLS}
        elif cmd == "list":
            result = service.list_tasks(view=args.view, query=args.query, limit=args.limit, offset=args.offset, offline=args.offline)
        elif cmd == "get":
            result = service.get_task(args.task_id, args.offline)
        elif cmd == "create":
            fields = {
                name: getattr(args, name)
                for name in ("title", "notes", "when", "deadline", "type", "project_id", "area_id", "heading_id")
                if getattr(args, name) is not None
            }
            result = service.create_task(fields, args.request_id)
        elif cmd == "update":
            result = service.update_task(args.task_id, json_argument(args.changes), args.request_id)
        elif cmd == "complete":
            result = service.update_task(args.task_id, {"status": args.status}, args.request_id)
        elif cmd == "delete":
            result = service.delete_task(args.task_id, args.permanent, args.request_id)
        elif cmd == "call":
            result = call(service, args.tool, json_argument(args.arguments))
        elif cmd == "mark-not-applied":
            result = service.abandon_uncertain(args.request_id)
        elif cmd == "watch":
            if args.interval < 5:
                raise ThingsError("Poll interval must be at least 5 seconds.")
            while True:
                try:
                    print(json.dumps(service.sync()), flush=True)
                except ThingsError as error:
                    print(str(error), file=sys.stderr, flush=True)
                time.sleep(args.interval)
        else:
            raise ThingsError("Unknown command.")
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0 if result.get("synced", True) else 2
    except ThingsError as error:
        print(str(error), file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        return 130
    except Exception:
        print("Operation failed locally. Inspect status and sync before repeating a write.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
