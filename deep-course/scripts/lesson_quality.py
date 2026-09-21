"""Deterministic, content-first lesson quality checks."""
from collections import Counter
from datetime import datetime
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import math
import re
from typing import Mapping
import unicodedata


DEPTH_LIMITS = {
    "light": {"minutes": (12, 20), "floor": 600, "target": (900, 1800)},
    "normal": {"minutes": (30, 45), "floor": 1800, "target": (2500, 5000)},
    "deep": {"minutes": (60, 90), "floor": 3500, "target": (5000, 9000)},
}

QUALITY_FIELDS = {
    "contract_version", "session_depth", "planned_minutes", "reading_minutes",
    "response_minutes", "below_target_justification", "objectives",
    "reading_sections", "worked_examples", "response_question_ids",
    "semantic_review",
}
_OBJECTIVE_FIELDS = {"objective_id", "text"}
_READING_SECTION_FIELDS = {
    "content_id", "role", "markdown_heading", "html_id", "objective_ids",
    "prerequisite_knowledge_ids",
}
_WORKED_EXAMPLE_FIELDS = {
    "example_id", "support", "markdown_heading", "html_id", "objective_ids",
}
_SEMANTIC_REVIEW_FIELDS = {"passed", "reviewed_at", "revision_summary"}
_READING_ROLES = {"orientation", "prerequisite_bridge", "concept", "synthesis", "consolidation"}
_EXAMPLE_SUPPORT = {"full", "faded", "independent"}
_RESPONSE_COUNT_LIMITS = {"light": (2, 3), "normal": (3, 5), "deep": (5, 8)}
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
_MAX_FINITE_FLOAT_INTEGER = int(float.fromhex("0x1.fffffffffffffp+1023"))


class QualityEvidenceError(ValueError):
    """Schema or semantic error raised by the public evidence normalizer."""

    def __init__(self, code: str, message: str, field: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.field = field


def _quality_failure(message: str, field: str | None = None, *, code: str = "invalid_quality_evidence") -> None:
    raise QualityEvidenceError(code, message, field)


def _exact_object(value: object, fields: set[str], field: str) -> dict:
    if not isinstance(value, dict) or set(value) != fields:
        _quality_failure(f"{field} must be an object with exactly the documented fields.", field)
    return value


def _finite_number(value: object, field: str) -> int | float:
    invalid = (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or (isinstance(value, float) and not math.isfinite(value))
        or (isinstance(value, int) and abs(value) > _MAX_FINITE_FLOAT_INTEGER)
    )
    if invalid:
        _quality_failure(f"{field} must be a finite number and not a boolean.", field)
    return value


def _nonempty_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _quality_failure(f"{field} must be a nonempty string.", field)
    return value


def _safe_id(value: object, field: str) -> str:
    identifier = _nonempty_string(value, field)
    if _SAFE_ID.fullmatch(identifier) is None:
        _quality_failure(f"{field} must be a safe identifier.", field)
    return identifier


def _id_list(value: object, field: str, *, known: set[str] | None = None) -> list[str]:
    if not isinstance(value, list):
        _quality_failure(f"{field} must be a list of safe identifiers.", field)
    result = [_safe_id(item, field) for item in value]
    if len(result) != len(set(result)):
        _quality_failure(f"{field} must not contain duplicate identifiers.", field)
    if known is not None and any(item not in known for item in result):
        _quality_failure(f"{field} contains an unknown objective reference.", field)
    return result


def _offset_timestamp(value: object, field: str) -> str:
    timestamp = _nonempty_string(value, field)
    lexical = re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|([+-])(\d{2}):(\d{2}))",
        timestamp,
    )
    if lexical is None:
        _quality_failure(f"{field} must be ISO 8601 with a T separator and explicit offset.", field)
    offset_hour = lexical.group(2)
    offset_minute = lexical.group(3)
    if offset_hour is not None and (int(offset_hour) > 23 or int(offset_minute) > 59):
        _quality_failure(f"{field} has an invalid timezone offset.", field)
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        _quality_failure(f"{field} must be an offset-aware ISO 8601 timestamp.", field)
    if parsed.utcoffset() is None:
        _quality_failure(f"{field} must include an explicit timezone offset.", field)
    return timestamp


