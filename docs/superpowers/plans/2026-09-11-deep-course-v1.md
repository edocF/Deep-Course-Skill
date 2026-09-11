# Deep Course v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an explicitly invoked, domain-neutral `deep-course` Skill that creates and runs adaptive multimodal courses while a dependency-free Python CLI protects course state.

**Architecture:** `SKILL.md` is a thin director that routes course operations to focused teaching references and Codex-native tools. `scripts/course_state.py` owns deterministic initialization, validation, atomic persistence, attempts, mastery scheduling, and lesson lifecycle transitions. A self-contained HTML asset supplies the standard learning shell and exports non-authoritative answer records for Codex to assess.

**Tech Stack:** Codex Skill Markdown/YAML, Python 3 standard library, HTML5, CSS, browser JavaScript, `unittest`, Git.

**Spec:** `docs/superpowers/specs/2026-09-11-deep-course-design.md`

## Global Constraints

- The Skill is explicitly invoked with `$deep-course`; implicit model invocation is disabled.
- Version 1 is single-learner, local-file, and domain-neutral.
- Runtime state code uses only the Python standard library.
- Course data defaults to `courses/<course-slug>/` and never lives inside the installed Skill.
- Every lesson has six core files: `lesson.html`, `lesson.md`, `exercises.md`, `answers.md`, `sources.md`, and `state.json`.
- `lesson.html` is the primary experience and works without a build step.
- Browser JavaScript exports answer JSON but never mutates authoritative course state.
- Mutable JSON writes are atomic; attempts are append-only JSON Lines.
- Unknown schema versions and paths escaping the selected course root fail closed.
- The course backbone changes only with learner approval; lesson pacing and inserted reinforcement or challenge lessons remain adaptive.

## File Map

```text
deep-course/
|-- SKILL.md                              Operation router and shared invariants
|-- agents/openai.yaml                    Explicit-only UI invocation metadata
|-- references/onboarding-and-curriculum.md  Intake, diagnostic, research, approval
|-- references/lesson-design.md           Session budget and artifact decisions
|-- references/research-and-sources.md    Source hierarchy and citation records
|-- references/assessment-and-adaptation.md  Rubrics, evidence, mastery, review
|-- references/state-contracts.md         CLI commands and JSON contracts
|-- scripts/course_state.py               Deterministic state API and CLI
|-- assets/lesson-template/lesson.html    Accessible static lesson shell
|-- tests/test_course_state.py            State unit and CLI integration tests
|-- tests/test_lesson_template.py         Browser-shell structural behavior tests
|-- tests/test_skill_package.py           Metadata, routing, and reference integrity
|-- tests/scenarios/*.md                   Baseline and forward behavior scenarios
`-- tests/evaluation-log.md                Observed no-skill and with-skill outcomes
```

---

### Task 1: Capture Baseline Skill Failures and Create Package Contract

**Files:**
- Create: `deep-course/tests/scenarios/create-long-course.md`
- Create: `deep-course/tests/scenarios/quantitative-lesson.md`
- Create: `deep-course/tests/scenarios/adaptive-remediation.md`
- Create: `deep-course/tests/evaluation-log.md`
- Create: `deep-course/tests/test_skill_package.py`

**Interfaces:**
- Consumes: the approved design specification.
- Produces: executable package checks and written baseline observations used to shape `SKILL.md`.

- [ ] **Step 1: Write three behavior scenarios before the Skill exists**

`create-long-course.md` asks a fresh agent to create a twelve-week course under time pressure and records whether it pre-generates lessons, skips learner approval, or invents unsupported domain facts. `quantitative-lesson.md` requests a bond-yield lesson and records whether the agent creates an inspectable numeric model and learner activity rather than decorative prose. `adaptive-remediation.md` supplies weak present-value answers and records whether the agent diagnoses the misconception, schedules retrieval, and preserves the approved backbone.

Each scenario uses this structure:

```markdown
# Scenario: Create a long course

## Setup
Run in an empty temporary workspace without the deep-course Skill.

