# Course state contracts

`scripts/course_state.py` is the sole deterministic owner of course initialization,
validation, and derived session inspection. Runtime code uses only the Python standard
library. All identifiers are stable strings and do not depend on display titles.

## Shared rules

- The schema version is the integer `1`. A Boolean is not a valid version. Every JSON
  document and every nonempty `attempts.jsonl` record carries `schema_version`.
- Timestamps are ISO 8601 date-times with an explicit UTC offset, for example
  `2026-09-11T09:00:00+08:00` or `2026-09-11T01:00:00Z`. Local timestamps without an
  offset fail validation.
- `course_id` in each mutable JSON document must equal `course.json.course_id`.
- Mutable JSON files are written to a temporary sibling, flushed, synchronized with
  `fsync`, and atomically installed with `os.replace`. `attempts.jsonl` is append-only
  after initialization.
- Validation is read-only. Unknown versions fail closed and are never migrated or
  rewritten automatically.
- Callers must run `validate` successfully before generating or recording a lesson.
  `next-session` enforces this boundary itself.

## Directory and file ownership

`init` refuses a file path or a nonempty directory. It creates `research/`, `lessons/`,
an empty `attempts.jsonl`, and these four versioned documents:

### `course.json`

```json
{
  "schema_version": 1,
  "course_id": "finance",
  "title": "Finance",
  "created_at": "2026-09-11T09:00:00+08:00",
  "status": "onboarding",
  "session_depth": "normal"
}
```

This file owns identity, lifecycle status, and the requested session depth. Course
status values are `onboarding`, `planning`, `awaiting_approval`, `active`, `paused`, and
`completed`. Session-depth values are `light`, `normal`, and `deep`.

### `learner-profile.json`

This file owns learner-entered `goals`, `prior_knowledge`, and `constraints`; each is
initialized as a list. It also carries `schema_version` and `course_id`.

### `curriculum.json`

This file owns `status`, `learning_outcomes`, `modules`, `knowledge_nodes`, and the
stable `backbone`. Curriculum status values are `draft`, `proposed`, and `approved`.

Each knowledge node has a unique `knowledge_id`, a display `title`, and a
`prerequisite_ids` list. Every prerequisite must identify another node and the graph
must be acyclic. A backbone entry has `lesson_id`, `title`, and `knowledge_ids`; it may
also declare `prerequisite_knowledge_ids`. The initial document contains empty lists.

### `progress.json`

This file owns `knowledge`, an object keyed by curriculum knowledge ID, and
`completed_lessons`, a list of stable lesson IDs. A knowledge entry may carry
`last_practiced_at` and `next_review_at`. Knowledge status values are `unseen`,
`learning`, `relearning`, `reviewing`, and `mastered`. The initial `knowledge` object
and `completed_lessons` list are empty.

### `attempts.jsonl`

Each line is one UTF-8 JSON object. Task 2 recognizes the version, optional `course_id`,
the timestamp fields `submitted_at`, `occurred_at`, and `exported_at`, top-level
`misconception_tags`, and response-level `misconception_tags`. Later state operations
extend this append-only record without changing these validation rules.

## Python interfaces

- `init_course(root, slug, title, created_at)` returns the new `course.json` object.
- `validate_course(root)` returns
  `{"valid": bool, "errors": [issue...], "warnings": [issue...]}`. Issues contain
  `code`, `message`, `path`, and, when applicable, `field`.
- `next_session(root, now)` returns `course_id`, `due_review_knowledge_ids`,
  `next_backbone_lesson`, and `recent_misconception_tags`.

Due reviews have `next_review_at <= now` and are ordered by due time, then knowledge
ID. The next backbone lesson is the first incomplete entry whose explicit prerequisites
and the prerequisites of its knowledge nodes all have `mastered` progress. Recent
misconception tags are de-duplicated from newest to oldest across only the last five
attempts. `next_backbone_lesson` is `null` when no entry is unlocked.

Domain failures raise `CourseStateError(code, message, path=None)`. Stable Task 2 codes
include `course_directory_not_empty`, `invalid_course_state`, `invalid_timestamp`,
`missing_file`, `malformed_json`, `malformed_jsonl`, `invalid_document`,
`invalid_field`, `unsupported_schema_version`, `course_id_mismatch`,
`duplicate_knowledge_id`, `missing_prerequisite`, `prerequisite_cycle`, and
`unknown_knowledge_id`.

## Command-line interface

```text
course_state.py init --root PATH --slug SLUG --title TITLE --created-at ISO8601
course_state.py validate --root PATH
course_state.py next-session --root PATH --now ISO8601
```

Each successful command writes exactly one JSON object to stdout. `validate` returning
`"valid": false` is a successful inspection and still exits zero. A domain error writes
exactly one object of this shape to stderr and exits `2`:

```json
{"ok": false, "error": {"code": "...", "message": "...", "path": null}}
```
