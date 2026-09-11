"""Deterministic, dependency-free storage for deep-course state."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
COURSE_STATUSES = {
    "onboarding",
    "planning",
    "awaiting_approval",
    "active",
    "paused",
    "completed",
}
SESSION_DEPTHS = {"light", "normal", "deep"}
CURRICULUM_STATUSES = {"draft", "proposed", "approved"}
KNOWLEDGE_STATUSES = {"unseen", "learning", "relearning", "reviewing", "mastered"}
STATE_FILES = (
    "course.json",
    "learner-profile.json",
    "curriculum.json",
    "progress.json",
)


class CourseStateError(Exception):
    """A domain error that can be serialized by the command-line adapter."""

    def __init__(self, code: str, message: str, path: Path | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.path = path


def atomic_write_json(path: Path, value: Any) -> None:
    """Write one JSON document by syncing and replacing a temporary sibling."""

    path = Path(path)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            json.dump(value, temporary, ensure_ascii=False, indent=2)
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, path)
    except Exception:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise


def _atomic_write_text(path: Path, value: str) -> None:
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(value)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, path)
    except Exception:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise


def init_course(root: Path, slug: str, title: str, created_at: str) -> dict:
    root = Path(root)
    if _timestamp(created_at) is None:
        raise CourseStateError(
            "invalid_timestamp",
            "created_at must be an ISO 8601 timestamp with an explicit offset",
        )
    if root.exists() and (not root.is_dir() or any(root.iterdir())):
        raise CourseStateError(
            "course_directory_not_empty",
            f"course directory is not empty: {root}",
            root,
        )

    root.mkdir(parents=True, exist_ok=True)
    (root / "research").mkdir()
    (root / "lessons").mkdir()

    course = {
        "schema_version": SCHEMA_VERSION,
        "course_id": slug,
        "title": title,
        "created_at": created_at,
        "status": "onboarding",
        "session_depth": "normal",
    }
    learner_profile = {
        "schema_version": SCHEMA_VERSION,
        "course_id": slug,
        "goals": [],
        "prior_knowledge": [],
        "constraints": [],
    }
    curriculum = {
        "schema_version": SCHEMA_VERSION,
        "course_id": slug,
        "status": "draft",
        "learning_outcomes": [],
        "modules": [],
        "knowledge_nodes": [],
        "backbone": [],
    }
    progress = {
        "schema_version": SCHEMA_VERSION,
        "course_id": slug,
        "knowledge": {},
        "completed_lessons": [],
    }

    atomic_write_json(root / "course.json", course)
    atomic_write_json(root / "learner-profile.json", learner_profile)
    atomic_write_json(root / "curriculum.json", curriculum)
    atomic_write_json(root / "progress.json", progress)
    _atomic_write_text(root / "attempts.jsonl", "")
    return course


def _issue(code: str, message: str, path: Path, field: str | None = None) -> dict:
    issue = {"code": code, "message": message, "path": str(path)}
    if field is not None:
        issue["field"] = field
    return issue


def _read_json_document(path: Path, errors: list[dict]) -> dict | None:
    if not path.is_file():
        errors.append(_issue("missing_file", f"missing {path.name}", path))
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        errors.append(_issue("malformed_json", f"cannot read {path.name}: {error}", path))
        return None
    if not isinstance(value, dict):
        errors.append(
            _issue("invalid_document", f"{path.name} must contain a JSON object", path)
        )
        return None
    return value


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or "T" not in value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _check_schema(document: dict, path: Path, errors: list[dict]) -> None:
    version = document.get("schema_version")
    if type(version) is not int or version != SCHEMA_VERSION:
        errors.append(
            _issue(
                "unsupported_schema_version",
                f"unsupported schema_version {version!r}; expected {SCHEMA_VERSION}",
                path,
                "schema_version",
            )
        )


def _check_enum(
    document: dict,
    field: str,
    allowed: set[str],
    path: Path,
    errors: list[dict],
) -> None:
    value = document.get(field)
    if value not in allowed:
        errors.append(
            _issue(
                "invalid_enum",
                f"{field} must be one of {', '.join(sorted(allowed))}",
                path,
                field,
            )
        )


def _check_list_fields(
    document: dict, fields: tuple[str, ...], path: Path, errors: list[dict]
) -> None:
    for field in fields:
        if not isinstance(document.get(field), list):
            errors.append(
                _issue("invalid_field", f"{field} must be a list", path, field)
            )


def _read_attempts(path: Path, errors: list[dict]) -> list[tuple[int, dict]]:
    if not path.is_file():
        errors.append(_issue("missing_file", "missing attempts.jsonl", path))
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        errors.append(_issue("malformed_jsonl", f"cannot read attempts.jsonl: {error}", path))
        return []

    records = []
    for line_number, line in enumerate(lines, start=1):
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            errors.append(
                _issue(
                    "malformed_jsonl",
                    f"attempts.jsonl line {line_number} is not valid JSON: {error.msg}",
                    path,
                    f"line {line_number}",
                )
            )
            continue
        if not isinstance(record, dict):
            errors.append(
                _issue(
                    "malformed_jsonl",
                    f"attempts.jsonl line {line_number} must contain a JSON object",
                    path,
                    f"line {line_number}",
                )
            )
            continue
        records.append((line_number, record))
    return records


def _validate_knowledge_graph(curriculum: dict, path: Path, errors: list[dict]) -> set[str]:
    nodes = curriculum.get("knowledge_nodes", [])
    if not isinstance(nodes, list):
        errors.append(
            _issue("invalid_field", "knowledge_nodes must be a list", path, "knowledge_nodes")
        )
        return set()

    graph: dict[str, list[str]] = {}
    duplicate_ids: set[str] = set()
    for index, node in enumerate(nodes):
        if not isinstance(node, dict) or not isinstance(node.get("knowledge_id"), str):
            errors.append(
                _issue(
                    "invalid_field",
                    "each knowledge node must have a string knowledge_id",
                    path,
                    f"knowledge_nodes[{index}].knowledge_id",
                )
            )
            continue
        knowledge_id = node["knowledge_id"]
        if knowledge_id in graph:
            duplicate_ids.add(knowledge_id)
        prerequisites = node.get("prerequisite_ids", [])
        if not isinstance(prerequisites, list) or not all(
            isinstance(item, str) for item in prerequisites
        ):
            errors.append(
                _issue(
                    "invalid_field",
                    f"prerequisite_ids for {knowledge_id!r} must be a list of strings",
                    path,
                    f"knowledge_nodes[{index}].prerequisite_ids",
                )
            )
            prerequisites = []
        graph.setdefault(knowledge_id, prerequisites)

    for knowledge_id in sorted(duplicate_ids):
        errors.append(
            _issue(
                "duplicate_knowledge_id",
                f"duplicate knowledge_id {knowledge_id!r}",
                path,
                "knowledge_nodes",
            )
        )

    known_ids = set(graph)
    for knowledge_id, prerequisites in graph.items():
        for prerequisite_id in prerequisites:
            if prerequisite_id not in known_ids:
                errors.append(
                    _issue(
                        "missing_prerequisite",
                        f"knowledge node {knowledge_id!r} references missing prerequisite {prerequisite_id!r}",
                        path,
                        "knowledge_nodes",
                    )
                )

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(knowledge_id: str) -> bool:
        if knowledge_id in visiting:
            return True
        if knowledge_id in visited:
            return False
        visiting.add(knowledge_id)
        cycle_found = any(
            prerequisite_id in graph and visit(prerequisite_id)
            for prerequisite_id in graph[knowledge_id]
        )
        visiting.remove(knowledge_id)
        visited.add(knowledge_id)
        return cycle_found

    if any(visit(knowledge_id) for knowledge_id in graph if knowledge_id not in visited):
        errors.append(
            _issue(
                "prerequisite_cycle",
                "knowledge prerequisite graph contains a cycle",
                path,
                "knowledge_nodes",
            )
        )
    return known_ids


def validate_course(root: Path) -> dict:
    """Return all deterministic validation findings without modifying the course."""

    root = Path(root)
    errors: list[dict] = []
    documents = {
        name: _read_json_document(root / name, errors) for name in STATE_FILES
    }
    for name, document in documents.items():
        if document is not None:
            _check_schema(document, root / name, errors)

    course = documents["course.json"]
    course_id = course.get("course_id") if course is not None else None
    if course is not None:
        course_path = root / "course.json"
        if not isinstance(course_id, str) or not course_id:
            errors.append(
                _issue(
                    "invalid_field", "course_id must be a nonempty string", course_path, "course_id"
                )
            )
        if not isinstance(course.get("title"), str) or not course["title"]:
            errors.append(
                _issue("invalid_field", "title must be a nonempty string", course_path, "title")
            )
        if _timestamp(course.get("created_at")) is None:
            errors.append(
                _issue(
                    "invalid_timestamp",
                    "created_at must be an ISO 8601 timestamp with an explicit offset",
                    course_path,
                    "created_at",
                )
            )
        _check_enum(course, "status", COURSE_STATUSES, course_path, errors)
        _check_enum(course, "session_depth", SESSION_DEPTHS, course_path, errors)

    if isinstance(course_id, str):
        for name in STATE_FILES[1:]:
            document = documents[name]
            if document is not None and document.get("course_id") != course_id:
                errors.append(
                    _issue(
                        "course_id_mismatch",
                        f"{name} course_id does not match {course_id!r}",
                        root / name,
                        "course_id",
                    )
                )

    curriculum = documents["curriculum.json"]
    profile = documents["learner-profile.json"]
    if profile is not None:
        _check_list_fields(
            profile,
            ("goals", "prior_knowledge", "constraints"),
            root / "learner-profile.json",
            errors,
        )
    known_ids = (
        _validate_knowledge_graph(curriculum, root / "curriculum.json", errors)
        if curriculum is not None
        else set()
    )
    if curriculum is not None:
        curriculum_path = root / "curriculum.json"
        _check_enum(
            curriculum, "status", CURRICULUM_STATUSES, curriculum_path, errors
        )
        _check_list_fields(
            curriculum,
            ("learning_outcomes", "modules", "backbone"),
            curriculum_path,
            errors,
        )
        backbone = curriculum.get("backbone", [])
        if isinstance(backbone, list):
            for index, lesson in enumerate(backbone):
                field = f"backbone[{index}]"
                if not isinstance(lesson, dict):
                    errors.append(
                        _issue(
                            "invalid_field",
                            "each backbone entry must be an object",
                            curriculum_path,
                            field,
                        )
                    )
                    continue
                for string_field in ("lesson_id", "title"):
                    if not isinstance(lesson.get(string_field), str) or not lesson[string_field]:
                        errors.append(
                            _issue(
                                "invalid_field",
                                f"{string_field} must be a nonempty string",
                                curriculum_path,
                                f"{field}.{string_field}",
                            )
                        )
                for id_field in ("knowledge_ids", "prerequisite_knowledge_ids"):
                    if id_field not in lesson and id_field == "prerequisite_knowledge_ids":
                        continue
                    identifiers = lesson.get(id_field)
                    if not isinstance(identifiers, list) or not all(
                        isinstance(item, str) for item in identifiers
                    ):
                        errors.append(
                            _issue(
                                "invalid_field",
                                f"{id_field} must be a list of strings",
                                curriculum_path,
                                f"{field}.{id_field}",
                            )
                        )
                        continue
                    for knowledge_id in identifiers:
                        if knowledge_id not in known_ids:
                            errors.append(
                                _issue(
                                    "unknown_knowledge_id",
                                    f"backbone entry references unknown knowledge_id {knowledge_id!r}",
                                    curriculum_path,
                                    f"{field}.{id_field}",
                                )
                            )

    progress = documents["progress.json"]
    if progress is not None:
        completed_lessons = progress.get("completed_lessons")
        if not isinstance(completed_lessons, list) or not all(
            isinstance(item, str) for item in completed_lessons
        ):
            errors.append(
                _issue(
                    "invalid_field",
                    "completed_lessons must be a list of strings",
                    root / "progress.json",
                    "completed_lessons",
                )
            )
        knowledge = progress.get("knowledge", {})
        if not isinstance(knowledge, dict):
            errors.append(
                _issue(
                    "invalid_field",
                    "knowledge must be an object keyed by knowledge_id",
                    root / "progress.json",
                    "knowledge",
                )
            )
        else:
            for knowledge_id, entry in knowledge.items():
                if knowledge_id not in known_ids:
                    errors.append(
                        _issue(
                            "unknown_knowledge_id",
                            f"progress references unknown knowledge_id {knowledge_id!r}",
                            root / "progress.json",
                            f"knowledge.{knowledge_id}",
                        )
                    )
                if not isinstance(entry, dict):
                    errors.append(
                        _issue(
                            "invalid_field",
                            f"progress entry {knowledge_id!r} must be an object",
                            root / "progress.json",
                            f"knowledge.{knowledge_id}",
                        )
                    )
                    continue
                if "status" in entry and entry["status"] not in KNOWLEDGE_STATUSES:
                    errors.append(
                        _issue(
                            "invalid_enum",
                            "knowledge status must be one of "
                            + ", ".join(sorted(KNOWLEDGE_STATUSES)),
                            root / "progress.json",
                            f"knowledge.{knowledge_id}.status",
                        )
                    )
                for timestamp_field in ("last_practiced_at", "next_review_at"):
                    if timestamp_field in entry and _timestamp(entry[timestamp_field]) is None:
                        errors.append(
                            _issue(
                                "invalid_timestamp",
                                f"{timestamp_field} must be an ISO 8601 timestamp with an explicit offset",
                                root / "progress.json",
                                f"knowledge.{knowledge_id}.{timestamp_field}",
                            )
                        )

    attempts_path = root / "attempts.jsonl"
    attempts = _read_attempts(attempts_path, errors)
    for line_number, attempt in attempts:
        _check_schema(attempt, attempts_path, errors)
        if "course_id" in attempt and isinstance(course_id, str) and attempt["course_id"] != course_id:
            errors.append(
                _issue(
                    "course_id_mismatch",
                    f"attempts.jsonl line {line_number} course_id does not match {course_id!r}",
                    attempts_path,
                    f"line {line_number}.course_id",
                )
            )
        for timestamp_field in ("submitted_at", "occurred_at", "exported_at"):
            if timestamp_field in attempt and _timestamp(attempt[timestamp_field]) is None:
                errors.append(
                    _issue(
                        "invalid_timestamp",
                        f"{timestamp_field} must be an ISO 8601 timestamp with an explicit offset",
                        attempts_path,
                        f"line {line_number}.{timestamp_field}",
                    )
                )

    return {"valid": not errors, "errors": errors, "warnings": []}


def next_session(root: Path, now: str) -> dict:
    """Compute due reviews, the next unlocked lesson, and recent misconceptions."""

    root = Path(root)
    report = validate_course(root)
    if not report["valid"]:
        raise CourseStateError(
            "invalid_course_state",
            f"course state is invalid ({len(report['errors'])} error(s))",
            root,
        )
    now_value = _timestamp(now)
    if now_value is None:
        raise CourseStateError(
            "invalid_timestamp",
            "now must be an ISO 8601 timestamp with an explicit offset",
        )

    curriculum = json.loads((root / "curriculum.json").read_text(encoding="utf-8"))
    progress = json.loads((root / "progress.json").read_text(encoding="utf-8"))
    knowledge_progress = progress["knowledge"]
    due = []
    for knowledge_id, entry in knowledge_progress.items():
        due_at = entry.get("next_review_at")
        parsed_due_at = _timestamp(due_at)
        if parsed_due_at is not None and parsed_due_at <= now_value:
            due.append((parsed_due_at, knowledge_id))
    due.sort(key=lambda item: (item[0], item[1]))

    nodes = {
        node["knowledge_id"]: node
        for node in curriculum.get("knowledge_nodes", [])
        if isinstance(node, dict) and isinstance(node.get("knowledge_id"), str)
    }
    completed_lessons = set(progress.get("completed_lessons", []))
    next_lesson = None
    for lesson in curriculum.get("backbone", []):
        if not isinstance(lesson, dict) or lesson.get("lesson_id") in completed_lessons:
            continue
        prerequisite_ids = set(lesson.get("prerequisite_knowledge_ids", []))
        for knowledge_id in lesson.get("knowledge_ids", []):
            prerequisite_ids.update(nodes.get(knowledge_id, {}).get("prerequisite_ids", []))
        if all(
            knowledge_progress.get(prerequisite_id, {}).get("status") == "mastered"
            for prerequisite_id in prerequisite_ids
        ):
            next_lesson = lesson
            break

    attempt_errors: list[dict] = []
    attempts = _read_attempts(root / "attempts.jsonl", attempt_errors)
    recent_tags = []
    seen_tags = set()
    for _, attempt in reversed(attempts[-5:]):
        tag_groups = [attempt.get("misconception_tags", [])]
        tag_groups.extend(
            response.get("misconception_tags", [])
            for response in attempt.get("responses", [])
            if isinstance(response, dict)
        )
        for tags in tag_groups:
            if not isinstance(tags, list):
                continue
            for tag in tags:
                if isinstance(tag, str) and tag not in seen_tags:
                    seen_tags.add(tag)
                    recent_tags.append(tag)

    return {
        "course_id": curriculum["course_id"],
        "due_review_knowledge_ids": [knowledge_id for _, knowledge_id in due],
        "next_backbone_lesson": next_lesson,
        "recent_misconception_tags": recent_tags,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Initialize and inspect deep-course state")
    commands = parser.add_subparsers(dest="command", required=True)

    initialize = commands.add_parser("init", help="initialize a new course directory")
    initialize.add_argument("--root", required=True, type=Path)
    initialize.add_argument("--slug", required=True)
    initialize.add_argument("--title", required=True)
    initialize.add_argument("--created-at", required=True)

    validate = commands.add_parser("validate", help="validate an existing course")
    validate.add_argument("--root", required=True, type=Path)

    inspect = commands.add_parser("next-session", help="inspect the next course session")
    inspect.add_argument("--root", required=True, type=Path)
    inspect.add_argument("--now", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        if arguments.command == "init":
            result = init_course(
                arguments.root, arguments.slug, arguments.title, arguments.created_at
            )
        elif arguments.command == "validate":
            result = validate_course(arguments.root)
        else:
            result = next_session(arguments.root, arguments.now)
    except CourseStateError as error:
        response = {
            "ok": False,
            "error": {
                "code": error.code,
                "message": error.message,
                "path": str(error.path) if error.path is not None else None,
            },
        }
        print(json.dumps(response, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2

    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