## Learner request
Create a twelve-week course that teaches me the named subject. I am in a hurry, so generate everything now.

## Observable decisions
- Whether onboarding and a diagnostic occur before curriculum generation.
- Whether the agent generates the skeleton or all lessons.
- Whether research claims are traceable.
- Whether user state is separated from reusable instructions.
```

- [ ] **Step 2: Run the scenarios without the new Skill and record exact outcomes**

Use fresh-context evaluations. Record the date, evaluator, scenario path, artifacts produced, observed decision for every bullet, and short verbatim rationalizations in `tests/evaluation-log.md`. The baseline is red when at least one scenario violates its observable decisions.

- [ ] **Step 3: Write the failing package test**

```python
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SkillPackageTests(unittest.TestCase):
    def test_required_package_files_exist(self):
        required = {
            "SKILL.md",
            "agents/openai.yaml",
            "references/onboarding-and-curriculum.md",
            "references/lesson-design.md",
            "references/research-and-sources.md",
            "references/assessment-and-adaptation.md",
            "references/state-contracts.md",
            "scripts/course_state.py",
            "assets/lesson-template/lesson.html",
        }
        missing = sorted(path for path in required if not (ROOT / path).is_file())
        self.assertEqual([], missing)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 4: Run the package test and verify it fails**

Run: `python -m unittest deep-course/tests/test_skill_package.py -v`

Expected: FAIL listing the package files that do not yet exist.

- [ ] **Step 5: Commit the red baseline**

```bash
git add deep-course/tests
git commit -m "test: capture deep-course baseline behavior"
```

---

### Task 2: Initialize, Validate, and Inspect Course State

**Files:**
- Create: `deep-course/scripts/course_state.py`
- Create: `deep-course/tests/test_course_state.py`
- Create: `deep-course/references/state-contracts.md`

**Interfaces:**
- Produces: `init_course(root: Path, slug: str, title: str, created_at: str) -> dict`, `validate_course(root: Path) -> dict`, `next_session(root: Path, now: str) -> dict`, and CLI JSON responses.
- Error type: `CourseStateError(code: str, message: str, path: Path | None = None)`.
- JSON schema version: integer `1`.

- [ ] **Step 1: Add failing initialization tests**

```python
class InitializationTests(unittest.TestCase):
    def test_init_creates_minimal_valid_course(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "courses" / "finance"
            result = course_state.init_course(
                root, "finance", "Finance", "2026-09-11T09:00:00+08:00"
            )
            self.assertEqual("finance", result["course_id"])
            self.assertTrue((root / "course.json").is_file())
            self.assertTrue((root / "attempts.jsonl").is_file())
            self.assertEqual([], course_state.validate_course(root)["errors"])

    def test_init_refuses_existing_nonempty_directory(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "existing"
            root.mkdir()
            (root / "keep.txt").write_text("user data", encoding="utf-8")
            with self.assertRaisesRegex(course_state.CourseStateError, "not empty"):
                course_state.init_course(root, "x", "X", "2026-09-11T09:00:00+08:00")
```

- [ ] **Step 2: Run the focused tests and verify import or symbol failure**

Run: `python -m unittest deep-course.tests.test_course_state.InitializationTests -v`

Expected: FAIL because `course_state.py` or its public functions do not exist.

- [ ] **Step 3: Implement minimal initialization and atomic JSON writes**

Implement `atomic_write_json()` with `tempfile.NamedTemporaryFile` in the destination directory, `flush()`, `os.fsync()`, and `os.replace()`. Initialize versioned `course.json`, `learner-profile.json`, `curriculum.json`, `progress.json`, and empty `attempts.jsonl`, plus `research/` and `lessons/`.

The initial `course.json` shape is:

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

- [ ] **Step 4: Add failing validation tests**

Cover unknown schema versions, invalid ISO timestamps without offsets, mismatched course IDs, duplicate knowledge IDs, missing prerequisite IDs, cycles in the prerequisite graph, progress entries for unknown knowledge IDs, malformed JSON Lines, and a valid empty course.

