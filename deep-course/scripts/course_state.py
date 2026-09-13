"""Deterministic, dependency-free storage for deep-course state."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath
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
EVIDENCE_QUALITIES = {"incorrect", "partial", "correct", "effortless"}
LESSON_STATUSES = ("draft", "ready", "delivered", "assessed")
CORE_ARTIFACTS = {"lesson.html", "lesson.md", "exercises.md", "answers.md", "sources.md", "state.json"}
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


def _owned_path(root: Path, path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise CourseStateError("path_outside_root", "owned state path resolves outside course root", path)
    return resolved


def _read_json_document(root: Path, path: Path, errors: list[dict]) -> dict | None:
    try:
        read_path = _owned_path(root, path)
    except CourseStateError as error:
        errors.append(_issue(error.code, error.message, path))
        return None
    if not path.is_file():
        errors.append(_issue("missing_file", f"missing {path.name}", path))
        return None
    try:
        value = json.loads(read_path.read_text(encoding="utf-8"))
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
    if not isinstance(value, str) or value not in allowed:
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


def _read_attempts(root: Path, path: Path, errors: list[dict]) -> list[tuple[int, dict]]:
    try:
        read_path = _owned_path(root, path)
    except CourseStateError as error:
        errors.append(_issue(error.code, error.message, path))
        return []
    if not path.is_file():
        errors.append(_issue("missing_file", "missing attempts.jsonl", path))
        return []
    try:
        lines = read_path.read_text(encoding="utf-8").split("\n")
        if lines and lines[-1] == "":
            lines.pop()
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


def _check_misconception_tags(document: dict, path: Path, field: str, errors: list[dict]) -> None:
    if "misconception_tags" not in document:
        return
    tags = document["misconception_tags"]
    if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
        errors.append(_issue("invalid_field", "misconception_tags must be a list of strings", path, field))


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


def _validate_mastery_fields(progress: dict, path: Path, errors: list[dict]) -> None:
    applied = progress.get("applied_attempt_ids", [])
    if (not isinstance(applied, list) or not all(isinstance(item, str) and item for item in applied)
            or len(applied) != len(set(applied))):
        errors.append(_issue("invalid_field", "applied_attempt_ids must contain unique strings", path))
    knowledge = progress.get("knowledge", {})
    if not isinstance(knowledge, dict):
        return
    for knowledge_id, entry in knowledge.items():
        if not isinstance(entry, dict):
            continue
        for field in ("mastery", "confidence"):
            value = entry.get(field, 0.0)
            if type(value) not in (int, float) or not 0 <= value <= 1:
                errors.append(_issue("invalid_field", f"{field} must be a finite number in [0, 1]", path,
                                     f"knowledge.{knowledge_id}.{field}"))
        interval = entry.get("interval_days", 0)
        if type(interval) is not int or interval < 0:
            errors.append(_issue("invalid_field", "interval_days must be a nonnegative integer", path,
                                 f"knowledge.{knowledge_id}.interval_days"))
        evidence = entry.get("evidence", [])
        if not isinstance(evidence, list):
            errors.append(_issue("invalid_field", "evidence must be a list", path))
            continue
        seen = set()
        for item in evidence:
            if (not isinstance(item, dict) or not isinstance(item.get("attempt_id"), str)
                    or not item["attempt_id"] or not isinstance(item.get("quality"), str)
                    or item["quality"] not in EVIDENCE_QUALITIES
                    or _timestamp(item.get("occurred_at")) is None
                    or (item.get("question_id") is not None and not isinstance(item["question_id"], str))):
                errors.append(_issue("invalid_field", "malformed mastery evidence", path))
                continue
            key = (item["attempt_id"], item.get("question_id"))
            if key in seen:
                errors.append(_issue("duplicate_evidence", "duplicate mastery evidence", path))
            seen.add(key)


def validate_course(root: Path) -> dict:
    """Return all deterministic validation findings without modifying the course."""

    return _validate_course(root)


def _validate_course(root: Path, progress_override: dict | None = None) -> dict:

    root = Path(root)
    errors: list[dict] = []
    documents = {
        name: _read_json_document(root, root / name, errors) for name in STATE_FILES
    }
    if progress_override is not None:
        documents["progress.json"] = progress_override
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
        _validate_mastery_fields(progress, root / "progress.json", errors)
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
        knowledge = progress.get("knowledge")
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
                if "status" in entry and (
                    not isinstance(entry["status"], str)
                    or entry["status"] not in KNOWLEDGE_STATUSES
                ):
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
    attempts = _read_attempts(root, attempts_path, errors)
    recorded_ids = set()
    for line_number, attempt in attempts:
        _check_schema(attempt, attempts_path, errors)
        field = f"line {line_number}"
        if "attempt_id" in attempt:
            try:
                _checked_payload(attempt)
                _check_new_attempt(attempt, course_id, known_ids)
                if attempt["attempt_id"] in recorded_ids:
                    raise CourseStateError("duplicate_attempt_id", "duplicate recorded attempt_id")
                recorded_ids.add(attempt["attempt_id"])
            except CourseStateError as error:
                error_field = field
                if error.code == "invalid_timestamp":
                    invalid_timestamp = next(name for name in ("submitted_at", "occurred_at", "exported_at")
                                             if (name == "submitted_at" or name in attempt)
                                             and _timestamp(attempt.get(name)) is None)
                    error_field = f"{field}.{invalid_timestamp}"
                errors.append(_issue(error.code, error.message, attempts_path, error_field))
        _check_misconception_tags(attempt, attempts_path, f"{field}.misconception_tags", errors)
        responses = attempt.get("responses", [])
        if not isinstance(responses, list):
            errors.append(_issue("invalid_field", "responses must be a list of objects", attempts_path, f"{field}.responses"))
        else:
            for index, response in enumerate(responses):
                response_field = f"{field}.responses[{index}]"
                if not isinstance(response, dict):
                    errors.append(_issue("invalid_field", "response must be an object", attempts_path, response_field))
                    continue
                _check_misconception_tags(response, attempts_path, f"{response_field}.misconception_tags", errors)
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

    if progress is not None:
        applied = progress.get("applied_attempt_ids", [])
        if isinstance(applied, list):
            for identifier in applied:
                if isinstance(identifier, str) and identifier not in recorded_ids:
                    errors.append(_issue("unknown_attempt_id", "applied attempt is not recorded", root / "progress.json"))
        knowledge = progress.get("knowledge", {})
        if isinstance(knowledge, dict):
            for entry in knowledge.values():
                if not isinstance(entry, dict) or not isinstance(entry.get("evidence", []), list):
                    continue
                for item in entry.get("evidence", []):
                    if not isinstance(item, dict) or not isinstance(item.get("attempt_id"), str):
                        continue
                    if item["attempt_id"] not in recorded_ids or not isinstance(applied, list) or item["attempt_id"] not in applied:
                        errors.append(_issue("invalid_evidence", "evidence must reference a recorded applied attempt", root / "progress.json"))

    return {"valid": not errors, "errors": errors, "warnings": []}


def _checked_payload(value: Any) -> str:
    """Reject path injection and serialize fully before opening any output."""
    def check(item: Any) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                if not isinstance(key, str):
                    raise CourseStateError("invalid_field", "JSON object keys must be strings")
                if key in {"path", "paths"} or key.endswith(("_path", "_paths")):
                    raise CourseStateError("injected_path_field", "records cannot supply filesystem path fields")
                check(child)
        elif isinstance(item, (list, tuple)):
            for child in item:
                check(child)
    try:
        check(value)
        serialized = json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        serialized.encode("utf-8")
        return serialized
    except (TypeError, ValueError, RecursionError, UnicodeError) as error:
        raise CourseStateError("invalid_field", "record must contain finite, serializable JSON values") from error


def _check_grading_fields(value: dict) -> None:
    if "quality" in value and (not isinstance(value["quality"], str) or value["quality"] not in EVIDENCE_QUALITIES):
        raise CourseStateError("invalid_quality", "quality must be incorrect, partial, correct, or effortless")
    if "misconception_tags" in value and (not isinstance(value["misconception_tags"], list)
            or not all(isinstance(tag, str) for tag in value["misconception_tags"])):
        raise CourseStateError("invalid_field", "misconception_tags must be a list of strings")
    if "feedback" in value and not isinstance(value["feedback"], str):
        raise CourseStateError("invalid_field", "feedback must be a string")


def _check_new_attempt(attempt: dict, course_id: str, known_ids: set[str]) -> None:
    if type(attempt.get("schema_version")) is not int or attempt["schema_version"] != SCHEMA_VERSION:
        raise CourseStateError("unsupported_schema_version", "attempt schema_version must be integer 1")
    for field in ("attempt_id", "lesson_id"):
        if not isinstance(attempt.get(field), str) or not attempt[field]:
            raise CourseStateError("invalid_field", f"{field} must be a nonempty string")
    if "course_id" in attempt and attempt["course_id"] != course_id:
        raise CourseStateError("course_id_mismatch", "attempt belongs to another course")
    for field in ("submitted_at", "occurred_at", "exported_at"):
        if (field == "submitted_at" or field in attempt) and _timestamp(attempt.get(field)) is None:
            raise CourseStateError("invalid_timestamp", f"{field} must have an explicit timezone offset")
    _check_grading_fields(attempt)
    responses = attempt.get("responses")
    if not isinstance(responses, list):
        raise CourseStateError("invalid_field", "responses must be a list")
    seen = set()
    for response in responses:
        if not isinstance(response, dict):
            raise CourseStateError("invalid_field", "each response must be an object")
        question_id = response.get("question_id")
        if not isinstance(question_id, str) or not question_id or "answer" not in response:
            raise CourseStateError("invalid_field", "each response requires question_id and answer")
        if question_id in seen:
            raise CourseStateError("duplicate_question_id", "response question_ids must be unique")
        seen.add(question_id)
        ids = response.get("knowledge_ids")
        if not isinstance(ids, list) or not all(isinstance(item, str) for item in ids):
            raise CourseStateError("invalid_field", "knowledge_ids must be a list of strings")
        if any(item not in known_ids for item in ids):
            raise CourseStateError("unknown_knowledge_id", "attempt references unknown knowledge_id")
        _check_grading_fields(response)


def append_attempt(root: Path, attempt: dict) -> dict:
    """Validate and append one immutable attempt record."""

    root = Path(root)
    report = validate_course(root)
    if not report["valid"]:
        raise CourseStateError(
            "invalid_course_state",
            f"course state is invalid ({len(report['errors'])} error(s))",
            root,
        )
    if not isinstance(attempt, dict):
        raise CourseStateError("invalid_field", "attempt must be an object")

    serialized = _checked_payload(attempt)
    curriculum_path = root / "curriculum.json"
    curriculum = json.loads(_owned_path(root, curriculum_path).read_text(encoding="utf-8"))
    known_ids = {
        node["knowledge_id"] for node in curriculum["knowledge_nodes"]
    }
    _check_new_attempt(attempt, curriculum["course_id"], known_ids)
    attempt_id = attempt["attempt_id"]

    attempts_path = root / "attempts.jsonl"
    errors: list[dict] = []
    attempts = _read_attempts(root, attempts_path, errors)
    if errors:
        raise CourseStateError("invalid_course_state", "cannot append to attempts", attempts_path)
    if any(record.get("attempt_id") == attempt_id for _, record in attempts):
        raise CourseStateError(
            "duplicate_attempt_id", f"duplicate attempt_id {attempt_id!r}", attempts_path
        )

    write_path = _owned_path(root, attempts_path)
    # A valid externally supplied JSONL file may lack its final line separator.
    existing = write_path.read_bytes()
    prefix = "\n" if existing and not existing.endswith((b"\n", b"\r")) else ""
    with write_path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(prefix + serialized + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return {"attempt_id": attempt_id, "line_index": len(attempts)}


def apply_mastery_updates(root: Path, attempt_id: str, updates: list[dict], occurred_at: str) -> dict:
    """Apply Codex-judged evidence and review math in one progress transaction."""
    root = Path(root)
    if not validate_course(root)["valid"]:
        raise CourseStateError("invalid_course_state", "course state is invalid", root)
    occurred = _timestamp(occurred_at)
    if occurred is None:
        raise CourseStateError("invalid_timestamp", "occurred_at must have an explicit timezone offset")
    if not isinstance(attempt_id, str) or not attempt_id:
        raise CourseStateError("invalid_field", "attempt_id must be a nonempty string")
    _checked_payload(updates)
    if not isinstance(updates, list) or not updates:
        raise CourseStateError("invalid_field", "updates must be a nonempty list")

    errors: list[dict] = []
    attempts = _read_attempts(root, root / "attempts.jsonl", errors)
    if errors:
        raise CourseStateError("invalid_course_state", "cannot read attempts", root)
    matches = [record for _, record in attempts if record.get("attempt_id") == attempt_id]
    if len(matches) != 1:
        raise CourseStateError("unknown_attempt_id", "attempt_id must identify exactly one recorded attempt")
    attempt = matches[0]
    progress_path = root / "progress.json"
    progress = json.loads(_owned_path(root, progress_path).read_text(encoding="utf-8"))
    applied = progress.setdefault("applied_attempt_ids", [])
    if attempt_id in applied:
        raise CourseStateError("duplicate_application", f"attempt {attempt_id!r} was already applied")
    curriculum = json.loads(_owned_path(root, root / "curriculum.json").read_text(encoding="utf-8"))
    known_ids = {node["knowledge_id"] for node in curriculum["knowledge_nodes"]}
    responses = {response.get("question_id"): response for response in attempt.get("responses", [])
                 if isinstance(response.get("question_id"), str)}
    seen: dict[str, set[str | None]] = {}
    for update in updates:
        if not isinstance(update, dict):
            raise CourseStateError("invalid_field", "each update must be an object")
        knowledge_id = update.get("knowledge_id")
        if not isinstance(knowledge_id, str) or knowledge_id not in known_ids:
            raise CourseStateError("unknown_knowledge_id", "update references unknown knowledge_id")
        if "quality" not in update:
            raise CourseStateError("invalid_quality", "quality is required")
        _check_grading_fields(update)
        question_id = update.get("question_id")
        if "question_id" in update and (not isinstance(question_id, str) or not question_id):
            raise CourseStateError("invalid_field", "question_id must be a nonempty string when supplied")
        if question_id is not None and (question_id not in responses
                or knowledge_id not in responses[question_id].get("knowledge_ids", [])):
            raise CourseStateError("invalid_evidence", "question evidence must match the recorded response and knowledge ID")
        previous = seen.setdefault(knowledge_id, set())
        if question_id in previous or (previous and (question_id is None or None in previous)):
            raise CourseStateError("duplicate_evidence", "duplicate or overlapping evidence for one knowledge node")
        previous.add(question_id)

    deltas = {"incorrect": (-0.20, 0.05), "partial": (0.05, 0.05),
              "correct": (0.15, 0.10), "effortless": (0.20, 0.10)}
    for update in updates:
        knowledge_id, quality = update["knowledge_id"], update["quality"]
        entry = progress["knowledge"].setdefault(knowledge_id, {})
        last = _timestamp(entry.get("last_practiced_at"))
        if last is not None and occurred < last:
            raise CourseStateError("out_of_order_evidence", "evidence cannot precede the last practice time")
        mastery_delta, confidence_delta = deltas[quality]
        entry["mastery"] = round(max(0.0, min(1.0, entry.get("mastery", 0.0) + mastery_delta)), 10)
        entry["confidence"] = round(max(0.0, min(1.0, entry.get("confidence", 0.0) + confidence_delta)), 10)
        previous_interval = entry.get("interval_days", 0)
        interval = {"incorrect": 1, "partial": 2,
                    "correct": max(3, previous_interval * 2),
                    "effortless": max(5, previous_interval * 3)}[quality]
        try:
            next_review_at = (occurred + timedelta(days=interval)).isoformat()
        except (OverflowError, ValueError) as error:
            raise CourseStateError("invalid_interval", "review date exceeds supported datetime range") from error
        entry.update(interval_days=interval, last_practiced_at=occurred_at, next_review_at=next_review_at)
        evidence = entry.setdefault("evidence", [])
        evidence.append({"attempt_id": attempt_id, "occurred_at": occurred_at, "quality": quality,
                         **{field: update[field] for field in ("question_id", "misconception_tags", "feedback")
                            if field in update}})
        successes = [item for item in evidence if item["quality"] in {"correct", "effortless"}]
        if quality == "incorrect":
            entry["status"] = "relearning"
        elif entry["mastery"] < 0.75:
            entry["status"] = "learning"
        elif entry["mastery"] >= 0.90 and len(successes) >= 3 and len({item["attempt_id"] for item in successes}) >= 2:
            entry["status"] = "mastered"
        else:
            entry["status"] = "reviewing"
    applied.append(attempt_id)
    if not _validate_course(root, progress_override=progress)["valid"]:
        raise CourseStateError("invalid_course_state", "resulting progress is invalid", progress_path)
    atomic_write_json(_owned_path(root, progress_path), progress)
    changed = list(seen)
    return {"attempt_id": attempt_id, "changed_knowledge_ids": changed,
            "next_review_at": {key: progress["knowledge"][key]["next_review_at"] for key in changed}}


def _lesson_relative_path(root: Path, value: Any, directory: str | None = None) -> Path:
    if (not isinstance(value, str) or not value or "\\" in value or ":" in value
            or "\x00" in value or PurePosixPath(value).is_absolute()
            or ".." in value.split("/")):
        raise CourseStateError("invalid_artifact_path", "lesson paths must be relative POSIX descendants")
    relative = PurePosixPath(value)
    if (len(relative.parts) < 2 or relative.parts[0] != "lessons"
            or (directory is None and len(relative.parts) != 2)):
        raise CourseStateError("invalid_artifact_path", "lesson_directory must be lessons/<lesson-directory>")
    root = root.resolve()
    try:
        resolved = (root / relative).resolve()
    except (OSError, RuntimeError, ValueError) as error:
        raise CourseStateError("invalid_artifact_path", "cannot resolve lesson path") from error
    expected = root / (PurePosixPath(directory) if directory is not None else relative)
    if (not resolved.is_relative_to(root) or not resolved.is_relative_to(expected)
            or (directory is not None and resolved == expected)
            or (directory is None and resolved != expected)):
        raise CourseStateError("invalid_artifact_path", "artifact resolves outside its lesson directory")
    return resolved


def _lesson_manifest_shape(root: Path, manifest: dict, course_id: str) -> dict:
    allowed = {"schema_version", "course_id", "lesson_id", "lesson_directory", "status",
               "learning_objectives", "artifacts", "delivered_at", "attempt_ids"}
    if not isinstance(manifest, dict) or any(key not in allowed for key in manifest):
        raise CourseStateError("invalid_field", "lesson manifest has unknown fields or is not an object")
    if type(manifest.get("schema_version")) is not int or manifest["schema_version"] != SCHEMA_VERSION:
        raise CourseStateError("unsupported_schema_version", "lesson schema_version must be integer 1")
    if manifest.get("course_id") != course_id:
        raise CourseStateError("course_id_mismatch", "lesson belongs to another course")
    if not isinstance(manifest.get("lesson_id"), str) or not manifest["lesson_id"].strip():
        raise CourseStateError("invalid_field", "lesson_id must be a nonempty string")
    if not isinstance(manifest.get("status"), str) or manifest["status"] not in LESSON_STATUSES:
        raise CourseStateError("invalid_enum", "lesson status must be draft, ready, delivered, or assessed")
    lesson_dir = _lesson_relative_path(root, manifest.get("lesson_directory"))
    directory = lesson_dir.relative_to(root.resolve()).as_posix()
    objectives = manifest.get("learning_objectives")
    if not isinstance(objectives, list) or not all(isinstance(item, str) and item.strip() for item in objectives):
        raise CourseStateError("invalid_field", "learning_objectives must be a list of nonempty strings")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        raise CourseStateError("invalid_field", "artifacts must be a list")
    normalized_artifacts = []
    seen = set()
    for artifact in artifacts:
        if not isinstance(artifact, dict) or set(artifact) - {"path", "sha256"}:
            raise CourseStateError("invalid_field", "each artifact requires path and, except state.json, sha256")
        path = _lesson_relative_path(root, artifact.get("path"), directory)
        relative = path.relative_to(root.resolve()).as_posix()
        if relative in seen:
            raise CourseStateError("duplicate_artifact_path", "artifact paths must be unique")
        seen.add(relative)
        item = {"path": relative}
        if path == lesson_dir / "state.json":
            if "sha256" in artifact:
                raise CourseStateError("invalid_artifact_hash", "state.json cannot contain a hash of itself")
        else:
            digest = artifact.get("sha256")
            if (not isinstance(digest, str) or len(digest) != 64
                    or any(char not in "0123456789abcdefABCDEF" for char in digest)):
                raise CourseStateError("invalid_artifact_hash", "artifact sha256 must be a 64-digit hexadecimal string")
            item["sha256"] = digest.lower()
        normalized_artifacts.append(item)
    result = {**manifest, "lesson_directory": directory, "artifacts": normalized_artifacts,
              "learning_objectives": list(objectives)}
    # Complete preflight before atomic_write_json opens a temporary output.
    try:
        json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError) as error:
        raise CourseStateError("invalid_field", "manifest must contain valid finite JSON") from error
    return result


def _check_lesson_artifacts(root: Path, manifest: dict) -> None:
    directory = manifest["lesson_directory"]
    if manifest["status"] != "draft":
        supplied = {item["path"] for item in manifest["artifacts"]}
        missing = sorted(f"{directory}/{name}" for name in CORE_ARTIFACTS if f"{directory}/{name}" not in supplied)
        if missing:
            raise CourseStateError("missing_core_artifact", "missing core artifact: " + ", ".join(missing))
        if not manifest["learning_objectives"]:
            raise CourseStateError("invalid_field", "ready lessons require nonempty learning_objectives")
    for item in manifest["artifacts"]:
        path = _lesson_relative_path(root, item["path"], directory)
        if item["path"] == f"{directory}/state.json":
            continue  # Written atomically from this manifest; a self hash is impossible.
        if not path.is_file():
            raise CourseStateError("missing_artifact", f"missing artifact {item['path']}", path)
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as error:
            raise CourseStateError("unreadable_artifact", f"cannot read artifact {item['path']}", path) from error
        if digest != item["sha256"]:
            raise CourseStateError("artifact_hash_mismatch", f"sha256 mismatch for {item['path']}", path)


def record_lesson(root: Path, manifest: dict) -> dict:
    """Validate lesson files and atomically advance state.json, under one writer.

    validate_course checks root-level state only. Call this boundary at every
    lesson transition or replay it unchanged to verify existing artifact bytes.
    This operation does not mark progress.completed_lessons or alter mastery.
    """
    root = Path(root).resolve()
    if not validate_course(root)["valid"]:
        raise CourseStateError("invalid_course_state", "course state is invalid", root)
    course = json.loads(_owned_path(root, root / "course.json").read_text(encoding="utf-8"))
    candidate = _lesson_manifest_shape(root, manifest, course["course_id"])
    directory = candidate["lesson_directory"]
    lesson_dir = _lesson_relative_path(root, directory)
    if not lesson_dir.is_dir():
        raise CourseStateError("missing_artifact", "create the lesson directory before recording", lesson_dir)
    state_path = lesson_dir / "state.json"
    if state_path.is_symlink():
        raise CourseStateError("invalid_artifact_path", "state.json must not be a symbolic link", state_path)
    previous = None
    # Lesson-local state is the registry: no second mutable index can drift.
    lessons_dir = _owned_path(root, root / "lessons")
    for child in lessons_dir.iterdir():
        existing_path = child / "state.json"
        if not (existing_path.exists() or existing_path.is_symlink()):
            continue
        _lesson_relative_path(root, child.relative_to(root).as_posix())
        errors: list[dict] = []
        existing = _read_json_document(root, existing_path, errors)
        if errors:
            raise CourseStateError("invalid_lesson_state", "cannot read existing lesson state", existing_path)
        existing = _lesson_manifest_shape(root, existing, course["course_id"])
        if existing["lesson_directory"] != child.relative_to(root).as_posix():
            raise CourseStateError("invalid_lesson_state", "stored lesson directory differs from its location", existing_path)
        if existing["lesson_id"] == candidate["lesson_id"]:
            if existing["lesson_directory"] != directory:
                raise CourseStateError("duplicate_lesson_id", "duplicate lesson_id in another directory")
            previous = existing
        elif child == lesson_dir:
            raise CourseStateError("duplicate_lesson_directory", "lesson directory already belongs to another lesson_id")
    status = candidate["status"]
    if previous is None:
        legal = status == "draft"
    else:
        legal = candidate == previous or LESSON_STATUSES.index(status) == LESSON_STATUSES.index(previous["status"]) + 1
    if not legal:
        raise CourseStateError("invalid_lesson_transition", "allow only draft -> ready -> delivered -> assessed or unchanged replay")
    if status in {"delivered", "assessed"}:
        if _timestamp(candidate.get("delivered_at")) is None:
            raise CourseStateError("invalid_timestamp", "delivered_at requires an explicit timezone offset")
        if previous and previous["status"] in {"delivered", "assessed"} and candidate["delivered_at"] != previous.get("delivered_at"):
            raise CourseStateError("invalid_lesson_transition", "delivered_at is immutable once delivered")
    elif "delivered_at" in candidate:
        raise CourseStateError("invalid_field", "delivered_at is valid only after delivery")
    if status == "assessed":
        ids = candidate.get("attempt_ids")
        if (not isinstance(ids, list) or not ids or not all(isinstance(item, str) and item for item in ids)
                or len(ids) != len(set(ids))):
            raise CourseStateError("invalid_field", "assessed lessons require unique nonempty attempt_ids")
        errors = []
        attempts = _read_attempts(root, root / "attempts.jsonl", errors)
        if errors:
            raise CourseStateError("invalid_course_state", "cannot read attempts")
        recorded = {item.get("attempt_id"): item for _, item in attempts if isinstance(item.get("attempt_id"), str)}
        for attempt_id in ids:
            if attempt_id not in recorded:
                raise CourseStateError("unknown_attempt_id", "assessed lesson references missing attempt")
            if recorded[attempt_id].get("lesson_id") != candidate["lesson_id"]:
                raise CourseStateError("attempt_lesson_mismatch", "attempt belongs to another lesson")
    elif "attempt_ids" in candidate:
        raise CourseStateError("invalid_field", "attempt_ids is valid only for assessed lessons")
    _check_lesson_artifacts(root, candidate)
    if candidate != previous:
        _lesson_relative_path(root, f"{directory}/state.json", directory)
        atomic_write_json(state_path, candidate)
    return candidate


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

    curriculum = json.loads(_owned_path(root, root / "curriculum.json").read_text(encoding="utf-8"))
    progress = json.loads(_owned_path(root, root / "progress.json").read_text(encoding="utf-8"))
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
    attempts = _read_attempts(root, root / "attempts.jsonl", attempt_errors)
    if attempt_errors:
        raise CourseStateError("invalid_course_state", "cannot inspect attempts", root / "attempts.jsonl")
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
            if not result["valid"]:
                raise CourseStateError(
                    "invalid_course_state",
                    f"course state is invalid ({len(result['errors'])} error(s))",
                    arguments.root,
                )
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
