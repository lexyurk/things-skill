import hashlib
import unittest
import zlib

from things_cloud import model
from things_cloud.errors import ThingsError

TASK = "A7h5eCi24RvAWKC3Hv3muf"
PROJECT = "KGvAPpMrzHAKMdgMiERP1V"
AREA = "MpkEei6ybkFS2n6SXvwfLf"


def ordinary(title="Original", **props):
    p = {"tt": title, "tp": 0, "ss": 0, "st": 1, "rr": None, "rp": None, "rt": [], "sr": None, "dd": None}
    p.update(props)
    return {"e": "Task7", "p": p, "notes": "keep me"}


class ModelTests(unittest.TestCase):
    def test_identifiers_cover_zero_bytes_and_reject_noncanonical_values(self):
        for raw in (bytes(16), b"\0" * 15 + b"\x01", bytes(range(16)), b"\xff" * 16):
            encoded = model.encode_id(raw)
            self.assertTrue(model.valid_id(encoded))
            self.assertFalse(model.valid_id("1" + encoded))
        for invalid in ("", "not-a-uuid", "123", "0" * 22, "O" * 22, TASK + " "):
            self.assertFalse(model.valid_id(invalid))
        self.assertEqual(len({model.new_id() for _ in range(100)}), 100)

    def test_legacy_ids_are_byte_exact_including_actiongroup_and_recurrence(self):
        identifier = "ACTIONGROUP-ABCDEF12-1234-1234-1234-123456789ABC"
        self.assertEqual(model.canonical_id(identifier), model.encode_id(hashlib.sha1(identifier.encode()).digest()[:16]))
        self.assertNotEqual(model.canonical_id(identifier), model.canonical_id(identifier.lower()))
        prefix = "ABCDEF12-1234-1234-1234-123456789ABC"
        self.assertEqual(
            model.canonical_id(prefix + "-20261013"),
            model.encode_id(hashlib.sha1(hashlib.sha1(prefix.encode()).digest()[:16] + b"-20261013").digest()[:16]),
        )

    def test_create_has_verified_complete_snapshot_and_null_modification(self):
        identity, change = model.create_task({}, {"title": "Café ☕", "notes": "你好"}, 1720000000.5)
        self.assertTrue(model.valid_id(identity))
        p = change[identity]["p"]
        expected = set(
            "tp sr dds rt rmd ss tr dl icp st ar tt do lai tir tg agr ix cd lt icc md ti dd ato nt icsd pr rp acrd sp sb rr xx".split()
        )
        self.assertEqual(set(p), expected)
        self.assertIsNone(p["md"])
        self.assertEqual(p["nt"], {"_t": "tx", "t": 1, "v": "你好", "ch": zlib.crc32("你好".encode())})

    def test_sparse_update_preserves_omitted_fields_and_explicit_nulls(self):
        state = {TASK: ordinary(dd=1700000000, tg=[AREA], custom={"preserved": True})}
        change = model.update_task(state, TASK, {"title": "New", "deadline": None}, 100.25)
        self.assertEqual(change[TASK]["p"], {"tt": "New", "dd": None, "md": 100.25})
        model.fold(state, change)
        self.assertEqual(state[TASK]["p"]["tg"], [AREA])
        self.assertEqual(state[TASK]["notes"], "keep me")
        self.assertEqual(state[TASK]["p"]["custom"], {"preserved": True})
        self.assertIsNone(state[TASK]["p"]["dd"])

    def test_notes_use_utf8_byte_offsets_and_validate_crc(self):
        state = {TASK: ordinary()}
        model.fold(state, {TASK: {"e": "Task7", "t": 1, "p": {"nt": model.note("café todo")}}})
        expected = "café! todo"
        patch = {"_t": "tx", "t": 2, "ps": [{"p": 5, "l": 0, "r": "!", "ch": zlib.crc32(expected.encode())}]}
        model.fold(state, {TASK: {"e": "Task7", "t": 1, "p": {"nt": patch}}})
        self.assertEqual(state[TASK]["notes"], expected)
        for invalid in (
            {"t": 2, "ps": [{"p": 4, "l": 1, "r": ""}]},
            {"t": 1, "v": "oops", "ch": 0},
            {"t": 2, "ps": [{"p": 200, "l": 1, "r": ""}]},
        ):
            with self.assertRaises(ThingsError):
                model.apply_note(expected, invalid)

    def test_days_and_reminders_are_independent_of_utc_offset(self):
        self.assertEqual(model.day_timestamp("2026-10-13"), 1791849600)
        self.assertEqual(model.day_string(model.day_timestamp("2026-10-25")), "2026-10-25")
        self.assertEqual(model.reminder("14:30"), 52200)
        for invalid in ("2026-02-30", "2026-2-3", "tomorrow", 10):
            with self.assertRaises(ThingsError):
                model.day_timestamp(invalid)
        for invalid in ("24:00", "9:00", "00:60", "10:00:00"):
            with self.assertRaises(ThingsError):
                model.reminder(invalid)

    def test_reminder_patch_resets_interaction_and_requires_day(self):
        state = {TASK: ordinary()}
        with self.assertRaises(ThingsError):
            model.update_task(state, TASK, {"reminder": "14:30"}, 100)
        change = model.update_task(state, TASK, {"when": "2026-10-13", "reminder": "14:30"}, 100)
        self.assertEqual(change[TASK]["p"]["ato"], 52200)
        self.assertIsNone(change[TASK]["p"]["lai"])
        self.assertEqual(model.update_task(state, TASK, {"reminder": None}, 101)[TASK]["p"], {"md": 101, "ato": None, "lai": None})

    def test_schedule_symbols_and_real_future_dates(self):
        today = "2026-10-13"
        self.assertEqual(model.schedule("evening", today)["sb"], 1)
        self.assertEqual(model.schedule("2026-10-14", today)["st"], 2)
        self.assertEqual(model.schedule("2026-10-12", today)["st"], 1)
        for location, start in (("inbox", 0), ("anytime", 1), ("someday", 2)):
            self.assertEqual(model.schedule(location, today), {"st": start, "sr": None, "tir": None, "sb": 0})

    def test_recurrence_unknowns_and_future_kinds_are_blocked(self):
        for properties in ({"rr": {}}, {"rp": {}}, {"rt": [AREA]}, {"icsd": 0}, {"acrd": 0}):
            with self.assertRaises(ThingsError):
                model.update_task({TASK: ordinary(**properties)}, TASK, {"title": "x"}, 1)
        missing = ordinary()
        del missing["p"]["rp"]
        with self.assertRaises(ThingsError):
            model.update_task({TASK: missing}, TASK, {"title": "x"}, 1)
        with self.assertRaises(ThingsError):
            model.fold({}, {TASK: {"e": "Task8", "t": 0, "p": {}}})

    def test_relationships_validate_target_types_and_project_heading_match(self):
        state = {TASK: ordinary(), PROJECT: ordinary(tp=1), AREA: {"e": "Area3", "p": {"tt": "Work"}}}
        change = model.update_task(state, TASK, {"project_id": PROJECT}, 1)
        self.assertEqual(change[TASK]["p"]["pr"], [PROJECT])
        self.assertEqual(change[TASK]["p"]["ar"], [])
        for fields in ({"project_id": TASK}, {"project_id": PROJECT, "area_id": AREA}, {"tag_ids": [AREA]}):
            with self.assertRaises(ThingsError):
                model.update_task(state, TASK, fields, 1)

    def test_legacy_history_and_modern_updates_replay_to_same_id(self):
        legacy = "ABCDEF12-1234-1234-1234-123456789ABC"
        identity = model.canonical_id(legacy)
        state = {}
        model.fold(state, {legacy: {"e": "Task4", "t": 0, "p": {"tt": "Old"}}})
        model.fold(state, {identity: {"e": "Task7", "t": 1, "p": {"tt": "New", "rr": None, "rp": None, "rt": []}}})
        self.assertEqual(len(state), 1)
        self.assertEqual(state[identity]["p"]["tt"], "New")

    def test_tombstones_and_deletions_remove_entities(self):
        state = {TASK: ordinary()}
        model.fold(state, {AREA: {"e": "Tombstone2", "t": 0, "p": {"dloid": TASK, "dld": 100}}})
        self.assertNotIn(TASK, state)
        model.fold(state, {AREA: {"e": "Tombstone2", "t": 2, "p": {}}})
        self.assertFalse(state)

    def test_invalid_input_never_produces_a_plan(self):
        for fields in ({"title": ""}, {"title": "x", "raw": {}}, {"title": "x", "when": "bad"}, {"title": "\ud800"}):
            with self.assertRaises(ThingsError):
                model.create_task({}, fields, 1)
        state = {TASK: ordinary()}
        for fields in ({}, {"index": True}, {"trashed": "true"}, {"status": "deleted"}, {"notes": None}):
            with self.assertRaises(ThingsError):
                model.update_task(state, TASK, fields, 1)


if __name__ == "__main__":
    unittest.main()