```python
def test_unknown_schema_version_fails_closed(self):
    root = self.make_course()
    data = json.loads((root / "course.json").read_text(encoding="utf-8"))
    data["schema_version"] = 99
    (root / "course.json").write_text(json.dumps(data), encoding="utf-8")
    report = course_state.validate_course(root)
    self.assertIn("unsupported_schema_version", {e["code"] for e in report["errors"]})
```

- [ ] **Step 5: Implement complete validation and next-session inspection**

`validate_course()` returns `{"valid": bool, "errors": list[dict], "warnings": list[dict]}` without mutating files. `next_session()` refuses invalid state, returns due review knowledge IDs ordered by due time, identifies the next unlocked backbone lesson, and includes recent misconception tags from the last five attempts.

- [ ] **Step 6: Add and test CLI adapters**

Support:

```text
course_state.py init --root PATH --slug SLUG --title TITLE --created-at ISO8601
course_state.py validate --root PATH
course_state.py next-session --root PATH --now ISO8601
```

Every success prints one JSON object to stdout. Every domain error prints `{"ok": false, "error": {"code": ..., "message": ..., "path": ...}}` to stderr and exits `2`.

- [ ] **Step 7: Document exact state contracts and run all state tests**

`state-contracts.md` defines owned fields, valid enums, CLI inputs and outputs, timestamp requirements, and the rule that callers must run `validate` before lesson generation.

Run: `python -m unittest deep-course/tests/test_course_state.py -v`

Expected: PASS.

- [ ] **Step 8: Commit initialization and validation**

```bash
git add deep-course/scripts/course_state.py deep-course/tests/test_course_state.py deep-course/references/state-contracts.md
git commit -m "feat: add validated course state foundation"
```

---

### Task 3: Add Attempts, Mastery Evidence, and Spaced Review

**Files:**
- Modify: `deep-course/scripts/course_state.py`
- Modify: `deep-course/tests/test_course_state.py`
- Create: `deep-course/references/assessment-and-adaptation.md`

**Interfaces:**
- Produces: `append_attempt(root: Path, attempt: dict) -> dict` and `apply_mastery_updates(root: Path, attempt_id: str, updates: list[dict], occurred_at: str) -> dict`.
- Quality enum: `incorrect`, `partial`, `correct`, `effortless`.
- Mastery values are decimal numbers from `0.0` through `1.0`; confidence values use the same range.

- [ ] **Step 1: Add failing append-only attempt tests**

Test a valid attempt, duplicate `attempt_id`, unknown knowledge ID, missing timezone offset, invalid quality enum, and injected path fields. Verify that a rejected record leaves `attempts.jsonl` byte-for-byte unchanged.

