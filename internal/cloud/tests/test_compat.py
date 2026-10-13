from datetime import date, timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from things_cloud import model
from things_cloud.cli import main
from things_cloud.compat import run
from things_cloud.errors import ThingsError
from things_cloud.mcp import call
from things_cloud.service import Service
from test_model import TASK, PROJECT, AREA, ordinary
from test_service import FakeCloud


class CLICompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cloud = FakeCloud()
        self.service = Service(self.tmp.name, cloud_factory=lambda **kwargs: self.cloud)
        self.service.connect("test@example.com", "not-stored")
        self.cloud.events = [{TASK: {"e": "Task7", "t": 0, "p": ordinary(cd=1)["p"]}}]

    def tearDown(self):
        self.tmp.cleanup()

    def invoke(self, command, args=None, **flags):
        return run(self.service, {"command": command.split(), "args": args or [], "flags": flags, "changed": list(flags)})

    def test_login_alias_persists_and_downloads_tasks_without_saving_password(self):
        env = Path(self.tmp.name) / ".env"
        env.write_text("USERNAME=test@example.com\nPASSWORD=secret-test-password\n")
        env.chmod(0o600)
        with patch("things_cloud.cli.Service", return_value=self.service), patch("builtins.print"):
            self.assertEqual(main(["login", "--env-file", str(env)]), 0)
        resumed = Service(self.tmp.name, cloud_factory=lambda **kwargs: self.cloud)
        self.assertEqual(resumed.get_task(TASK)["task"]["title"], "Original")
        self.assertNotIn("secret-test-password", resumed.store.account_path.read_text())

    def test_existing_list_command_downloads_other_device_change(self):
        self.service.sync()
        self.cloud.events.append({TASK: {"e": "Task7", "t": 1, "p": {"tt": "From phone"}}})
        response = self.invoke("list", args=["anytime"])
        self.assertEqual(response["kind"], "tasks")
        self.assertEqual(response["data"][0]["uuid"], TASK)
        self.assertEqual(response["data"][0]["title"], "From phone")

    def test_list_returns_every_page_and_trash(self):
        event = {}
        for i in range(510):
            event[model.new_id()] = {"e": "Task7", "t": 0, "p": ordinary(str(i), st=0)["p"]}
        self.cloud.events.append(event)
        self.assertEqual(len(self.invoke("list")["data"]), 510)
        self.service.update_task(TASK, {"trashed": True})
        self.assertEqual(self.invoke("list", args=["trash"])["data"][0]["uuid"], TASK)

    def test_create_reminder_checklist_and_idempotent_replay(self):
        flags = {"title": "Call café", "when": "tomorrow@14:30", "checklist-items": ["First", "Second"], "request-id": "cli-create"}
        response = self.invoke("todo add", **flags)
        self.assertTrue(response["synced"])
        identity = response["data"]["ids"][0]
        task = self.service.get_task(identity)["task"]
        self.assertEqual(task["scheduled"], (date.today() + timedelta(days=1)).isoformat())
        self.assertEqual(task["reminder"], "14:30")
        self.assertEqual([c["title"] for c in task["checklist"]], ["First", "Second"])
        self.assertEqual(self.invoke("todo add", **flags)["data"]["ids"], [identity])
        self.assertEqual(len(self.cloud.commits), 4)

    def test_update_can_clear_notes_deadline_and_reopen(self):
        self.service.update_task(TASK, {"notes": "Text", "deadline": "2026-10-20", "status": "completed"})
        self.invoke("todo update", id=TASK, notes="", deadline="", completed=False)
        task = self.service.get_task(TASK)["task"]
        self.assertEqual(task["notes"], "")
        self.assertIsNone(task["deadline"])
        self.assertEqual(task["status"], "open")

    def test_delete_means_trash_and_not_canceled(self):
        self.invoke("todo delete", id=TASK)
        task = self.service.get_task(TASK)["task"]
        self.assertTrue(task["trashed"])
        self.assertEqual(task["status"], "open")

    def test_resolves_named_project_area_tags_and_heading(self):
        area = self.service.create_entity("area", "Work")["ids"][0]
        project = self.service.create_task({"title": "Release", "type": "project", "area_id": area})["ids"][0]
        heading = self.service.create_entity("heading", "Prep", project)["ids"][0]
        tag = self.service.create_entity("tag", "Focus")["ids"][0]
        self.invoke("todo update", id=TASK, **{"list": "Release", "heading": "Prep", "tags": ["Focus"]})
        task = self.service.get_task(TASK)["task"]
        self.assertEqual(task["effective_area_id"], area)
        self.assertEqual(task["heading_ids"], [heading])
        self.assertEqual(task["tag_ids"], [tag])
        self.assertEqual(self.invoke("todos", project=project, heading=heading)["data"][0]["project_title"], "Release")
        self.assertEqual(self.invoke("areas", **{"include-items": True})["data"][0]["items"][0]["area_title"], "Work")
        self.assertEqual(self.invoke("tagged", tag="Focus")["data"][0]["uuid"], TASK)

    def test_ambiguous_title_and_invalid_followup_are_rejected_before_creating(self):
        self.service.create_entity("tag", "Duplicate")
        self.service.create_entity("tag", "Duplicate")
        count = len(self.cloud.commits)
        for flags in ({"tags": ["Duplicate"]}, {"when": "anytime@14:30"}, {"checklist-items": [""]}, {"request-id": "bad:request"}):
            with self.assertRaises(ThingsError):
                self.invoke("todo add", title="Should not exist", **flags)
            self.assertEqual(len(self.cloud.commits), count)

    def test_projects_with_children_are_replay_safe(self):
        flags = {"title": "Project", "to-dos": ["One", "Two"], "request-id": "cli-project"}
        identity = self.invoke("project add", **flags)["data"]["ids"][0]
        self.invoke("project add", **flags)
        self.assertEqual(len(self.cloud.commits), 3)
        project = self.invoke("projects", **{"include-items": True})["data"][0]
        self.assertEqual(project["uuid"], identity)
        self.assertEqual(len(project["items"]), 2)

    def test_wrong_task_type_cannot_be_mutated_and_url_batch_fails_explicitly(self):
        for cmd, flags in (("project delete", {"id": TASK}), ("json", {"data": "[]"})):
            with self.assertRaises(ThingsError):
                self.invoke(cmd, **flags)
        self.assertFalse(self.cloud.commits)

    def test_accepted_but_unverified_action_never_reports_synced(self):
        self.cloud.fail_read_at = 2
        # Preflight and write's initial pull read index 1; the post-write pull
        # advances to index 2 only after it has already observed the commit.
        self.cloud.extra_on_commit = {model.new_id(): {"e": "Tag4", "t": 0, "p": {"tt": "Other"}}}
        self.cloud.page_size = 1
        response = self.invoke("todo update", id=TASK, title="Changed")
        self.assertFalse(response["synced"])
        self.assertNotIn("; synced", response["message"])

    def test_connected_mcp_status_downloads_and_offline_argument_is_rejected(self):
        self.assertEqual(call(self.service, "things_status", {})["head_index"], 1)
        with self.assertRaises(ThingsError):
            call(self.service, "things_list_tasks", {"offline": True})

    def test_referenced_area_and_tag_cannot_be_deleted(self):
        self.cloud.events.append(
            {
                AREA: {"e": "Area3", "t": 0, "p": {"tt": "Area"}},
                PROJECT: {"e": "Task7", "t": 0, "p": ordinary("Project", tp=1, ar=[AREA])["p"]},
            }
        )
        with self.assertRaises(ThingsError):
            self.service.delete_entity(AREA)
        self.service.update_task(PROJECT, {"area_id": None})
        self.assertTrue(self.service.delete_entity(AREA)["synced"])
        tag = self.service.create_entity("tag", "Temp")["ids"][0]
        self.service.update_task(TASK, {"tag_ids": [tag]})
        with self.assertRaises(ThingsError):
            self.service.delete_entity(tag)
        self.service.update_task(TASK, {"tag_ids": []})
        self.assertTrue(self.service.delete_entity(tag)["synced"])
