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