```python
def test_attempt_is_appended_once(self):
    root = self.make_course_with_node("pv")
    attempt = {
        "schema_version": 1,
        "attempt_id": "attempt-001",
        "lesson_id": "lesson-001",
        "submitted_at": "2026-09-11T10:00:00+08:00",
        "responses": [{"question_id": "q1", "knowledge_ids": ["pv"], "answer": "900"}],
    }
    course_state.append_attempt(root, attempt)
    with self.assertRaisesRegex(course_state.CourseStateError, "duplicate"):
        course_state.append_attempt(root, attempt)
    self.assertEqual(1, len((root / "attempts.jsonl").read_text(encoding="utf-8").splitlines()))
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `python -m unittest deep-course.tests.test_course_state.AttemptTests -v`

Expected: FAIL because `append_attempt` is absent.

- [ ] **Step 3: Implement validated append-only attempts**

Reject caller-supplied filesystem paths. Serialize one compact UTF-8 JSON object followed by `\n`, flush, and sync before returning. Return the immutable attempt ID and its zero-based line index.

- [ ] **Step 4: Add failing mastery and review-schedule tests**

Use the v1 interval table:

| Quality | Mastery delta | Confidence delta | Next interval |
|---|---:|---:|---:|
| incorrect | -0.20 | +0.05 | 1 day |
| partial | +0.05 | +0.05 | 2 days |
| correct | +0.15 | +0.10 | `max(3, previous_interval * 2)` days |
| effortless | +0.20 | +0.10 | `max(5, previous_interval * 3)` days |

Clamp mastery and confidence to `[0, 1]`. Set `status` to `relearning` after incorrect evidence, `learning` below `0.75`, `reviewing` at `0.75–0.89`, and `mastered` at `0.90` or above only when at least three successful pieces of evidence exist across at least two distinct attempts.

- [ ] **Step 5: Implement mastery updates as one atomic transaction**

Require the referenced attempt to exist. Reject duplicate application of the same `attempt_id`. Update all knowledge nodes in memory, validate the resulting document, atomically replace `progress.json`, and return changed nodes plus their next review timestamps.

- [ ] **Step 6: Document grading boundaries**

`assessment-and-adaptation.md` states that Codex assesses semantic response quality with a lesson-specific rubric and supplies the quality enum, misconception tags, and concise feedback. The script verifies structure and applies math; it never infers semantic quality from answer text.

- [ ] **Step 7: Run state tests and commit**

Run: `python -m unittest deep-course/tests/test_course_state.py -v`

Expected: PASS.

```bash
git add deep-course/scripts/course_state.py deep-course/tests/test_course_state.py deep-course/references/assessment-and-adaptation.md
git commit -m "feat: track mastery evidence and spaced review"
```

---

### Task 4: Enforce the Lesson Artifact Lifecycle

**Files:**
- Modify: `deep-course/scripts/course_state.py`
- Modify: `deep-course/tests/test_course_state.py`
- Create: `deep-course/references/lesson-design.md`

**Interfaces:**
- Produces: `record_lesson(root: Path, manifest: dict) -> dict`.
- Lesson states: `draft`, `ready`, `delivered`, `assessed`.
- Core artifact paths must be relative descendants of `lessons/<lesson-directory>/`.

- [ ] **Step 1: Add failing lesson manifest tests**

Test missing core artifacts, absolute paths, `..` traversal, symbolic-link escape where supported, duplicate lesson IDs, artifact hashes that do not match file bytes, and a complete draft-to-ready transition.

```python
def test_ready_lesson_requires_all_core_artifacts(self):
    root, lesson_dir = self.make_lesson_files(omit="sources.md")
    with self.assertRaisesRegex(course_state.CourseStateError, "sources.md"):
        course_state.record_lesson(root, self.manifest(lesson_dir, status="ready"))
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `python -m unittest deep-course.tests.test_course_state.LessonLifecycleTests -v`

Expected: FAIL because `record_lesson` is absent.

- [ ] **Step 3: Implement path containment and artifact hashing**

Resolve the course root and each artifact, require `artifact_path.is_relative_to(course_root)` and the expected lesson directory, reject symlinks that resolve outside, calculate SHA-256, and store only normalized relative POSIX paths.

- [ ] **Step 4: Implement lesson transitions**

Allow `draft -> ready -> delivered -> assessed`. Permit idempotent recording of an unchanged manifest. Reject skipped or backward transitions. A `ready` lesson requires all six core files and a nonempty learning-objective list. A `delivered` lesson records `delivered_at`; an `assessed` lesson references at least one existing attempt.

- [ ] **Step 5: Write the lesson design reference**

Define light, normal, and deep session budgets; retrieval-first openings; concept limits based on prerequisites and cognitive load; artifact selection by learning objective; grounded cases; active problem solving; final recall; accessible HTML; and the rule that optional media must be used by an activity.

- [ ] **Step 6: Run tests and commit**

Run: `python -m unittest deep-course/tests/test_course_state.py -v`

Expected: PASS.

```bash
git add deep-course/scripts/course_state.py deep-course/tests/test_course_state.py deep-course/references/lesson-design.md
git commit -m "feat: validate lesson artifact lifecycle"
```

---

### Task 5: Build the Self-Contained HTML Lesson Shell

**Files:**
- Create: `deep-course/assets/lesson-template/lesson.html`
- Create: `deep-course/tests/test_lesson_template.py`

