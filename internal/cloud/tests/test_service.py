import copy
from datetime import date, timedelta
import json
from pathlib import Path
import tempfile
import unittest

from things_cloud import model
from things_cloud.errors import CloudError, ThingsError, UncertainWrite
from things_cloud.service import Service
from test_model import TASK, PROJECT, AREA, ordinary


class FakeCloud:
    def __init__(self):
        self.events = []
        self.page_size = 2
        self.commits = []
        self.fail_commit = None
        self.fail_read_at = None
        self.accept_then_timeout = False
        self.extra_on_commit = None
        self.extra_after_page = None
        self.history_key = "test-history-capability"

    def authenticate(self, email, password):
        return self.history_key

    def page(self, index):
        if index == self.fail_read_at:
            raise ThingsError("Test connection failure")
        result = {
            "items": copy.deepcopy(self.events[index : index + self.page_size]),
            "current-item-index": len(self.events),
            "schema": 301,
        }
        if self.extra_after_page:
            self.events.append(self.extra_after_page)
            self.extra_after_page = None
        return result

    def commit(self, changes, ancestor):
        if self.fail_commit:
            raise self.fail_commit
        self.commits.append((copy.deepcopy(changes), ancestor))
        if self.extra_on_commit:
            self.events.append(self.extra_on_commit)
            self.extra_on_commit = None
        self.events.append(copy.deepcopy(changes))
        if self.accept_then_timeout:
            raise UncertainWrite("Test timeout")
        return len(self.events)


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cloud = FakeCloud()
        self.service = Service(self.tmp.name, cloud_factory=lambda **kwargs: self.cloud)
        self.service.connect("test@example.com", "never-persist-this-password")
        self.cloud.events = [{TASK: {"e": "Task7", "t": 0, "p": ordinary()["p"]}}]

    def tearDown(self):
        self.tmp.cleanup()

    def test_connect_persists_only_capability_with_private_permissions(self):
        path = Path(self.tmp.name) / "account.json"
        self.assertNotIn("never-persist", path.read_text())
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(Path(self.tmp.name).stat().st_mode & 0o777, 0o700)
        self.assertNotIn("history", json.dumps(self.service.status()))

    def test_full_and_incremental_replay_with_pagination(self):
        self.cloud.events += [{TASK: {"e": "Task7", "t": 1, "p": {"tt": f"Name {i}"}}} for i in range(5)]
        result = self.service.sync()
        self.assertEqual(result["head_index"], 6)
        self.assertEqual(self.service.get_task(TASK, offline=True)["task"]["title"], "Name 4")
        self.assertEqual(self.service.sync()["changes_downloaded"], 0)
        self.cloud.events.append({TASK: {"e": "Task7", "t": 1, "p": {"dd": model.day_timestamp("2026-10-25")}}})
        self.assertEqual(self.service.sync()["changes_downloaded"], 1)
        self.assertEqual(self.service.get_task(TASK)["task"]["deadline"], "2026-10-25")

    def test_sync_failure_does_not_partially_replace_cache(self):
        self.service.sync()
        self.cloud.events += [{TASK: {"e": "Task7", "t": 1, "p": {"tt": "Intermediate"}}}] * 4
        self.cloud.fail_read_at = 3
        with self.assertRaises(ThingsError):
            self.service.sync()
        self.assertEqual(self.service.status()["head_index"], 1)
        self.assertEqual(self.service.get_task(TASK, offline=True)["task"]["title"], "Original")
        self.cloud.fail_read_at = None
        self.assertEqual(self.service.sync()["head_index"], 5)

    def test_snapshot_uses_first_page_head_even_when_cloud_keeps_changing(self):
        self.cloud.extra_after_page = {TASK: {"e": "Task7", "t": 1, "p": {"tt": "Later"}}}
        self.assertEqual(self.service.sync()["head_index"], 1)
        self.assertEqual(self.service.get_task(TASK, offline=True)["task"]["title"], "Original")
        self.assertEqual(self.service.sync()["head_index"], 2)

    def test_write_resyncs_and_preserves_intervening_other_device_changes(self):
        self.cloud.extra_on_commit = {TASK: {"e": "Task7", "t": 1, "p": {"tg": [AREA]}}}
        result = self.service.update_task(TASK, {"title": "Updated"}, "stable-1")
        self.assertTrue(result["synced"])
        self.assertEqual(self.cloud.commits[0][1], 1)
        task = self.service.get_task(TASK, offline=True)["task"]
        self.assertEqual(task["title"], "Updated")
        self.assertEqual(task["tag_ids"], [AREA])
        self.assertEqual(self.service.status()["head_index"], 3)

    def test_stable_request_id_prevents_duplicate_creates(self):
        first = self.service.create_task({"title": "New"}, "create-1")
        second = self.service.create_task({"title": "New"}, "create-1")
        self.assertEqual(first["ids"], second["ids"])
        self.assertTrue(second["replayed"])
        self.assertEqual(len(self.cloud.commits), 1)
        with self.assertRaises(ThingsError):
            self.service.create_task({"title": "Different"}, "create-1")

    def test_accepted_timeout_reconciles_without_resending(self):
        self.cloud.accept_then_timeout = True
        with self.assertRaises(UncertainWrite):
            self.service.create_task({"title": "Timeout"}, "timeout-1")
        self.assertEqual(len(self.service.status()["unresolved_writes"]), 1)
        self.assertEqual(self.service.sync()["unresolved_writes"], [])
        result = self.service.create_task({"title": "Timeout"}, "timeout-1")
        self.assertTrue(result["synced"])
        self.assertEqual(len(self.cloud.commits), 1)

    def test_unknown_write_is_not_blindly_retried(self):
        self.cloud.fail_commit = UncertainWrite("Unknown")
        with self.assertRaises(UncertainWrite):
            self.service.update_task(TASK, {"title": "Unknown"}, "unknown-1")
        self.cloud.fail_commit = None
        with self.assertRaises(UncertainWrite):
            self.service.create_task({"title": "Another"}, "another-1")
        self.service.abandon_uncertain("unknown-1")
        self.assertTrue(self.service.create_task({"title": "Another"}, "another-1")["synced"])

    def test_rejected_write_never_reports_success_or_changes_local_state(self):
        self.cloud.fail_commit = CloudError(409)
        with self.assertRaises(CloudError):
            self.service.update_task(TASK, {"title": "Rejected"}, "reject-1")
        self.assertEqual(self.service.get_task(TASK, offline=True)["task"]["title"], "Original")
        self.assertEqual(self.service.status()["unresolved_writes"], [])

    def test_read_after_acceptance_failure_reports_unverified_success(self):
        def fail_after_accept(changes, ancestor):
            self.cloud.events.append(changes)
            self.cloud.fail_read_at = len(self.cloud.events) - 1
            return len(self.cloud.events)

        self.cloud.commit = fail_after_accept
        result = self.service.update_task(TASK, {"title": "Accepted"})
        self.assertTrue(result["accepted_by_cloud"])
        self.assertFalse(result["synced"])
        self.assertEqual(self.service.status()["head_index"], 1)

    def test_lists_get_current_cloud_data_and_support_offline_search_pagination(self):
        self.cloud.events.append(
            {
                PROJECT: {
                    "e": "Task7",
                    "t": 0,
                    "p": ordinary("Tomorrow", sr=model.day_timestamp((date.today() + timedelta(days=1)).isoformat()), st=2)["p"],
                }
            }
        )
        self.assertEqual(self.service.list_tasks(view="upcoming")["tasks"][0]["id"], PROJECT)
        self.assertEqual(self.service.list_tasks(query="tomorrow", offline=True)["total"], 1)
        first = self.service.list_tasks(limit=1)
        self.assertEqual(first["total"], 2)
        self.assertEqual(first["next_offset"], 1)
        self.assertEqual(self.service.list_tasks(limit=1, offset=1)["next_offset"], None)

    def test_trash_restore_complete_reopen_and_leaf_purge(self):
        self.assertTrue(self.service.delete_task(TASK)["synced"])
        self.assertEqual(self.service.list_tasks(view="trash")["total"], 1)
        self.service.update_task(TASK, {"trashed": False, "status": "completed"})
        self.assertEqual(self.service.list_tasks(view="logbook")["total"], 1)
        self.service.update_task(TASK, {"status": "open"})
        self.assertEqual(self.service.get_task(TASK)["task"]["status"], "open")
        self.service.delete_task(TASK, permanent=True)
        with self.assertRaises(ThingsError):
            self.service.get_task(TASK)

    def test_checklist_crud_prevents_parent_purge_until_children_removed(self):
        created = self.service.checklist("create", task_id=TASK, title="First")
        cid = created["ids"][0]
        self.service.checklist("update", checklist_id=cid, title="Done", status="completed")
        task = self.service.get_task(TASK)["task"]
        self.assertEqual(task["checklist"][0]["status"], "completed")
        with self.assertRaises(ThingsError):
            self.service.delete_task(TASK, permanent=True)
        self.service.checklist("delete", checklist_id=cid)
        self.assertEqual(self.service.get_task(TASK)["task"]["checklist"], [])

    def test_area_tag_project_heading_crud_and_relationships(self):
        area = self.service.create_entity("area", "Work")["ids"][0]
        tag = self.service.create_entity("tag", "Focus")["ids"][0]
        project = self.service.create_entity("project", "Launch", parent_id=area)["ids"][0]
        heading = self.service.create_entity("heading", "Build", parent_id=project)["ids"][0]
        self.service.update_entity(tag, {"title": "Deep work", "shortcut": "d"})
        self.service.update_entity(area, {"tag_ids": [tag]})
        self.service.update_task(TASK, {"heading_id": heading, "tag_ids": [tag]})
        self.assertEqual(self.service.list_tasks(area_id=area)["total"], 2)
        self.assertEqual(self.service.list_tasks(tag_id=tag)["tasks"][0]["id"], TASK)
        with self.assertRaises(ThingsError):
            self.service.update_entity(tag, {"parent_id": tag})

    def test_invalid_plan_and_recurring_task_never_reach_commit(self):
        with self.assertRaises(ThingsError):
            self.service.create_task({"title": "", "when": "bad"})
        self.cloud.events.append({TASK: {"e": "Task7", "t": 1, "p": {"rp": {"opaque": True}}}})
        with self.assertRaises(ThingsError):
            self.service.update_task(TASK, {"title": "Unsafe"})
        self.assertFalse(self.cloud.commits)

    def test_newer_schema_and_incomplete_pages_fail_closed(self):
        self.cloud.page = lambda index: {"items": [], "current-item-index": 2, "schema": 301}
        with self.assertRaises(ThingsError):
            self.service.sync()
        self.assertEqual(self.service.status()["head_index"], 0)
        self.cloud.page = lambda index: {"items": [], "current-item-index": 0, "schema": 302}
        with self.assertRaises(ThingsError):
            self.service.sync()

    def test_switching_accounts_never_leaks_old_cache(self):
        self.service.sync()
        self.cloud.history_key = "other-test-capability"
        self.cloud.events = []
        self.service.connect("other@example.com", "hidden")
        self.assertEqual(self.service.list_tasks()["total"], 0)

    def test_disconnect_removes_credentials_and_data(self):
        self.service.sync()
        self.service.disconnect()
        self.assertFalse(self.service.status()["connected"])
        self.assertEqual(self.service.status()["task_count"], 0)
        with self.assertRaises(ThingsError):
            self.service.list_tasks()


if __name__ == "__main__":
    unittest.main()
