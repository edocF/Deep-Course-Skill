import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import course_state  # noqa: E402


CREATED_AT = "2026-09-11T09:00:00+08:00"


class InitializationTests(unittest.TestCase):
    def test_init_creates_minimal_valid_course(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "courses" / "finance"
            result = course_state.init_course(root, "finance", "Finance", CREATED_AT)

            self.assertEqual("finance", result["course_id"])
            self.assertTrue((root / "course.json").is_file())
            self.assertTrue((root / "attempts.jsonl").is_file())
            self.assertTrue((root / "research").is_dir())
            self.assertTrue((root / "lessons").is_dir())
            self.assertEqual(
                {
                    "schema_version": 1,
                    "course_id": "finance",
                    "title": "Finance",
                    "created_at": CREATED_AT,
                    "status": "onboarding",
                    "session_depth": "normal",
                },
                json.loads((root / "course.json").read_text(encoding="utf-8")),
            )
            self.assertEqual(
                {
                    "schema_version": 1,
                    "course_id": "finance",
                    "goals": [],
                    "prior_knowledge": [],
                    "constraints": [],
                },
                json.loads(
                    (root / "learner-profile.json").read_text(encoding="utf-8")
                ),
            )
            self.assertEqual(
                {
                    "schema_version": 1,
                    "course_id": "finance",
                    "status": "draft",
                    "learning_outcomes": [],
                    "modules": [],
                    "knowledge_nodes": [],
                    "backbone": [],
                },
                json.loads((root / "curriculum.json").read_text(encoding="utf-8")),
            )
            self.assertEqual(
                {
                    "schema_version": 1,
                    "course_id": "finance",
                    "knowledge": {},
                    "completed_lessons": [],
                },
                json.loads((root / "progress.json").read_text(encoding="utf-8")),
            )
            self.assertEqual("", (root / "attempts.jsonl").read_text(encoding="utf-8"))
            self.assertEqual([], course_state.validate_course(root)["errors"])

    def test_init_refuses_existing_nonempty_directory(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "existing"
            root.mkdir()
            (root / "keep.txt").write_text("user data", encoding="utf-8")

            with self.assertRaisesRegex(course_state.CourseStateError, "not empty"):
                course_state.init_course(root, "x", "X", CREATED_AT)

    def test_init_rejects_timestamp_without_offset_before_creating_files(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "finance"

            with self.assertRaises(course_state.CourseStateError) as raised:
                course_state.init_course(root, "finance", "Finance", "2026-09-11T09:00:00")

            self.assertEqual("invalid_timestamp", raised.exception.code)
            self.assertFalse(root.exists())


class CourseFixture(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name) / "finance"
        course_state.init_course(self.root, "finance", "Finance", CREATED_AT)

    def read_json(self, name):
        return json.loads((self.root / name).read_text(encoding="utf-8"))

    def write_json(self, name, value):
        (self.root / name).write_text(json.dumps(value), encoding="utf-8")


class AttemptTests(CourseFixture):
    def attempt(self, **fields):
        return {"schema_version": 1, "attempt_id": "attempt-new", "lesson_id": "lesson-001",
                "submitted_at": "2026-09-11T10:00:00+08:00", "responses": [], **fields}

    def test_malformed_attempts_never_change_existing_bytes(self):
        self.make_course_with_node()
        course_state.append_attempt(self.root, self.attempt(attempt_id="prior"))
        path = self.root / "attempts.jsonl"
        before = path.read_bytes()
        cases = [self.attempt(schema_version=value) for value in (None, True, 99)]
        cases += [self.attempt(responses=value) for value in (None, {}, [None], [1])]
        cases += [self.attempt(lesson_id=""), self.attempt(course_id="wrong"),
                  self.attempt(feedback=object()), self.attempt(score=float("nan")),
                  self.attempt(misconception_tags="bad"), {1: "bad"}]
        cases += [self.attempt(responses=[{"question_id": "q", "knowledge_ids": ["pv"],
                                          "answer": "1", "quality": value}])
                  for value in ([], {}, None)]
        cases += [self.attempt(responses=[{"question_id": "q", "knowledge_ids": value,
                                          "answer": "1"}]) for value in (None, "pv", [[]])]
        for attempt in cases:
            with self.subTest(attempt=attempt):
                with self.assertRaises(course_state.CourseStateError):
                    course_state.append_attempt(self.root, attempt)
                self.assertEqual(before, path.read_bytes())

    def test_append_preserves_record_without_terminal_newline(self):
        self.make_course_with_node()
        path = self.root / "attempts.jsonl"
        original = json.dumps(self.attempt(attempt_id="prior")).encode()
        path.write_bytes(original)
        result = course_state.append_attempt(self.root, self.attempt())
        self.assertEqual(1, result["line_index"])
        self.assertTrue(path.read_bytes().startswith(original + b"\n"))
        self.assertEqual(2, len(path.read_bytes().splitlines()))
        self.assertTrue(course_state.validate_course(self.root)["valid"])

    def make_course_with_node(self, knowledge_id="pv"):
        curriculum = self.read_json("curriculum.json")
        curriculum["knowledge_nodes"] = [
            {
                "knowledge_id": knowledge_id,
                "title": "Present value",
                "prerequisite_ids": [],
            }
        ]
        self.write_json("curriculum.json", curriculum)
        return self.root

    def test_attempt_is_appended_once(self):
        root = self.make_course_with_node("pv")
        attempt = {
            "schema_version": 1,
            "attempt_id": "attempt-001",
            "lesson_id": "lesson-001",
            "submitted_at": "2026-09-11T10:00:00+08:00",
            "responses": [
                {
                    "question_id": "q1",
                    "knowledge_ids": ["pv"],
                    "answer": "900",
                }
            ],
        }

        result = course_state.append_attempt(root, attempt)
        with self.assertRaisesRegex(course_state.CourseStateError, "duplicate"):
            course_state.append_attempt(root, attempt)

        self.assertEqual({"attempt_id": "attempt-001", "line_index": 0}, result)
        self.assertEqual(
            json.dumps(attempt, ensure_ascii=False, separators=(",", ":")) + "\n",
            (root / "attempts.jsonl").read_text(encoding="utf-8"),
        )

    def test_unknown_response_knowledge_id_is_rejected_without_writing(self):
        root = self.make_course_with_node("pv")
        attempts_path = root / "attempts.jsonl"
        before = attempts_path.read_bytes()
        attempt = {
            "schema_version": 1,
            "attempt_id": "attempt-unknown",
            "lesson_id": "lesson-001",
            "submitted_at": "2026-09-11T10:00:00+08:00",
            "responses": [
                {
                    "question_id": "q1",
                    "knowledge_ids": ["unknown"],
                    "answer": "900",
                }
            ],
        }

        with self.assertRaises(course_state.CourseStateError) as raised:
            course_state.append_attempt(root, attempt)

        self.assertEqual("unknown_knowledge_id", raised.exception.code)
        self.assertEqual(before, attempts_path.read_bytes())

    def test_attempt_timestamp_without_offset_is_rejected_without_writing(self):
        root = self.make_course_with_node("pv")
        attempts_path = root / "attempts.jsonl"
        before = attempts_path.read_bytes()
        attempt = {
            "schema_version": 1,
            "attempt_id": "attempt-local-time",
            "lesson_id": "lesson-001",
            "submitted_at": "2026-09-11T10:00:00",
            "responses": [],
        }

        with self.assertRaises(course_state.CourseStateError) as raised:
            course_state.append_attempt(root, attempt)

        self.assertEqual("invalid_timestamp", raised.exception.code)
        self.assertEqual(before, attempts_path.read_bytes())

    def test_invalid_response_quality_is_rejected_without_writing(self):
        root = self.make_course_with_node("pv")
        attempts_path = root / "attempts.jsonl"
        before = attempts_path.read_bytes()
        attempt = {
            "schema_version": 1,
            "attempt_id": "attempt-bad-quality",
            "lesson_id": "lesson-001",
            "submitted_at": "2026-09-11T10:00:00+08:00",
            "responses": [
                {
                    "question_id": "q1",
                    "knowledge_ids": ["pv"],
                    "answer": "900",
                    "quality": "excellent",
                }
            ],
        }

        with self.assertRaises(course_state.CourseStateError) as raised:
            course_state.append_attempt(root, attempt)

        self.assertEqual("invalid_quality", raised.exception.code)
        self.assertEqual(before, attempts_path.read_bytes())

    def test_caller_supplied_path_fields_are_rejected_without_writing(self):
        root = self.make_course_with_node("pv")
        attempts_path = root / "attempts.jsonl"
        base = {
            "schema_version": 1,
            "attempt_id": "attempt-path",
            "lesson_id": "lesson-001",
            "submitted_at": "2026-09-11T10:00:00+08:00",
            "responses": [],
        }
        cases = [
            {**base, "path": "../../outside.json"},
            {**base, "responses": [{"knowledge_ids": ["pv"], "artifact_path": "x"}]},
        ]

        for attempt in cases:
            with self.subTest(attempt=attempt):
                before = attempts_path.read_bytes()
                with self.assertRaises(course_state.CourseStateError) as raised:
                    course_state.append_attempt(root, attempt)
                self.assertEqual("injected_path_field", raised.exception.code)
                self.assertEqual(before, attempts_path.read_bytes())


class MasteryTests(CourseFixture):
    def configure_nodes(self, *knowledge_ids):
        curriculum = self.read_json("curriculum.json")
        curriculum["knowledge_nodes"] = [
            {
                "knowledge_id": knowledge_id,
                "title": knowledge_id.title(),
                "prerequisite_ids": [],
            }
            for knowledge_id in knowledge_ids
        ]
        self.write_json("curriculum.json", curriculum)

    def append_attempt(self, attempt_id, responses=None):
        course_state.append_attempt(
            self.root,
            {
                "schema_version": 1,
                "attempt_id": attempt_id,
                "lesson_id": "lesson-001",
                "submitted_at": "2026-09-11T10:00:00+08:00",
                "responses": responses or [],
            },
        )

    def test_quality_table_updates_mastery_confidence_status_and_review_time(self):
        self.configure_nodes("incorrect", "partial", "correct", "effortless")
        self.append_attempt("attempt-table")
        progress = self.read_json("progress.json")
        progress["knowledge"] = {
            "incorrect": {"mastery": 0.1, "confidence": 0.98, "interval_days": 10},
            "partial": {"mastery": 0.7, "confidence": 0.98, "interval_days": 10},
            "correct": {"mastery": 0.5, "confidence": 0.95, "interval_days": 2},
            "effortless": {"mastery": 0.8, "confidence": 0.95, "interval_days": 2},
        }
        self.write_json("progress.json", progress)
        updates = [
            {"knowledge_id": quality, "quality": quality}
            for quality in ("incorrect", "partial", "correct", "effortless")
        ]

        course_state.apply_mastery_updates(
            self.root,
            "attempt-table",
            updates,
            "2026-09-11T10:00:00+08:00",
        )

        entries = self.read_json("progress.json")["knowledge"]
        expected = {
            "incorrect": (0.0, 1.0, "relearning", 1, "2026-09-12T10:00:00+08:00"),
            "partial": (0.75, 1.0, "reviewing", 2, "2026-09-13T10:00:00+08:00"),
            "correct": (0.65, 1.0, "learning", 4, "2026-09-15T10:00:00+08:00"),
            "effortless": (1.0, 1.0, "reviewing", 6, "2026-09-17T10:00:00+08:00"),
        }
        for knowledge_id, values in expected.items():
            with self.subTest(knowledge_id=knowledge_id):
                entry = entries[knowledge_id]
                self.assertEqual(values[0], entry["mastery"])
                self.assertEqual(values[1], entry["confidence"])
                self.assertEqual(values[2], entry["status"])
                self.assertEqual(values[3], entry["interval_days"])
                self.assertEqual(values[4], entry["next_review_at"])
                self.assertEqual("2026-09-11T10:00:00+08:00", entry["last_practiced_at"])


    def test_three_successes_in_one_attempt_do_not_establish_mastery(self):
        self.configure_nodes("pv")
        progress = self.read_json("progress.json")
        progress["knowledge"] = {"pv": {"mastery": 0.9}}
        self.write_json("progress.json", progress)
        self.append_attempt("a1", [{"question_id": q, "knowledge_ids": ["pv"], "answer": "ok"}
                                   for q in ("q1", "q2", "q3")])
        course_state.apply_mastery_updates(self.root, "a1", [
            {"knowledge_id": "pv", "question_id": q, "quality": "correct"}
            for q in ("q1", "q2", "q3")], CREATED_AT)
        self.assertEqual("reviewing", self.read_json("progress.json")["knowledge"]["pv"]["status"])

    def test_third_success_on_second_attempt_can_master(self):
        self.configure_nodes("pv")
        progress = self.read_json("progress.json")
        progress["knowledge"] = {"pv": {"mastery": 0.9}}
        self.write_json("progress.json", progress)
        self.append_attempt("a1", [{"question_id": q, "knowledge_ids": ["pv"], "answer": "ok"}
                                   for q in ("q1", "q2")])
        course_state.apply_mastery_updates(self.root, "a1", [
            {"knowledge_id": "pv", "question_id": q, "quality": "effortless"}
            for q in ("q1", "q2")], CREATED_AT)
        self.assertEqual("reviewing", self.read_json("progress.json")["knowledge"]["pv"]["status"])
        self.append_attempt("a2")
        result = course_state.apply_mastery_updates(self.root, "a2", [
            {"knowledge_id": "pv", "quality": "correct", "misconception_tags": [],
             "feedback": "Clear independent explanation."}], "2026-09-12T09:00:00+08:00")
        entry = self.read_json("progress.json")["knowledge"]["pv"]
        self.assertEqual("mastered", entry["status"])
        self.assertEqual(3, len(entry["evidence"]))
        self.assertEqual(["pv"], result["changed_knowledge_ids"])
        self.assertEqual(entry["next_review_at"], result["next_review_at"]["pv"])
        self.assertTrue(course_state.validate_course(self.root)["valid"])

    def test_invalid_updates_leave_progress_unchanged(self):
        self.configure_nodes("pv")
        self.append_attempt("a1")
        good = {"knowledge_id": "pv", "quality": "correct"}
        invalid = [[], None, [None], [good, {"knowledge_id": "unknown", "quality": "correct"}],
                   [good, good], [{**good, "quality": []}], [{**good, "quality": "great"}],
                   [{**good, "question_id": "missing"}], [{**good, "misconception_tags": "bad"}],
                   [{**good, "feedback": 1}], [{**good, "artifact_path": "outside"}]]
        path = self.root / "progress.json"
        before = path.read_bytes()
        for updates in invalid:
            with self.subTest(updates=updates):
                with self.assertRaises(course_state.CourseStateError):
                    course_state.apply_mastery_updates(self.root, "a1", updates, CREATED_AT)
                self.assertEqual(before, path.read_bytes())
        for attempt_id, stamp in [("missing", CREATED_AT), ("a1", "2026-09-11T09:00:00")]:
            with self.assertRaises(course_state.CourseStateError):
                course_state.apply_mastery_updates(self.root, attempt_id, [good], stamp)
            self.assertEqual(before, path.read_bytes())
        course_state.apply_mastery_updates(self.root, "a1", [good], CREATED_AT)
        before = path.read_bytes()
        with self.assertRaisesRegex(course_state.CourseStateError, "already applied"):
            course_state.apply_mastery_updates(self.root, "a1", [good], CREATED_AT)
        self.assertEqual(before, path.read_bytes())

    def test_failed_atomic_replace_preserves_progress_and_allows_retry(self):
        self.configure_nodes("pv")
        self.append_attempt("a1")
        before = (self.root / "progress.json").read_bytes()
        updates = [{"knowledge_id": "pv", "quality": "correct"}]
        with patch.object(course_state.os, "replace", side_effect=OSError("disk failure")):
            with self.assertRaises(OSError):
                course_state.apply_mastery_updates(self.root, "a1", updates, CREATED_AT)
        self.assertEqual(before, (self.root / "progress.json").read_bytes())
        course_state.apply_mastery_updates(self.root, "a1", updates, CREATED_AT)
        entry = self.read_json("progress.json")["knowledge"]["pv"]
        self.assertEqual(0.15, entry["mastery"])
        self.assertEqual(3, entry["interval_days"])

    def test_partial_evidence_never_counts_as_successful_mastery(self):
        self.configure_nodes("pv")
        progress = self.read_json("progress.json")
        progress["knowledge"] = {"pv": {"mastery": 0.9}}
        self.write_json("progress.json", progress)
        for index in range(3):
            self.append_attempt(str(index))
            course_state.apply_mastery_updates(self.root, str(index),
                [{"knowledge_id": "pv", "quality": "partial"}], CREATED_AT)
        self.assertEqual("reviewing", self.read_json("progress.json")["knowledge"]["pv"]["status"])

    def test_invalid_persisted_numeric_or_evidence_state_fails_closed(self):
        self.configure_nodes("pv")
        self.append_attempt("a1")
        original = self.read_json("progress.json")
        cases = [{"mastery": value} for value in (-0.1, 1.1, True, "0.5", float("nan"), 10**400)]
        cases += [{"confidence": 2}, {"interval_days": -1}, {"interval_days": []},
                  {"interval_days": True}, {"evidence": [None]}, {"evidence": "bad"}]
        for entry in cases:
            with self.subTest(entry=entry):
                self.write_json("progress.json", {**original, "knowledge": {"pv": entry}})
                before = (self.root / "progress.json").read_bytes()
                self.assertFalse(course_state.validate_course(self.root)["valid"])
                with self.assertRaises(course_state.CourseStateError):
                    course_state.apply_mastery_updates(self.root, "a1",
                        [{"knowledge_id": "pv", "quality": "correct"}], CREATED_AT)
                self.assertEqual(before, (self.root / "progress.json").read_bytes())

    def test_persisted_evidence_must_reference_recorded_applied_attempts(self):
        self.configure_nodes("pv")
        self.append_attempt("a1")
        course_state.apply_mastery_updates(self.root, "a1", [{"knowledge_id": "pv", "quality": "correct"}], CREATED_AT)
        original = self.read_json("progress.json")
        for mutation in ("unknown_application", "unknown_evidence", "missing_application", "duplicate_evidence"):
            progress = json.loads(json.dumps(original))
            if mutation == "unknown_application":
                progress["applied_attempt_ids"].append("missing")
            elif mutation == "unknown_evidence":
                progress["knowledge"]["pv"]["evidence"][0]["attempt_id"] = "missing"
            elif mutation == "missing_application":
                progress["applied_attempt_ids"] = []
            else:
                progress["knowledge"]["pv"]["evidence"] *= 2
            self.write_json("progress.json", progress)
            with self.subTest(mutation=mutation):
                self.assertFalse(course_state.validate_course(self.root)["valid"])

    def test_review_minimum_and_old_or_overflowing_evidence(self):
        self.configure_nodes("pv")
        self.append_attempt("a1")
        updates = [{"knowledge_id": "pv", "quality": "effortless"}]
        course_state.apply_mastery_updates(self.root, "a1", updates, CREATED_AT)
        entry = self.read_json("progress.json")["knowledge"]["pv"]
        self.assertEqual(5, entry["interval_days"])
        self.assertEqual("2026-09-16T09:00:00+08:00", entry["next_review_at"])
        self.append_attempt("a2")
        before = (self.root / "progress.json").read_bytes()
        for stamp in ("2026-09-10T09:00:00+08:00", "9999-12-31T09:00:00+08:00"):
            with self.assertRaises(course_state.CourseStateError):
                course_state.apply_mastery_updates(self.root, "a2", updates, stamp)
            self.assertEqual(before, (self.root / "progress.json").read_bytes())


class ValidationTests(CourseFixture):
    def error_codes(self):
        return {error["code"] for error in course_state.validate_course(self.root)["errors"]}

    def test_valid_empty_course_has_no_errors_or_warnings(self):
        self.assertEqual(
            {"valid": True, "errors": [], "warnings": []},
            course_state.validate_course(self.root),
        )

    def test_unknown_schema_version_fails_closed(self):
        course = self.read_json("course.json")
        course["schema_version"] = 99
        self.write_json("course.json", course)

        self.assertIn("unsupported_schema_version", self.error_codes())

    def test_schema_version_must_be_an_integer(self):
        course = self.read_json("course.json")
        course["schema_version"] = 1.0
        self.write_json("course.json", course)

        self.assertIn("unsupported_schema_version", self.error_codes())

    def test_timestamp_without_offset_is_invalid(self):
        course = self.read_json("course.json")
        course["created_at"] = "2026-09-11T09:00:00"
        self.write_json("course.json", course)

        self.assertIn("invalid_timestamp", self.error_codes())

    def test_mismatched_course_id_is_invalid(self):
        profile = self.read_json("learner-profile.json")
        profile["course_id"] = "another-course"
        self.write_json("learner-profile.json", profile)

        self.assertIn("course_id_mismatch", self.error_codes())

    def test_duplicate_knowledge_ids_are_invalid(self):
        curriculum = self.read_json("curriculum.json")
        curriculum["knowledge_nodes"] = [
            {"knowledge_id": "pv", "title": "Present value", "prerequisite_ids": []},
            {"knowledge_id": "pv", "title": "PV again", "prerequisite_ids": []},
        ]
        self.write_json("curriculum.json", curriculum)

        self.assertIn("duplicate_knowledge_id", self.error_codes())

    def test_missing_prerequisite_ids_are_invalid(self):
        curriculum = self.read_json("curriculum.json")
        curriculum["knowledge_nodes"] = [
            {
                "knowledge_id": "bond-pricing",
                "title": "Bond pricing",
                "prerequisite_ids": ["present-value"],
            }
        ]
        self.write_json("curriculum.json", curriculum)

        self.assertIn("missing_prerequisite", self.error_codes())

    def test_prerequisite_cycles_are_invalid(self):
        curriculum = self.read_json("curriculum.json")
        curriculum["knowledge_nodes"] = [
            {"knowledge_id": "a", "title": "A", "prerequisite_ids": ["b"]},
            {"knowledge_id": "b", "title": "B", "prerequisite_ids": ["a"]},
        ]
        self.write_json("curriculum.json", curriculum)

        self.assertIn("prerequisite_cycle", self.error_codes())

    def test_progress_for_unknown_knowledge_id_is_invalid(self):
        progress = self.read_json("progress.json")
        progress["knowledge"] = {"unknown": {"status": "unseen"}}
        self.write_json("progress.json", progress)

        self.assertIn("unknown_knowledge_id", self.error_codes())

    def test_invalid_owned_enum_is_invalid(self):
        course = self.read_json("course.json")
        course["session_depth"] = "enormous"
        self.write_json("course.json", course)

        self.assertIn("invalid_enum", self.error_codes())

    def test_invalid_owned_field_shape_is_invalid(self):
        profile = self.read_json("learner-profile.json")
        profile["goals"] = "learn everything"
        self.write_json("learner-profile.json", profile)

        self.assertIn("invalid_field", self.error_codes())

    def test_backbone_references_unknown_knowledge_id(self):
        curriculum = self.read_json("curriculum.json")
        curriculum["backbone"] = [
            {"lesson_id": "lesson-1", "title": "Lesson", "knowledge_ids": ["unknown"]}
        ]
        self.write_json("curriculum.json", curriculum)

        self.assertIn("unknown_knowledge_id", self.error_codes())

    def test_progress_timestamp_without_offset_is_invalid(self):
        curriculum = self.read_json("curriculum.json")
        curriculum["knowledge_nodes"] = [
            {"knowledge_id": "pv", "title": "Present value", "prerequisite_ids": []}
        ]
        self.write_json("curriculum.json", curriculum)
        progress = self.read_json("progress.json")
        progress["knowledge"] = {
            "pv": {"status": "learning", "next_review_at": "2026-09-12T09:00:00"}
        }
        self.write_json("progress.json", progress)

        self.assertIn("invalid_timestamp", self.error_codes())

    def test_attempt_timestamp_without_offset_is_invalid(self):
        attempt = {
            "schema_version": 1,
            "attempt_id": "attempt-001",
            "lesson_id": "lesson-001",
            "submitted_at": "2026-09-11T10:00:00",
            "responses": [],
        }
        (self.root / "attempts.jsonl").write_text(
            json.dumps(attempt) + "\n", encoding="utf-8"
        )

        self.assertIn("invalid_timestamp", self.error_codes())

    def test_malformed_json_lines_are_invalid(self):
        (self.root / "attempts.jsonl").write_text("{not json}\n", encoding="utf-8")

        self.assertIn("malformed_jsonl", self.error_codes())

    def test_attempt_error_reports_its_physical_line_number(self):
        invalid_timestamp = {
            "schema_version": 1,
            "attempt_id": "attempt-002",
            "lesson_id": "lesson-001",
            "submitted_at": "2026-09-11T10:00:00",
            "responses": [],
        }
        (self.root / "attempts.jsonl").write_text(
            "{not json}\n" + json.dumps(invalid_timestamp) + "\n", encoding="utf-8"
        )

        errors = course_state.validate_course(self.root)["errors"]
        timestamp_error = next(error for error in errors if error["code"] == "invalid_timestamp")
        self.assertEqual("line 2.submitted_at", timestamp_error["field"])

    def test_validation_does_not_mutate_course_files(self):
        paths = [self.root / name for name in (*course_state.STATE_FILES, "attempts.jsonl")]
        before = {path: path.read_bytes() for path in paths}

        course_state.validate_course(self.root)

        self.assertEqual(before, {path: path.read_bytes() for path in paths})


class NextSessionTests(CourseFixture):
    def test_next_session_orders_due_reviews_and_unlocks_backbone_lesson(self):
        curriculum = self.read_json("curriculum.json")
        curriculum["status"] = "approved"
        curriculum["knowledge_nodes"] = [
            {"knowledge_id": "pv", "title": "Present value", "prerequisite_ids": []},
            {"knowledge_id": "rates", "title": "Rates", "prerequisite_ids": []},
            {
                "knowledge_id": "bonds",
                "title": "Bond pricing",
                "prerequisite_ids": ["pv"],
            },
        ]
        curriculum["backbone"] = [
            {"lesson_id": "lesson-pv", "title": "Present value", "knowledge_ids": ["pv"]},
            {
                "lesson_id": "lesson-bonds",
                "title": "Bond pricing",
                "knowledge_ids": ["bonds"],
            },
        ]
        self.write_json("curriculum.json", curriculum)
        progress = self.read_json("progress.json")
        progress["completed_lessons"] = ["lesson-pv"]
        progress["knowledge"] = {
            "pv": {
                "status": "mastered",
                "next_review_at": "2026-09-11T08:30:00+08:00",
            },
            "rates": {
                "status": "mastered",
                "next_review_at": "2026-09-11T08:00:00+08:00",
            },
            "bonds": {
                "status": "learning",
                "next_review_at": "2026-09-12T08:00:00+08:00",
            },
        }
        self.write_json("progress.json", progress)
        attempts = [
            ["excluded-old-tag"],
            ["discounting-reversal"],
            [],
            ["sign-error"],
            ["discounting-reversal"],
            ["unit-confusion"],
        ]
        records = [
            {
                "schema_version": 1,
                "attempt_id": f"attempt-{index}",
                "lesson_id": "lesson-pv",
                "submitted_at": f"2026-09-11T0{index}:00:00+08:00",
                "responses": [],
                "misconception_tags": tags,
            }
            for index, tags in enumerate(attempts, start=1)
        ]
        (self.root / "attempts.jsonl").write_text(
            "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
        )

        result = course_state.next_session(self.root, "2026-09-11T09:00:00+08:00")

        self.assertEqual(["rates", "pv"], result["due_review_knowledge_ids"])
        self.assertEqual("lesson-bonds", result["next_backbone_lesson"]["lesson_id"])
        self.assertEqual(
            ["unit-confusion", "discounting-reversal", "sign-error"],
            result["recent_misconception_tags"],
        )

    def test_next_session_refuses_invalid_course_state(self):
        course = self.read_json("course.json")
        course["schema_version"] = 99
        self.write_json("course.json", course)

        with self.assertRaises(course_state.CourseStateError) as raised:
            course_state.next_session(self.root, "2026-09-11T09:00:00+08:00")

        self.assertEqual("invalid_course_state", raised.exception.code)


class RobustValidationTests(CourseFixture):
    def test_missing_progress_knowledge_is_invalid(self):
        progress = self.read_json("progress.json")
        del progress["knowledge"]
        self.write_json("progress.json", progress)
        report = course_state.validate_course(self.root)
        self.assertFalse(report["valid"])
        self.assertIn(("invalid_field", "knowledge"), {(e["code"], e.get("field")) for e in report["errors"]})
        with self.assertRaises(course_state.CourseStateError) as raised:
            course_state.next_session(self.root, CREATED_AT)
        self.assertEqual("invalid_course_state", raised.exception.code)

    def test_malformed_attempt_inspection_structures_are_rejected(self):
        cases = [
            ({"responses": value}, "responses")
            for value in (1, None, "answer", {})
        ] + [
            ({"responses": [value]}, "responses[0]")
            for value in (1, None, "answer", [])
        ] + [
            ({"misconception_tags": value}, "misconception_tags")
            for value in (1, None, "tag", {}, [1], [[]], [{}])
        ] + [
            ({"responses": [{"misconception_tags": value}]}, "responses[0].misconception_tags")
            for value in (1, None, "tag", {}, [1], [[]], [{}])
        ]
        for fields, field in cases:
            with self.subTest(fields=fields):
                record = {"schema_version": 1, **fields}
                (self.root / "attempts.jsonl").write_text(
                    json.dumps({"schema_version": 1}) + "\n" + json.dumps(record) + "\n",
                    encoding="utf-8",
                )
                report = course_state.validate_course(self.root)
                self.assertFalse(report["valid"])
                self.assertIn(("invalid_field", "line 2." + field), {(e["code"], e.get("field")) for e in report["errors"]})
                with self.assertRaises(course_state.CourseStateError) as raised:
                    course_state.next_session(self.root, CREATED_AT)
                self.assertEqual("invalid_course_state", raised.exception.code)

    def test_valid_optional_attempt_structures_are_inspectable(self):
        records = [
            {"schema_version": 1},
            {"schema_version": 1, "responses": []},
            {"schema_version": 1, "responses": [{}, {"misconception_tags": ["sign", "units"]}], "misconception_tags": ["units"]},
        ]
        (self.root / "attempts.jsonl").write_text(
            "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
        )
        self.assertTrue(course_state.validate_course(self.root)["valid"])
        self.assertEqual(["units", "sign"], course_state.next_session(self.root, CREATED_AT)["recent_misconception_tags"])

    def test_non_string_enums_return_validation_errors(self):
        curriculum = self.read_json("curriculum.json")
        curriculum["knowledge_nodes"] = [{"knowledge_id": "pv", "prerequisite_ids": []}]
        self.write_json("curriculum.json", curriculum)
        progress = self.read_json("progress.json")
        progress["knowledge"] = {"pv": {"status": "learning"}}
        self.write_json("progress.json", progress)
        cases = [
            ("course.json", ("status",), "status"),
            ("course.json", ("session_depth",), "session_depth"),
            ("curriculum.json", ("status",), "status"),
            ("progress.json", ("knowledge", "pv", "status"), "knowledge.pv.status"),
        ]
        for name, keys, field in cases:
            original = self.read_json(name)
            for value in ([], {}, None, 1, True):
                with self.subTest(name=name, field=field, value=value):
                    document = self.read_json(name)
                    entry = document
                    for key in keys[:-1]:
                        entry = entry[key]
                    entry[keys[-1]] = value
                    self.write_json(name, document)
                    try:
                        report = course_state.validate_course(self.root)
                        self.assertFalse(report["valid"])
                        self.assertIn(("invalid_enum", field), {(e["code"], e.get("field")) for e in report["errors"]})
                        with self.assertRaises(course_state.CourseStateError) as raised:
                            course_state.next_session(self.root, CREATED_AT)
                        self.assertEqual("invalid_course_state", raised.exception.code)
                    finally:
                        self.write_json(name, original)


class ContainmentTests(CourseFixture):
    def escaped_resolution(self, name):
        resolve = Path.resolve

        def resolve_path(path, *args, **kwargs):
            if path == self.root / name:
                return resolve(self.root.parent / name)
            return resolve(path, *args, **kwargs)

        return patch.object(Path, "resolve", resolve_path)

    def test_owned_state_paths_cannot_resolve_outside_root(self):
        for name in (*course_state.STATE_FILES, "attempts.jsonl"):
            with self.subTest(name=name):
                with self.escaped_resolution(name):
                    report = course_state.validate_course(self.root)
                    self.assertFalse(report["valid"])
                    self.assertIn("path_outside_root", {e["code"] for e in report["errors"]})
                    with self.assertRaises(course_state.CourseStateError) as raised:
                        course_state.next_session(self.root, CREATED_AT)
                    self.assertEqual("invalid_course_state", raised.exception.code)

    def test_next_session_checks_paths_again_after_validation(self):
        validate = course_state.validate_course
        for name in ("curriculum.json", "progress.json", "attempts.jsonl"):
            with self.subTest(name=name):
                def validate_then_replace(root):
                    report = validate(root)
                    escaped.start()
                    return report

                escaped = self.escaped_resolution(name)
                try:
                    with patch.object(course_state, "validate_course", validate_then_replace):
                        with self.assertRaises(course_state.CourseStateError):
                            course_state.next_session(self.root, CREATED_AT)
                finally:
                    escaped.stop()


class CommandLineTests(unittest.TestCase):
    script = SCRIPTS_DIR / "course_state.py"

    def run_cli(self, *arguments):
        return subprocess.run(
            [sys.executable, str(self.script), *map(str, arguments)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )

    def test_successful_commands_print_one_json_object(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "finance"
            initialized = self.run_cli(
                "init",
                "--root",
                root,
                "--slug",
                "finance",
                "--title",
                "Finance",
                "--created-at",
                CREATED_AT,
            )
            validated = self.run_cli("validate", "--root", root)
            inspected = self.run_cli(
                "next-session", "--root", root, "--now", CREATED_AT
            )

            self.assertEqual(0, initialized.returncode, initialized.stderr)
            self.assertEqual("finance", json.loads(initialized.stdout)["course_id"])
            self.assertEqual(0, validated.returncode, validated.stderr)
            self.assertTrue(json.loads(validated.stdout)["valid"])
            self.assertEqual(0, inspected.returncode, inspected.stderr)
            self.assertEqual([], json.loads(inspected.stdout)["due_review_knowledge_ids"])
            self.assertEqual("", initialized.stderr + validated.stderr + inspected.stderr)

    def test_domain_error_prints_json_to_stderr_and_exits_two(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "existing"
            root.mkdir()
            (root / "keep.txt").write_text("user data", encoding="utf-8")

            result = self.run_cli(
                "init",
                "--root",
                root,
                "--slug",
                "finance",
                "--title",
                "Finance",
                "--created-at",
                CREATED_AT,
            )

            self.assertEqual(2, result.returncode)
            self.assertEqual("", result.stdout)
            error = json.loads(result.stderr)
            self.assertEqual(False, error["ok"])
            self.assertEqual("course_directory_not_empty", error["error"]["code"])
            self.assertEqual(str(root), error["error"]["path"])

    def test_invalid_validation_exits_two_with_domain_error(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "missing"
            result = self.run_cli("validate", "--root", root)
            self.assertEqual(2, result.returncode)
            self.assertEqual("", result.stdout)
            error = json.loads(result.stderr)
            self.assertFalse(error["ok"])
            self.assertEqual("invalid_course_state", error["error"]["code"])
            self.assertEqual(str(root), error["error"]["path"])


if __name__ == "__main__":
    unittest.main()