**Interfaces:**
- Consumes: lesson metadata and question data embedded in `<script type="application/json" id="lesson-data">`.
- Produces: a downloaded `deep-course-response-v1.json` document with `schema_version`, `course_id`, `lesson_id`, `exported_at`, and `responses`.

- [ ] **Step 1: Add failing template structure tests**

```python
class LessonTemplateTests(unittest.TestCase):
    def test_template_is_self_contained_and_accessible(self):
        text = TEMPLATE.read_text(encoding="utf-8")
        self.assertNotIn("https://", text)
        self.assertIn('id="lesson-data"', text)
        self.assertIn('type="application/json"', text)
        self.assertIn("<main", text)
        self.assertIn("aria-live=", text)
        self.assertIn("deep-course-response-v1.json", text)

    def test_browser_code_does_not_write_course_files(self):
        text = TEMPLATE.read_text(encoding="utf-8")
        self.assertNotIn("showSaveFilePicker", text)
        self.assertNotIn("FileSystemFileHandle", text)
```

- [ ] **Step 2: Run the template test and verify it fails**

Run: `python -m unittest deep-course/tests/test_lesson_template.py -v`

Expected: FAIL because the template is absent.

- [ ] **Step 3: Implement the lesson shell**

Include semantic navigation, progress indication, retrieval prompt, concept sections, visual/data slot, case slot, exercises, final recall, keyboard-visible focus, responsive print styles, reduced-motion handling, and a hidden answer explanation revealed after objective responses.

Embed CSS and JavaScript. JavaScript validates question IDs, gathers objective and open responses, provides immediate objective feedback from authored explanations, and downloads the versioned response JSON with `Blob` and an object URL.

- [ ] **Step 4: Add export-contract assertions**

Parse the embedded example data with `html.parser` and assert unique question IDs, every objective option has feedback, no authoritative mastery field is exported, and the export schema matches the fields accepted by `append_attempt()`.

- [ ] **Step 5: Run tests and visually inspect the template**

Run: `python -m unittest deep-course/tests/test_lesson_template.py -v`

Open the template in a browser, test keyboard navigation, objective feedback, answer export, narrow-screen layout, and print preview. Record the inspected browser and result in `tests/evaluation-log.md`.

- [ ] **Step 6: Commit the HTML shell**

```bash
git add deep-course/assets/lesson-template/lesson.html deep-course/tests/test_lesson_template.py deep-course/tests/evaluation-log.md
git commit -m "feat: add interactive lesson HTML shell"
```

---

### Task 6: Author the Director Skill and Focused References

**Files:**
- Create: `deep-course/SKILL.md`
- Create: `deep-course/agents/openai.yaml`
- Create: `deep-course/references/onboarding-and-curriculum.md`
- Create: `deep-course/references/research-and-sources.md`
- Modify: `deep-course/tests/test_skill_package.py`

**Interfaces:**
- Consumes: state CLI JSON, approved curriculum, learner request, relevant reference file, and available Codex-native tools.
- Produces: a validated course operation and user-facing result with direct links to generated artifacts.

- [ ] **Step 1: Extend the failing package tests**

Assert valid YAML frontmatter with name `deep-course`, a concise human-facing description, `allow_implicit_invocation: false`, existing relative reference links, no domain pack, no direct LLM API dependency, and no unfinished scaffold tokens.

- [ ] **Step 2: Run the package tests and verify failure**

Run: `python -m unittest deep-course/tests/test_skill_package.py -v`

Expected: FAIL because the director files are absent.

- [ ] **Step 3: Write minimal `SKILL.md` routing**

The entrypoint contains:

1. a purpose and explicit-invocation boundary;
2. a state-first router for create, teach, assess, progress, and revise operations;
3. reference pointers with precise conditions;
4. the rule to invoke native artifact skills only when the lesson decision calls for that artifact;
5. pre-mutation validation and post-generation lesson-manifest validation;
6. completion criteria for each operation;
7. recovery behavior for unavailable tools or invalid state.

Keep domain methods and detailed file schemas in references rather than duplicating them in the entrypoint.

