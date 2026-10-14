from datetime import date
import unittest

from things_cloud import model
from things_cloud.errors import ThingsError
from test_model import TASK, PROJECT, AREA, ordinary
import test_service


class ModelRegressionTests(unittest.TestCase):
    def test_modern_invalid_ids_are_not_migrated_into_invented_valid_ids(self):
        with self.assertRaises(ThingsError):
            model.fold({}, {"invalid-modern-id": {"e": "Task7", "t": 0, "p": ordinary()["p"]}})

    def test_duplicate_creates_are_never_editable(self):
        state = {}
        event = {TASK: {"e": "Task7", "t": 0, "p": ordinary()["p"]}}
        model.fold(state, event)
        model.fold(state, event)
        with self.assertRaises(ThingsError):
            model.writable_task(state, TASK)

    def test_malformed_rt_and_relationships_block_edits(self):
        for fields in ({"rt": ""}, {"pr": ["not-a-modern-id"]}):
            with self.assertRaises(ThingsError):
                model.writable_task({TASK: ordinary(**fields)}, TASK)

    def test_literal_xml_notes_are_preserved(self):
        self.assertEqual(model.apply_note("", "<example>keep this</example>"), "<example>keep this</example>")
        self.assertEqual(model.apply_note("", "<note><p>legacy</p></note>"), "legacy")

    def test_area_heading_conflict_and_clearing_project_clears_heading(self):
        heading = model.new_id()
        state = {
            TASK: ordinary(pr=[PROJECT], agr=[heading]),
            PROJECT: ordinary(tp=1),
            AREA: {"e": "Area3", "p": {}},
            heading: ordinary(tp=2, pr=[PROJECT]),
        }
        with self.assertRaises(ThingsError):
            model.update_task(state, TASK, {"area_id": AREA, "heading_id": heading}, 10)
        patch = model.update_task(state, TASK, {"project_id": None}, 10)[TASK]["p"]
        self.assertEqual(patch["pr"], [])
        self.assertEqual(patch["agr"], [])

    def test_heading_schedule_and_repeating_parent_mutations_blocked(self):
        with self.assertRaises(ThingsError):
            model.update_task({TASK: ordinary(tp=2, pr=[PROJECT])}, TASK, {"when": "inbox"}, 1)
        state = {PROJECT: ordinary(tp=1, rp={"active": True})}
        with self.assertRaises(ThingsError):
            model.create_task(state, {"title": "child", "project_id": PROJECT}, 1)

    def test_inbox_container_rules_and_move_out_of_inbox(self):
        state = {TASK: ordinary(st=0), PROJECT: ordinary(tp=1)}
        patch = model.update_task(state, TASK, {"project_id": PROJECT}, 1)[TASK]["p"]
        self.assertEqual(patch["st"], 1)
        self.assertEqual(model.update_task(state, TASK, {"when": "inbox"}, 1)[TASK]["p"]["pr"], [])
        with self.assertRaises(ThingsError):
            model.create_task(state, {"title": "child", "when": "inbox", "project_id": PROJECT}, 1)


class ViewRegressionTests(test_service.ServiceTests):
    # Only these methods are run here; base fixture is reused without duplicating tests.
    def test_deferred_task_remains_visible_when_its_day_arrives(self):
        self.cloud.events.append({TASK: {"e": "Task7", "t": 1, "p": {"st": 2, "sr": model.day_timestamp(date.today().isoformat())}}})
        self.assertEqual(self.service.list_tasks(view="today")["total"], 1)

    def test_nullable_relationships_and_indices_are_safe_for_queries(self):
        self.cloud.events.append({TASK: {"e": "Task7", "t": 1, "p": {"pr": None, "tg": None, "ti": None, "ix": None}}})
        self.assertEqual(self.service.list_tasks(tag_id=AREA)["total"], 0)
        self.assertEqual(self.service.list_tasks()["tasks"][0]["index"], 0)

    def test_anytime_excludes_unavailable_project_children(self):
        self.cloud.events += [
            {PROJECT: {"e": "Task7", "t": 0, "p": ordinary("Project", tp=1, st=2)["p"]}},
            {TASK: {"e": "Task7", "t": 1, "p": {"pr": [PROJECT]}}},
        ]
        self.assertEqual(self.service.list_tasks(view="anytime")["total"], 0)
        self.assertEqual(self.service.list_tasks(view="someday")["total"], 1)

    def test_heading_only_relationship_resolves_project_and_area(self):
        heading = model.new_id()
        self.cloud.events += [
            {AREA: {"e": "Area3", "t": 0, "p": {"tt": "Work"}}},
            {PROJECT: {"e": "Task7", "t": 0, "p": ordinary("Project", tp=1, ar=[AREA])["p"]}},
            {heading: {"e": "Task7", "t": 0, "p": ordinary("Heading", tp=2, pr=[PROJECT])["p"]}},
            {TASK: {"e": "Task7", "t": 1, "p": {"pr": [], "agr": [heading]}}},
        ]
        task = self.service.list_tasks(project_id=PROJECT)["tasks"][0]
        self.assertEqual(task["effective_project_id"], PROJECT)
        self.assertEqual(task["effective_area_id"], AREA)


# unittest otherwise repeats inherited tests from the fixture class.
for name in list(vars(test_service.ServiceTests)):
    if name.startswith("test_"):
        setattr(ViewRegressionTests, name, None)


if __name__ == "__main__":
    unittest.main()