def normalize_quality_evidence(evidence: object, learning_objectives: list[str]) -> dict:
    """Validate and detach one immutable lesson-quality evidence value."""
    evidence = _exact_object(evidence, QUALITY_FIELDS, "quality_evidence")
    if type(evidence["contract_version"]) is not int or evidence["contract_version"] != 1:
        _quality_failure("contract_version must be integer 1.", "contract_version")
    depth = evidence["session_depth"]
    if not isinstance(depth, str) or depth not in DEPTH_LIMITS:
        _quality_failure("session_depth must be light, normal, or deep.", "session_depth")
    planned_minutes = _finite_number(evidence["planned_minutes"], "planned_minutes")
    reading_minutes = _finite_number(evidence["reading_minutes"], "reading_minutes")
    response_minutes = _finite_number(evidence["response_minutes"], "response_minutes")
    justification = evidence["below_target_justification"]
    if not isinstance(justification, str):
        _quality_failure("below_target_justification must be a string.", "below_target_justification")

    objectives_value = evidence["objectives"]
    if not isinstance(objectives_value, list):
        _quality_failure("objectives must be a list.", "objectives")
    objectives: list[dict] = []
    objective_ids: set[str] = set()
    for index, item in enumerate(objectives_value):
        item = _exact_object(item, _OBJECTIVE_FIELDS, f"objectives[{index}]")
        objective_id = _safe_id(item["objective_id"], f"objectives[{index}].objective_id")
        if objective_id in objective_ids:
            _quality_failure("objective_id values must be unique.", "objectives")
        objective_ids.add(objective_id)
        objectives.append({
            "objective_id": objective_id,
            "text": _nonempty_string(item["text"], f"objectives[{index}].text"),
        })
    if (
        not isinstance(learning_objectives, list)
        or not all(isinstance(item, str) and item.strip() for item in learning_objectives)
        or [item["text"] for item in objectives] != list(learning_objectives)
    ):
        _quality_failure(
            "Evidence objectives must match learning_objectives in order.",
            "objectives",
            code="objective_uncovered",
        )

    sections_value = evidence["reading_sections"]
    if not isinstance(sections_value, list):
        _quality_failure("reading_sections must be a list.", "reading_sections")
    sections: list[dict] = []
    content_ids: set[str] = set()
    declared_html_ids: set[str] = set()
    for index, item in enumerate(sections_value):
        item = _exact_object(item, _READING_SECTION_FIELDS, f"reading_sections[{index}]")
        content_id = _safe_id(item["content_id"], f"reading_sections[{index}].content_id")
        if content_id in content_ids:
            _quality_failure("content_id values must be unique.", "reading_sections")
        content_ids.add(content_id)
        role = item["role"]
        if not isinstance(role, str) or role not in _READING_ROLES:
            _quality_failure("reading section role is not supported.", f"reading_sections[{index}].role")
        html_id = _safe_id(item["html_id"], f"reading_sections[{index}].html_id")
        if html_id in declared_html_ids:
            _quality_failure("html_id values must be unique.", "reading_sections")
        declared_html_ids.add(html_id)
        sections.append({
            "content_id": content_id,
            "role": role,
            "markdown_heading": _nonempty_string(item["markdown_heading"], f"reading_sections[{index}].markdown_heading"),
            "html_id": html_id,
            "objective_ids": _id_list(item["objective_ids"], f"reading_sections[{index}].objective_ids", known=objective_ids),
            "prerequisite_knowledge_ids": _id_list(item["prerequisite_knowledge_ids"], f"reading_sections[{index}].prerequisite_knowledge_ids"),
        })

    examples_value = evidence["worked_examples"]
    if not isinstance(examples_value, list):
        _quality_failure("worked_examples must be a list.", "worked_examples")
    examples: list[dict] = []
    example_ids: set[str] = set()
    for index, item in enumerate(examples_value):
        item = _exact_object(item, _WORKED_EXAMPLE_FIELDS, f"worked_examples[{index}]")
        example_id = _safe_id(item["example_id"], f"worked_examples[{index}].example_id")
        if example_id in example_ids:
            _quality_failure("example_id values must be unique.", "worked_examples")
        example_ids.add(example_id)
        support = item["support"]
        if not isinstance(support, str) or support not in _EXAMPLE_SUPPORT:
            _quality_failure("worked example support is not supported.", f"worked_examples[{index}].support")
        html_id = _safe_id(item["html_id"], f"worked_examples[{index}].html_id")
        if html_id in declared_html_ids:
            _quality_failure("html_id values must be unique.", "worked_examples")
        declared_html_ids.add(html_id)
        examples.append({
            "example_id": example_id,
            "support": support,
            "markdown_heading": _nonempty_string(item["markdown_heading"], f"worked_examples[{index}].markdown_heading"),
            "html_id": html_id,
            "objective_ids": _id_list(item["objective_ids"], f"worked_examples[{index}].objective_ids", known=objective_ids),
        })

    response_ids = _id_list(evidence["response_question_ids"], "response_question_ids")
    review = _exact_object(evidence["semantic_review"], _SEMANTIC_REVIEW_FIELDS, "semantic_review")
    if review["passed"] is not True:
        _quality_failure("semantic_review.passed must be true.", "semantic_review.passed")
    normalized_review = {
        "passed": True,
        "reviewed_at": _offset_timestamp(review["reviewed_at"], "semantic_review.reviewed_at"),
        "revision_summary": _nonempty_string(review["revision_summary"], "semantic_review.revision_summary"),
    }
    return {
        "contract_version": 1,
        "session_depth": depth,
        "planned_minutes": planned_minutes,
        "reading_minutes": reading_minutes,
        "response_minutes": response_minutes,
        "below_target_justification": justification,
        "objectives": objectives,
        "reading_sections": sections,
        "worked_examples": examples,
        "response_question_ids": response_ids,
        "semantic_review": normalized_review,
    }