- [ ] **Step 4: Write onboarding and curriculum guidance**

Define the interview, adaptive diagnostic stopping condition, conservative skipped-diagnostic state, broad research phase, prerequisite graph, learner approval gate, stable backbone, and criteria for reinforcement or challenge insertions.

- [ ] **Step 5: Write research and source guidance**

Define primary-source preference, cross-check conditions, current-data handling, claim-to-source mapping, access-date use, uncertainty reporting, and the boundary between sourced facts and uncited stable explanation.

- [ ] **Step 6: Create explicit-only UI metadata**

`agents/openai.yaml` contains a clear display name, a short description, a starter prompt using `$deep-course`, and:

```yaml
policy:
  allow_implicit_invocation: false
```

- [ ] **Step 7: Run package tests and official validation**

Run:

```text
python -m unittest deep-course/tests/test_skill_package.py -v
python <skill-creator-path>/scripts/quick_validate.py deep-course
```

Expected: both commands pass with no missing references or scaffold markers.

- [ ] **Step 8: Commit the director**

```bash
git add deep-course/SKILL.md deep-course/agents/openai.yaml deep-course/references deep-course/tests/test_skill_package.py
git commit -m "feat: add deep-course director workflow"
```

---

### Task 7: Forward-Test the Full Learning Loop

**Files:**
- Modify: `deep-course/tests/evaluation-log.md`
- Modify: Skill or reference files only when an observed failure justifies the change.

**Interfaces:**
- Consumes: the completed Skill package and the three baseline scenarios.
- Produces: independently observed behavior evidence and a disposable sample course outside `deep-course/`.

- [ ] **Step 1: Re-run each baseline scenario with the Skill**

Use fresh contexts and isolated temporary course directories. Record actual artifacts and decisions under a separate “with Skill” result for every observable decision. The long-course scenario passes only if it produces onboarding and an approved skeleton without pre-generating all lessons.

- [ ] **Step 2: Run three variation scenarios**

Verify a conceptual lesson omits decorative media, current facts are deferred or qualified when research is unavailable, and an answer record containing traversal paths is rejected without state mutation.

- [ ] **Step 3: Close only observed instruction gaps**

For each failed decision, identify whether the cause is a weak pointer, missing completion criterion, ambiguous contract, or script defect. Make the narrowest correction, add a regression assertion or scenario observation, and rerun that scenario.

- [ ] **Step 4: Execute an end-to-end state round trip**

Initialize a disposable course, populate a two-node curriculum, generate one lesson from the HTML shell, mark it ready and delivered, export a response, append the attempt, apply mastery evidence, inspect the review queue, and validate the final state.

- [ ] **Step 5: Run the full verification suite**

Run:

```text
python -m unittest discover -s deep-course/tests -p "test_*.py" -v
python <skill-creator-path>/scripts/quick_validate.py deep-course
git diff --check
```

Expected: all tests pass, validation succeeds, and `git diff --check` prints no errors.

- [ ] **Step 6: Commit verified behavior**

```bash
git add deep-course
git commit -m "test: verify adaptive course workflow"
```

---

### Task 8: Final Package Review and Repository Handoff

**Files:**
- Modify: only files implicated by final verification.

**Interfaces:**
- Produces: a clean, locally committed Skill package ready to install or copy, plus a synchronized GitHub branch when repository authentication permits.

- [ ] **Step 1: Review the final diff against the design**

Confirm every lifecycle phase, core lesson artifact, source rule, state invariant, failure condition, and v1 non-goal maps to implemented instructions or tested code. Remove duplicated guidance and unused assets.

- [ ] **Step 2: Verify repository state**

Run:

```text
git status --short
git log --oneline --decorate -10
```

Expected: the working tree is clean and the task commits are present on `main`.

- [ ] **Step 3: Synchronize GitHub when authorized**

If the connected GitHub identity has write access to `edocF/Deep-Course-Skill`, publish the exact local commit sequence to `main`. If authentication remains unavailable, preserve all local commits and report the identity or permission mismatch without rewriting history.