def reading_units(text: str) -> int:
    cjk = len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", text))
    latin_words = len(re.findall(r"\b[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ'’-]*\b", text))
    return cjk + 2 * latin_words


class _VisibleHTMLText(HTMLParser):
    """Collect instructional prose while excluding interface and support sections."""

    _IGNORED_TAGS = {"script", "style", "nav", "form", "label", "button", "input", "select", "option", "textarea"}
    _SECTION_TAGS = {"section", "aside"}
    _NONINSTRUCTIONAL_CONTAINER = re.compile(r"(?:^|[-_\s])(answer(?:s|[-_\s]*key)?|sources?|references?)(?:$|[-_\s])", re.IGNORECASE)
    _NONINSTRUCTIONAL_HEADING = re.compile(r"^\s*(?:answer(?:s|\s+key)?|sources?|references?)\b", re.IGNORECASE)

    def __init__(self) -> None:
        super().__init__()
        self._ignored_depth = 0
        self._sections: list[dict[str, object]] = []
        self._heading_sections: list[dict[str, object]] = []
        self.parts: list[str] = []

    @classmethod
    def _is_named_noninstructional_container(cls, attrs: list[tuple[str, str | None]]) -> bool:
        return any(
            name.lower() in {"class", "id"}
            and value is not None
            and cls._NONINSTRUCTIONAL_CONTAINER.search(value) is not None
            for name, value in attrs
        )

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in self._IGNORED_TAGS:
            self._ignored_depth += 1
            return
        if self._ignored_depth:
            return
        is_named_noninstructional = self._is_named_noninstructional_container(attrs)
        if tag in self._SECTION_TAGS or is_named_noninstructional:
            self._sections.append({
                "tag": tag,
                "parts": [],
                "headings": [],
                "is_named_noninstructional": is_named_noninstructional,
            })
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"} and self._sections:
            self._heading_sections.append(self._sections[-1])

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        return None

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self._IGNORED_TAGS and self._ignored_depth:
            self._ignored_depth -= 1
            return
        if self._ignored_depth:
            return
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"} and self._heading_sections:
            self._heading_sections.pop()
        if self._sections and self._sections[-1]["tag"] == tag:
            section = self._sections.pop()
            headings = section["headings"]
            is_named_noninstructional = bool(section["is_named_noninstructional"])
            if not is_named_noninstructional and not any(self._NONINSTRUCTIONAL_HEADING.search(heading) for heading in headings):
                if self._sections:
                    self._sections[-1]["parts"].extend(section["parts"])
                else:
                    self.parts.extend(section["parts"])

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        if self._sections:
            self._sections[-1]["parts"].append(data)
        else:
            self.parts.append(data)
        if self._heading_sections:
            self._heading_sections[-1]["headings"].append(data)


class _LessonHTMLIndex(HTMLParser):
    """Index stable content IDs and the embedded response-question contract."""

    def __init__(self) -> None:
        super().__init__()
        self.id_counts: Counter[str] = Counter()
        self.id_positions: dict[str, list[int]] = {}
        self.lesson_data_parts: list[str] = []
        self.required_control_ids: list[str | None] = []
        self.required_control_positions: list[tuple[str | None, int]] = []
        self.question_groups: list[str | None] = []
        self.question_group_positions: list[tuple[str | None, int]] = []
        self._lesson_data_depth = 0
        self._position = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._position += 1
        attributes = {name.lower(): value for name, value in attrs}
        html_id = attributes.get("id")
        if html_id is not None:
            self.id_counts[html_id] += 1
            self.id_positions.setdefault(html_id, []).append(self._position)
        if tag.lower() == "script" and html_id == "lesson-data":
            self._lesson_data_depth += 1
        if "data-questions" in attributes:
            group = attributes.get("data-questions")
            self.question_groups.append(group)
            self.question_group_positions.append((group, self._position))
        if tag.lower() in {"input", "select", "textarea"} and "required" in attributes:
            question_id = (
                attributes.get("data-question-id")
                or attributes.get("data-response-id")
                or attributes.get("name")
                or html_id
            )
            self.required_control_ids.append(question_id)
            self.required_control_positions.append((question_id, self._position))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag.lower() == "script" and self._lesson_data_depth:
            self._lesson_data_depth -= 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._lesson_data_depth:
            self._lesson_data_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._lesson_data_depth:
            self.lesson_data_parts.append(data)


def _normalized_label(value: str) -> str:
    return " ".join(value.split())


def _markdown_headings(text: str) -> list[dict[str, object]]:
    text = _strip_markdown_html_comments(_strip_fenced_code_blocks(text))
    matches = list(re.finditer(r"(?m)^ {0,3}(#{1,6})[ \t]+(.+?)[ \t]*$", text))
    headings: list[dict[str, object]] = []
    for index, match in enumerate(matches):
        level = len(match.group(1))
        heading = re.sub(r"[ \t]+#+[ \t]*$", "", match.group(2)).strip()
        end = len(text)
        for following in matches[index + 1:]:
            if len(following.group(1)) <= level:
                end = following.start()
                break
        headings.append({
            "heading": _normalized_label(heading),
            "body": text[match.end():end],
            "position": match.start(),
        })
    return headings


def _instructional_digest(text: str) -> str:
    text = _strip_markdown_noninstructional(text)
    normalized = unicodedata.normalize("NFKC", text).casefold()
    normalized = "".join(
        " " if unicodedata.category(character)[0] in {"P", "S"} else character
        for character in normalized
    )
    normalized = " ".join(normalized.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _append_error_once(errors: list[dict], code: str, message: str, **details: str) -> None:
    if not any(item["code"] == code for item in errors):
        errors.append(_error(code, message, **details))


def _ordered_progression(
    evidence: dict,
    response_questions: list[dict],
    artifact_positions: dict[str, dict[tuple[str, str], int]],
    source: str,
) -> bool:
    positions = artifact_positions[source]
    sections = evidence["reading_sections"]
    examples = evidence["worked_examples"]

    def reading(role: str) -> list[int] | None:
        keys = [("reading", item["content_id"]) for item in sections if item["role"] == role]
        return [positions[key] for key in keys] if all(key in positions for key in keys) else None

    def support(level: str) -> list[int] | None:
        keys = [("example", item["example_id"]) for item in examples if item["support"] == level]
        return [positions[key] for key in keys] if all(key in positions for key in keys) else None

    phases: list[list[int]] = []
    for role in ("orientation", "prerequisite_bridge"):
        values = reading(role)
        if values is None:
            return True
        phases.append(values)
    concept_positions = reading("concept")
    if concept_positions is None:
        return True
    phases.extend([[position] for position in concept_positions])
    synthesis = reading("synthesis")
    full = support("full")
    faded = support("faded")
    independent = support("independent")
    consolidation = reading("consolidation")
    if any(values is None for values in (synthesis, full, faded, independent, consolidation)):
        return True
    phases.extend([synthesis, full, faded])
    if source == "html":
        independent = independent + [
            item["html_position"]
            for item in response_questions
            if item["support"] == "independent" and item["objective_ids"] and item["html_position"] is not None
        ]
    phases.extend([independent, consolidation])
    populated = [values for values in phases if values]
    return all(max(before) < min(after) for before, after in zip(populated, populated[1:]))


def _progression_errors(
    evidence: dict,
    response_questions: list[dict] | None = None,
    artifact_positions: dict[str, dict[tuple[str, str], int]] | None = None,
) -> list[dict]:
    errors: list[dict] = []
    response_questions = response_questions or []
    sections = evidence["reading_sections"]
    examples = evidence["worked_examples"]
    objective_ids = {item["objective_id"] for item in evidence["objectives"]}
    if evidence["session_depth"] == "normal":
        role_counts = Counter(item["role"] for item in sections)
        if any(role_counts[role] == 0 for role in _READING_ROLES) or not 2 <= role_counts["concept"] <= 3:
            errors.append(_error(
                "missing_progression",
                "Normal lessons require all five reading roles and two or three concept sections.",
                field="reading_sections",
            ))
        if artifact_positions is not None and not all(
            _ordered_progression(evidence, response_questions, artifact_positions, source)
            for source in ("markdown", "html")
        ):
            _append_error_once(
                errors,
                "missing_progression",
                "Declared lesson content must follow the dependency progression in Markdown and HTML.",
                field="reading_sections",
            )
        support = {item["support"] for item in examples}
        independent_responses = [
            item for item in response_questions
            if item["support"] == "independent" and item["objective_ids"]
        ]
        has_independent = "independent" in support or bool(independent_responses)
        if not {"full", "faded"}.issubset(support) or not has_independent:
            errors.append(_error(
                "missing_worked_example",
                "Normal lessons require full and faded examples plus an independent task.",
                field="worked_examples",
            ))
    concept_coverage = {
        objective_id
        for item in sections if item["role"] == "concept"
        for objective_id in item["objective_ids"]
    }
    practice_coverage = {
        objective_id
        for item in examples
        for objective_id in item["objective_ids"]
    }
    practice_coverage.update(
        objective_id
        for item in response_questions if item["support"] == "independent"
        for objective_id in item["objective_ids"]
    )
    if not objective_ids or not objective_ids.issubset(concept_coverage) or not objective_ids.issubset(practice_coverage):
        errors.append(_error(
            "objective_uncovered",
            "Every learning objective needs concept and worked or independent coverage.",
            field="objectives",
        ))
    return errors


def _artifact_correspondence_errors(
    markdown: str,
    html: str,
    evidence: dict,
) -> tuple[list[dict], list[dict], dict[str, dict[tuple[str, str], int]]]:
    errors: list[dict] = []
    response_questions: list[dict] = []
    artifact_positions: dict[str, dict[tuple[str, str], int]] = {"markdown": {}, "html": {}}
    headings = _markdown_headings(markdown)
    heading_counts = Counter(item["heading"] for item in headings)
    indexed_html = _LessonHTMLIndex()
    try:
        indexed_html.feed(html)
        indexed_html.close()
    except (ValueError, OSError):
        return [_error("unreadable_artifact", "Required lesson HTML could not be parsed.")], response_questions, artifact_positions

    declared = evidence["reading_sections"] + evidence["worked_examples"]
    for item in declared:
        key = ("reading", item["content_id"]) if "content_id" in item else ("example", item["example_id"])
        heading = _normalized_label(item["markdown_heading"])
        if heading_counts[heading] != 1:
            _append_error_once(
                errors,
                "artifact_correspondence",
                "Every declared Markdown heading must exist exactly once.",
                field="markdown_heading",
            )
        else:
            artifact_positions["markdown"][key] = int(next(
                heading_item["position"] for heading_item in headings if heading_item["heading"] == heading
            ))
        if indexed_html.id_counts[item["html_id"]] != 1:
            _append_error_once(
                errors,
                "artifact_correspondence",
                "Every declared HTML ID must exist exactly once.",
                field="html_id",
            )
        else:
            artifact_positions["html"][key] = indexed_html.id_positions[item["html_id"]][0]

    digests: set[str] = set()
    for section in evidence["reading_sections"]:
        matching = [item for item in headings if item["heading"] == _normalized_label(section["markdown_heading"])]
        if len(matching) != 1:
            continue
        digest = _instructional_digest(str(matching[0]["body"]))
        if digest in digests:
            _append_error_once(
                errors,
                "duplicate_instructional_content",
                "Distinct content IDs must contain distinct normalized instructional blocks.",
                field="reading_sections",
            )
        digests.add(digest)

    response_ids = set(evidence["response_question_ids"])
    objective_ids = {item["objective_id"] for item in evidence["objectives"]}
    question_ids: set[str] = set()
    identified_controls = [item for item in indexed_html.required_control_ids if item is not None]
    invalid_controls = (
        len(identified_controls) != len(indexed_html.required_control_ids)
        or any(_SAFE_ID.fullmatch(item) is None for item in identified_controls)
        or len(identified_controls) != len(set(identified_controls))
    )
    identified_groups = [item for item in indexed_html.question_groups if item is not None]
    invalid_groups = (
        len(identified_groups) != len(indexed_html.question_groups)
        or any(_SAFE_ID.fullmatch(item) is None for item in identified_groups)
        or len(identified_groups) != len(set(identified_groups))
    )
    if invalid_controls or invalid_groups:
        _append_error_once(
            errors,
            "artifact_correspondence",
            "Required response controls and groups must have safe, unique identities.",
            field="response_question_ids",
        )
    required_ids = set(identified_controls)
    try:
        lesson_data = json.loads("".join(indexed_html.lesson_data_parts))
        questions = lesson_data.get("questions") if isinstance(lesson_data, dict) else None
        if not isinstance(questions, list):
            raise ValueError
        for question in questions:
            if not isinstance(question, dict):
                raise ValueError
            question_id = question.get("question_id", question.get("id"))
            if not isinstance(question_id, str) or _SAFE_ID.fullmatch(question_id) is None or question_id in question_ids:
                raise ValueError
            question_ids.add(question_id)
            support = question.get("support")
            if support is not None and support not in {"guided", "independent"}:
                raise ValueError
            associated_objectives = question.get("objective_ids", [])
            if (
                not isinstance(associated_objectives, list)
                or any(not isinstance(item, str) or _SAFE_ID.fullmatch(item) is None for item in associated_objectives)
                or len(associated_objectives) != len(set(associated_objectives))
                or any(item not in objective_ids for item in associated_objectives)
            ):
                raise ValueError
            if question_id in response_ids:
                html_position = next(
                    (position for control_id, position in indexed_html.required_control_positions if control_id == question_id),
                    next(
                        (position for group, position in indexed_html.question_group_positions if group == question.get("section")),
                        None,
                    ),
                )
                if html_position is None:
                    raise ValueError
                response_questions.append({
                    "question_id": question_id,
                    "support": support,
                    "objective_ids": list(associated_objectives),
                    "html_position": html_position,
                })
            if question.get("required", True) is not False:
                required_ids.add(question_id)
    except (json.JSONDecodeError, TypeError, ValueError):
        _append_error_once(
            errors,
            "artifact_correspondence",
            "lesson-data must contain valid response questions and objective references.",
            field="response_question_ids",
        )
    else:
        if not response_ids.issubset(question_ids):
            _append_error_once(
                errors,
                "artifact_correspondence",
                "Every declared response question must exist in lesson-data.",
                field="response_question_ids",
            )
        if not required_ids.issubset(response_ids):
            _append_error_once(
                errors,
                "artifact_correspondence",
                "Required response controls must be declared in response_question_ids.",
                field="response_question_ids",
            )
    return errors, response_questions, artifact_positions

def _error(code: str, message: str, *, path: str | None = None, field: str | None = None) -> dict:
    item = {"code": code, "message": message}
    if path is not None:
        item["path"] = path
    if field is not None:
        item["field"] = field
    return item


def _strip_fenced_code_blocks(text: str) -> str:
    """Remove CommonMark fenced code, including unclosed fences through EOF."""
    retained: list[str] = []
    fence_character: str | None = None
    fence_length = 0
    for line in text.splitlines(keepends=True):
        stripped_line = line.rstrip("\r\n")
        if fence_character is None:
            opener = re.match(r"^ {0,3}(`{3,}|~{3,})[^\r\n]*$", stripped_line)
            if opener:
                marker = opener.group(1)
                fence_character = marker[0]
                fence_length = len(marker)
            else:
                retained.append(line)
        elif re.fullmatch(rf" {{0,3}}{re.escape(fence_character)}{{{fence_length},}}[ \t]*", stripped_line):
            fence_character = None
            fence_length = 0
    return "".join(retained)


def _strip_markdown_html_comments(text: str) -> str:
    """Remove rendered-invisible HTML comments, including an unclosed tail."""
    return re.sub(r"<!--.*?(?:-->|$)", "", text, flags=re.DOTALL)


def _strip_markdown_noninstructional(text: str) -> str:
    text = _strip_markdown_html_comments(_strip_fenced_code_blocks(text))
    text = re.sub(r"(?m)^(?: {4}|\t).*(?:\n(?: {4}|\t).*)*", "", text)
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*(?:answer(?:s| key)?|sources?|references?)\b.*$(?:\n(?!\s{0,3}#{1,6}\s).*)*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"(?im)^\s*(?:(?:navigation|previous|next|back|continue)(?:[\s|·•]+(?:previous|next|back|continue))*)\s*$", "", text)
    return re.sub(r"[`*_~>#]", "", text)


def _read_text(path: Path, relative_path: str) -> tuple[str | None, dict | None]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None, _error("missing_artifact", "Required lesson artifact is missing.", path=relative_path)
    except (OSError, UnicodeError):
        return None, _error("unreadable_artifact", "Required lesson artifact could not be read as UTF-8 text.", path=relative_path)
    if any((ord(character) < 32 and character not in "\t\n\r") or 127 <= ord(character) <= 159 for character in text):
        return None, _error("non_text_artifact", "Required lesson artifact must contain text, not binary data.", path=relative_path)
    return text, None


def _curriculum_knowledge_ids(root: Path) -> tuple[set[str] | None, dict | None]:
    relative_path = "curriculum.json"
    path = root / relative_path
    try:
        path.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return None, _error(
            "invalid_artifact_path",
            "curriculum.json must stay inside the course root.",
            path=relative_path,
        )
    text, read_error = _read_text(path, relative_path)
    if read_error is not None:
        return None, read_error
    try:
        curriculum = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None, _error(
            "invalid_curriculum",
            "curriculum.json must contain valid JSON with knowledge_nodes.",
            path=relative_path,
        )
    nodes = curriculum.get("knowledge_nodes") if isinstance(curriculum, dict) else None
    if not isinstance(nodes, list):
        return None, _error(
            "invalid_curriculum",
            "curriculum.json knowledge_nodes must be a list.",
            path=relative_path,
            field="knowledge_nodes",
        )
    identifiers: list[str] = []
    for index, node in enumerate(nodes):
        identifier = node.get("knowledge_id") if isinstance(node, dict) else None
        if not isinstance(identifier, str) or not identifier or _SAFE_ID.fullmatch(identifier) is None:
            return None, _error(
                "invalid_curriculum",
                "Every curriculum knowledge node needs a safe knowledge_id.",
                path=relative_path,
                field=f"knowledge_nodes[{index}].knowledge_id",
            )
        identifiers.append(identifier)
    if len(identifiers) != len(set(identifiers)):
        return None, _error(
            "invalid_curriculum",
            "Curriculum knowledge_id values must be unique.",
            path=relative_path,
            field="knowledge_nodes",
        )
    return set(identifiers), None


def _contained_lesson_directory(root: Path, manifest: Mapping[str, object]) -> tuple[Path | None, str | None, dict | None]:
    directory = manifest.get("lesson_directory")
    if not isinstance(directory, str) or not directory:
        return None, None, _error("invalid_artifact_path", "lesson_directory must be a non-empty relative path.", field="lesson_directory")
    candidate = Path(directory)
    if candidate.is_absolute():
        return None, None, _error("invalid_artifact_path", "lesson_directory must stay inside the course root.", field="lesson_directory")
    try:
        resolved_root = root.resolve()
        resolved_lesson = (resolved_root / candidate).resolve()
        resolved_lesson.relative_to(resolved_root)
    except (OSError, ValueError):
        return None, None, _error("invalid_artifact_path", "lesson_directory must stay inside the course root.", field="lesson_directory")
    return resolved_lesson, candidate.as_posix(), None


def _depth_band(planned_minutes: object) -> str | None:
    if (
        isinstance(planned_minutes, bool)
        or not isinstance(planned_minutes, (int, float))
        or (isinstance(planned_minutes, float) and not math.isfinite(planned_minutes))
        or (isinstance(planned_minutes, int) and abs(planned_minutes) > _MAX_FINITE_FLOAT_INTEGER)
    ):
        return None
    for name, limit in DEPTH_LIMITS.items():
        low, high = limit["minutes"]
        if low <= planned_minutes <= high:
            return name
    return None


def audit_lesson(root: Path, manifest: Mapping[str, object]) -> dict:
    """Measure a lesson's readable Markdown and HTML, reporting errors structurally."""
    report = {"valid": True, "errors": [], "warnings": [], "metrics": {
        "markdown_reading_units": 0,
        "html_reading_units": 0,
    }}
    if not isinstance(manifest, Mapping):
        report["errors"].append(_error("invalid_manifest", "Lesson manifest must be a mapping."))
        report["valid"] = False
        return report

    quality: dict | None = None
    if "quality_evidence" in manifest:
        try:
            quality = normalize_quality_evidence(
                manifest.get("quality_evidence"),
                manifest.get("learning_objectives"),
            )
        except QualityEvidenceError as error:
            report["errors"].append(_error(error.code, error.message, field=error.field))

    try:
        course_root = Path(root)
    except TypeError:
        report["errors"].append(_error("invalid_artifact_path", "Course root is not a valid path."))
        report["valid"] = False
        return report
    lesson_dir, directory, directory_error = _contained_lesson_directory(course_root, manifest)
    if directory_error:
        report["errors"].append(directory_error)
        report["valid"] = False
        return report

    markdown, markdown_error = _read_text(lesson_dir / "lesson.md", f"{directory}/lesson.md")
    html, html_error = _read_text(lesson_dir / "lesson.html", f"{directory}/lesson.html")
    for error in (markdown_error, html_error):
        if error:
            report["errors"].append(error)
    if markdown is not None:
        report["metrics"]["markdown_reading_units"] = reading_units(_strip_markdown_noninstructional(markdown))
    if html is not None:
        parser = _VisibleHTMLText()
        try:
            parser.feed(html)
            parser.close()
        except (ValueError, OSError):
            report["errors"].append(_error("unreadable_artifact", "Required lesson HTML could not be parsed.", path=f"{directory}/lesson.html"))
        else:
            report["metrics"]["html_reading_units"] = reading_units(_strip_markdown_noninstructional(" ".join(parser.parts)))

    if quality is not None:
        known_knowledge_ids, curriculum_error = _curriculum_knowledge_ids(course_root)
        if curriculum_error is not None:
            report["errors"].append(curriculum_error)
        else:
            prerequisite_ids = {
                identifier
                for section in quality["reading_sections"]
                for identifier in section["prerequisite_knowledge_ids"]
            }
            unknown_ids = sorted(prerequisite_ids - known_knowledge_ids)
            if unknown_ids:
                report["errors"].append(_error(
                    "invalid_quality_evidence",
                    "prerequisite_knowledge_ids reference unknown curriculum knowledge: " + ", ".join(unknown_ids),
                    path="curriculum.json",
                    field="reading_sections",
                ))

    planned_minutes = quality["planned_minutes"] if quality is not None else manifest.get("planned_minutes")
    depth_band = _depth_band(planned_minutes)
    if depth_band is None:
        report["errors"].append(_error(
            "invalid_time_evidence",
            "planned_minutes must be a finite number in a supported lesson-duration band.",
            field="planned_minutes",
        ))
    elif quality is not None and depth_band != quality["session_depth"]:
        report["errors"].append(_error(
            "invalid_time_evidence",
            "planned_minutes must fall inside the declared session_depth range.",
            field="planned_minutes",
        ))
    elif report["metrics"]["markdown_reading_units"] < DEPTH_LIMITS[depth_band]["floor"]:
        report["errors"].append(_error(
            "insufficient_reading_depth",
            f"{depth_band.title()}-depth lessons need at least {DEPTH_LIMITS[depth_band]['floor']:,} Markdown reading units.",
            path=f"{directory}/lesson.md",
            field="planned_minutes",
        ))

    if quality is not None:
        correspondence_errors: list[dict] = []
        response_questions: list[dict] = []
        artifact_positions: dict[str, dict[tuple[str, str], int]] | None = None
        if markdown is not None and html is not None:
            correspondence_errors, response_questions, artifact_positions = _artifact_correspondence_errors(markdown, html, quality)
        response_count = len(quality["response_question_ids"])
        response_share = quality["response_minutes"] / quality["planned_minutes"] if quality["planned_minutes"] else math.inf
        html_fraction = report["metrics"]["html_reading_units"] / max(report["metrics"]["markdown_reading_units"], 1)
        report["metrics"].update({
            "session_depth": quality["session_depth"],
            "planned_minutes": quality["planned_minutes"],
            "reading_minutes": quality["reading_minutes"],
            "response_minutes": quality["response_minutes"],
            "concept_count": sum(item["role"] == "concept" for item in quality["reading_sections"]),
            "response_count": response_count,
            "response_share": response_share,
            "html_fraction": html_fraction,
        })
        report["errors"].extend(_progression_errors(quality, response_questions, artifact_positions))
        if not 0 < quality["reading_minutes"] < quality["planned_minutes"]:
            _append_error_once(
                report["errors"],
                "invalid_time_evidence",
                "reading_minutes must be positive and less than planned_minutes.",
                field="reading_minutes",
            )
        minimum_responses, maximum_responses = _RESPONSE_COUNT_LIMITS[quality["session_depth"]]
        if (
            quality["response_minutes"] < 0
            or quality["response_minutes"] > quality["planned_minutes"] * 0.35
            or not minimum_responses <= response_count <= maximum_responses
        ):
            report["errors"].append(_error(
                "interaction_overweight",
                "Response time and count must stay inside the session-depth interaction limits.",
                field="response_minutes",
            ))
        target_floor = DEPTH_LIMITS[quality["session_depth"]]["target"][0]
        if report["metrics"]["markdown_reading_units"] < target_floor:
            report["warnings"].append(_error(
                "below_target_reading",
                "Instructional reading is below the target band for this session depth.",
                path=f"{directory}/lesson.md",
            ))
            if not quality["below_target_justification"].strip():
                report["errors"].append(_error(
                    "invalid_quality_evidence",
                    "below_target_justification is required below the target reading band.",
                    field="below_target_justification",
                ))
        if html_fraction < 0.90:
            report["errors"].append(_error(
                "html_content_loss",
                "HTML must preserve at least 90 percent of Markdown instructional units.",
                path=f"{directory}/lesson.html",
            ))
        for error in correspondence_errors:
            if "path" not in error:
                error["path"] = f"{directory}/lesson.html" if error.get("field") in {"html_id", "response_question_ids"} else f"{directory}/lesson.md"
            report["errors"].append(error)
    report["valid"] = not report["errors"]
    return report
