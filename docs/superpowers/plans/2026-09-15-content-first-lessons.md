# Content-First Lessons Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Deep Course generate substantial, reading-centered, top-down lessons whose claimed 30–45 minute duration is supported by real content and activities rather than UI labels.

**Architecture:** Add a focused standard-library `lesson_quality` module that audits the canonical `lesson.md`, its HTML delivery, and immutable `quality_evidence`. Gate every new draft-to-ready transition through that audit while preserving legacy lesson manifests. Rewrite the director and lesson template so Codex authors and reviews the complete reading manuscript before it builds sparse, high-value interactions.

**Tech Stack:** Python 3.10+ standard library, `unittest`, semantic HTML/CSS/JavaScript, Markdown reference documents, Codex Skill packaging.

**Spec:** `docs/superpowers/specs/2026-09-15-content-first-lessons-design.md`

## Global Constraints

- `lesson.md` is the canonical teaching manuscript; visible HTML instructional reading units must be at least 90% of Markdown instructional reading units.
- Keep the six core artifacts: `lesson.html`, `lesson.md`, `exercises.md`, `answers.md`, `sources.md`, and `state.json`.
- Runtime code uses only the Python standard library; no agent framework or direct LLM API.
- Hard reading-unit floors are 600 for `light`, 1,800 for `normal`, and 3,500 for `deep`; no exception may go below the floor.
- Planned duration must be 12–20 minutes for `light`, 30–45 for `normal`, and 60–90 for `deep`.
- Planned response time must be at most 35% of the full session.
- Required response controls are limited to 2–3 for `light`, 3–5 for `normal`, and 5–8 for `deep`.
- Content proceeds from whole-model orientation and prerequisites through ordered concepts, examples with faded support, synthesis, transfer, and recall.
- Existing ready, delivered, and assessed manifests without `quality_evidence` remain valid legacy records.
- A failed audit leaves all authoritative course and lesson bytes unchanged.
- Keep current accessibility, local-resource, responsive, print, export, and path-containment guarantees.

---

### Task 1: Establish the shallow-lesson regression signal

**Files:**
- Create: `deep-course/tests/test_lesson_quality.py`
- Create: `deep-course/scripts/lesson_quality.py`
- Read: `deep-course/tests/evaluation-log.md`
- Read: `deep-course/tests/scenarios/quantitative-lesson.md`

**Interfaces:**
- Produces: `reading_units(text: str) -> int`
- Produces: `audit_lesson(root: pathlib.Path, manifest: Mapping[str, object]) -> dict`
- Report shape: `{"valid": bool, "errors": list[dict], "warnings": list[dict], "metrics": dict}`
- Error item shape: `{"code": str, "message": str, "path": str | None, "field": str | None}`; omit optional keys when absent.

- [ ] **Step 1: Write a failing shallow-normal regression test**

Create a `unittest.TestCase` that writes a six-artifact temporary lesson with:

- `planned_minutes: 35`;
- about 350–450 English words of instructional text;
- one compact concept explanation;
- one full example;
- several response prompts; and
- otherwise valid Markdown and HTML.

Use the same observable shape as the existing YTM evaluation sample. The core assertion is:

```python
report = lesson_quality.audit_lesson(root, manifest)
self.assertFalse(report["valid"])
self.assertIn(
    "insufficient_reading_depth",
    {item["code"] for item in report["errors"]},
)
self.assertLess(report["metrics"]["markdown_reading_units"], 1800)
```

- [ ] **Step 2: Run the focused test and observe RED**

Run:

```powershell
python -m unittest deep-course/tests/test_lesson_quality.py -v
```

Expected: import error or missing `audit_lesson`, proving the test reaches the absent quality boundary.

- [ ] **Step 3: Implement deterministic reading extraction**

In `lesson_quality.py`, add:

```python
from html.parser import HTMLParser
from pathlib import Path
import re

DEPTH_LIMITS = {
    "light": {"minutes": (12, 20), "floor": 600, "target": (900, 1800)},
    "normal": {"minutes": (30, 45), "floor": 1800, "target": (2500, 5000)},
    "deep": {"minutes": (60, 90), "floor": 3500, "target": (5000, 9000)},
}

def reading_units(text: str) -> int:
    cjk = len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", text))
    latin_words = len(re.findall(r"\b[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ'’-]*\b", text))
    return cjk + 2 * latin_words
```

Strip fenced code, inline Markdown markers, navigation, scripts, styles, form labels,
buttons, answer keys, and source lists from the instructional measurement. Use
`HTMLParser`; do not use regular expressions to parse HTML structure.

- [ ] **Step 4: Implement the minimum red-capable audit**

`audit_lesson` must resolve `lesson.md` and `lesson.html` from the candidate's
contained `lesson_directory`, compute both reading-unit metrics, and reject a
normal lesson below 1,800 units with `insufficient_reading_depth`. Missing,
unreadable, escaping, or non-text artifacts return structured errors rather than
tracebacks.

- [ ] **Step 5: Run focused and full tests**

Run:

```powershell
python -m unittest deep-course/tests/test_lesson_quality.py -v
python -m unittest discover -s deep-course/tests -p "test_*.py" -v
```

Expected: the new shallow fixture is rejected and all existing tests remain green.

- [ ] **Step 6: Commit**

```powershell
git add deep-course/scripts/lesson_quality.py deep-course/tests/test_lesson_quality.py
git commit -m "feat: reject shallow timed lessons"
```

---

### Task 2: Validate content progression and restrained interaction

**Files:**
- Modify: `deep-course/scripts/lesson_quality.py`
- Modify: `deep-course/tests/test_lesson_quality.py`

**Interfaces:**
- Consumes: `audit_lesson(root, manifest) -> dict` from Task 1.
- Produces: `normalize_quality_evidence(evidence: object, learning_objectives: list[str]) -> dict`.
- `audit_lesson` returns normalized metrics for duration, reading units, concept count, response count, response share, and HTML/Markdown parity.

- [ ] **Step 1: Add failing schema and boundary tests**

Add table-driven tests for these exact failures:

```python
cases = {
    "invalid_time_evidence": {"planned_minutes": 29},
    "missing_progression": {"reading_sections": []},
    "objective_uncovered": {"objectives": []},
    "missing_worked_example": {"worked_examples": []},
    "interaction_overweight": {"response_minutes": 14},
    "html_content_loss": {"html_fraction": 0.50},
    "invalid_quality_evidence": {"contract_version": 99},
}
```

For each mutation, assert the named code and assert that the input manifest and
lesson files are byte-identical after the read-only audit.

Add an anti-filler test in which one paragraph is repeated under several IDs.
Distinct `content_id` values must not pass when normalized instructional blocks
have the same digest.

- [ ] **Step 2: Run the focused tests and observe RED**

Run:

```powershell
python -m unittest deep-course/tests/test_lesson_quality.py -v
```

Expected: failures for every not-yet-implemented error code.

- [ ] **Step 3: Define the exact `quality_evidence` contract**

Accept only these top-level fields:

```python
QUALITY_FIELDS = {
    "contract_version", "session_depth", "planned_minutes", "reading_minutes",
    "response_minutes", "below_target_justification", "objectives",
    "reading_sections", "worked_examples", "response_question_ids",
    "semantic_review",
}
```

Use these nested shapes:

```python
objective = {"objective_id": str, "text": str}
reading_section = {
    "content_id": str,
    "role": "orientation" | "prerequisite_bridge" | "concept" | "synthesis" | "consolidation",
    "markdown_heading": str,
    "html_id": str,
    "objective_ids": list[str],
    "prerequisite_knowledge_ids": list[str],
}
worked_example = {
    "example_id": str,
    "support": "full" | "faded" | "independent",
    "markdown_heading": str,
    "html_id": str,
    "objective_ids": list[str],
}
semantic_review = {
    "passed": True,
    "reviewed_at": offset_aware_iso8601,
    "revision_summary": nonempty_str,
}
```

Reject booleans as numbers, duplicate or unsafe IDs, unknown fields, unknown
references, non-finite values, and timestamps without an explicit offset.

- [ ] **Step 4: Implement progression checks**

For `normal`, require all five roles, two or three `concept` sections, at least
one `full` and one `faded` example, and one `independent` task represented in
either `worked_examples` or `response_question_ids`. Require every objective ID
to appear in at least one concept section and one worked/independent item.

The objective texts in `quality_evidence.objectives` must equal the manifest's
`learning_objectives` in order.

- [ ] **Step 5: Implement time and interaction checks**

Validate the exact depth ranges from `DEPTH_LIMITS`. Require:

```python
0 < reading_minutes < planned_minutes
0 <= response_minutes <= planned_minutes * 0.35
```

Enforce response counts of 2–3, 3–5, and 5–8 for light, normal, and deep.
Falling below the target reading band adds `below_target_reading` warning and
requires nonempty `below_target_justification`; falling below the hard floor is
always an error.

- [ ] **Step 6: Implement artifact correspondence and parity**

Parse Markdown ATX headings and HTML IDs. Verify every declared heading and ID
exists exactly once. Extract each reading block, normalize whitespace and
punctuation, and reject duplicate block digests. Compute:

```python
html_fraction = html_instructional_units / max(markdown_instructional_units, 1)
```

Reject values below `0.90`. Verify every `response_question_id` exists in the
embedded `lesson-data` JSON and that no undeclared required response control is
present.

- [ ] **Step 7: Run tests and commit**

```powershell
python -m unittest deep-course/tests/test_lesson_quality.py -v
python -m unittest discover -s deep-course/tests -p "test_*.py" -v
git add deep-course/scripts/lesson_quality.py deep-course/tests/test_lesson_quality.py
git commit -m "feat: validate lesson progression evidence"
```

---

### Task 3: Gate new ready lessons without breaking legacy courses

**Files:**
- Modify: `deep-course/scripts/course_state.py:30-35,930-1160`
- Modify: `deep-course/tests/test_course_state.py:535-900`
- Test: `deep-course/tests/test_lesson_quality.py`

**Interfaces:**
- Consumes: `lesson_quality.audit_lesson(root, manifest) -> dict`.
- Produces: lesson manifests with optional immutable `quality_evidence`.
- Preserves: `record_lesson(root: Path, manifest: dict) -> dict` and all public error behavior.

- [ ] **Step 1: Add failing lifecycle tests**

Add tests proving:

1. a new draft-to-ready candidate without `quality_evidence` fails with
   `missing_quality_evidence`;
2. a candidate with an invalid audit fails using the audit's first error code;
3. either failure preserves the exact pre-call bytes;
4. a valid audited candidate reaches ready;
5. `quality_evidence` cannot change after ready;
6. unchanged replay reruns content integrity and quality checks;
7. existing ready/delivered/assessed state without evidence remains valid;
8. a previously recorded legacy draft must supply evidence when it transitions
   to ready; and
9. attempts, assessment, and completion behavior are unchanged.

- [ ] **Step 2: Run focused lifecycle tests and observe RED**

```powershell
python -m unittest discover -s deep-course/tests -p "test_course_state.py" -v
```

Expected: only the new quality-integration assertions fail.

- [ ] **Step 3: Extend the manifest shape safely**

Add `quality_evidence` to the allowed manifest fields and
`LESSON_CONTENT_FIELDS`. Normalize it through
`lesson_quality.normalize_quality_evidence` before JSON preflight.

Do not require evidence while recording a new `draft`. Require it when the
candidate crosses from draft to ready. Treat a persisted non-draft manifest
without the field as legacy only when it already existed before the call.

- [ ] **Step 4: Invoke the gate before any state write**

After artifact hashes pass but before `atomic_write_json`, call:

```python
quality = lesson_quality.audit_lesson(root, candidate)
if not quality["valid"]:
    first = quality["errors"][0]
    raise CourseStateError(first["code"], first["message"], Path(first["path"]) if first.get("path") else None)
```

Complete all audit and serialization preflight before opening a temporary output.
Do not mutate the caller's manifest.

- [ ] **Step 5: Test atomic failure and backward compatibility**

Patch the audit to fail after artifact reads and assert all files remain
byte-identical. Replay real legacy fixture states through delivered and assessed
transitions. Confirm only teaching-content fields are frozen; delivery and
attempt metadata retain their existing legal transitions.

- [ ] **Step 6: Run tests and commit**

```powershell
python -m unittest deep-course/tests/test_lesson_quality.py -v
python -m unittest discover -s deep-course/tests -p "test_course_state.py" -v
python -m unittest discover -s deep-course/tests -p "test_*.py" -v
git add deep-course/scripts/course_state.py deep-course/tests/test_course_state.py deep-course/scripts/lesson_quality.py deep-course/tests/test_lesson_quality.py
git commit -m "feat: gate ready lessons on content quality"
```

---

### Task 4: Rewrite the director around reading and editorial quality

**Files:**
- Create: `deep-course/references/lesson-quality.md`
- Modify: `deep-course/SKILL.md`
- Modify: `deep-course/references/lesson-design.md`
- Modify: `deep-course/references/research-and-sources.md`
- Modify: `deep-course/references/assessment-and-adaptation.md`
- Modify: `deep-course/references/state-contracts.md`
- Modify: `deep-course/tests/test_skill_package.py`

**Interfaces:**
- Consumes: the exact audit and manifest contracts from Tasks 1–3.
- Produces: a content-first authoring protocol that routes every Teach operation through manuscript, semantic review, quality audit, HTML derivation, and lifecycle validation.

- [ ] **Step 1: Add failing package-contract tests**

Assert that the packaged instructions explicitly contain and link all of these
requirements:

```python
required_phrases = {
    "canonical teaching manuscript",
    "whole-model preview",
    "prerequisite bridge",
    "faded",
    "reading_units",
    "35%",
    "90%",
    "fresh reviewing subagent",
}
```

Assert `SKILL.md` routes Teach to `lesson-quality.md`, and every referenced path
is contained and exists.

- [ ] **Step 2: Run package tests and observe RED**

```powershell
python -m unittest deep-course/tests/test_skill_package.py -v
```

- [ ] **Step 3: Write `lesson-quality.md`**

Turn the approved spec into an operational checklist, including:

- reading-volume floors and target bands;
- top-down required roles;
- full/faded/independent example sequence;
- objective coverage matrix;
- sparse-interaction policy;
- semantic editorial rubric;
- structured `quality_evidence` example;
- exact audit command/API and error recovery; and
- rejection behavior that keeps the lesson draft.

Keep explanatory rationale here; keep `SKILL.md` short and directive.

- [ ] **Step 4: Rewrite lesson authoring order**

In `lesson-design.md`, replace HTML-slot-first language with this strict order:

```text
state and prerequisites
→ teaching blueprint
→ focused research
→ complete lesson.md manuscript
→ skeptical content review and revision
→ exercises / answers / sources
→ faithful lesson.html derivation
→ deterministic quality audit
→ responsive/export inspection
→ record ready
```

State that a learner must be able to obtain the main value by reading without
answering every control. Do not require a question after every concept.

- [ ] **Step 5: Align research, assessment, state, and director references**

Research guidance must prioritize explanatory synthesis and source quality.
Assessment guidance must not convert every reading checkpoint into state
evidence. State guidance must document new evidence, legacy handling, audit
errors, and immutable fields. `SKILL.md` must refuse delivery when the content
audit or skeptical editorial review fails.

- [ ] **Step 6: Run tests and commit**

```powershell
python -m unittest deep-course/tests/test_skill_package.py -v
python -m unittest discover -s deep-course/tests -p "test_*.py" -v
git add deep-course/SKILL.md deep-course/references deep-course/tests/test_skill_package.py
git commit -m "docs: make deep-course reading centered"
```

---

### Task 5: Replace the slot-driven shell with a reading-first template

**Files:**
- Modify: `deep-course/assets/lesson-template/lesson.html`
- Modify: `deep-course/tests/test_lesson_template.py`
- Test: `deep-course/tests/test_lesson_quality.py`

**Interfaces:**
- Consumes: `reading_sections`, `worked_examples`, and response IDs from the quality contract.
- Preserves: `Lesson.validate`, `Lesson.feedback`, `Lesson.buildResponse`, and `Lesson.downloadResponse` JavaScript APIs.
- Produces: semantic article sections with stable `data-content-id`, example IDs, and sparse `data-questions` containers.

- [ ] **Step 1: Add failing reading-first template tests**

Test for:

- curriculum-position and whole-model preview blocks before concept detail;
- a prerequisite bridge;
- at least two nested concept chapters in the normal example;
- full and faded examples with stable IDs;
- synthesis before independent application;
- no locked or click-to-unlock reading content;
- required response count within 3–5;
- substantial uninterrupted prose between response controls;
- all instructional sections printable and available without JavaScript;
- current focus, accessibility, responsive, feedback, and export guarantees.

- [ ] **Step 2: Run template tests and observe RED**

```powershell
python -m unittest deep-course/tests/test_lesson_template.py -v
```

- [ ] **Step 3: Restructure the semantic HTML**

Use this top-level sequence:

```html
<header id="orientation" data-content-id="orientation">…</header>
<section id="prerequisite-bridge" data-content-id="prerequisite-bridge">…</section>
<section id="concept-one" data-content-id="concept-one">…</section>
<section id="concept-two" data-content-id="concept-two">…</section>
<section id="synthesis" data-content-id="synthesis">…</section>
<section id="independent-application">…</section>
<section id="recall">…</section>
```

Keep optional figures, tables, and calculators adjacent to the explanation they
serve. Remove labels such as “visual slot” and “case slot.” Use callouts for
examples and boundaries, not for every paragraph.

- [ ] **Step 4: Reduce interaction density without weakening assessment**

Ship a normal example with four required responses: prior retrieval, one major
checkpoint, independent application, and recall. Preserve immediate authored
feedback only for the objective checkpoint. Keep all reading visible regardless
of response state.

- [ ] **Step 5: Make the example itself content-rich**

The template example must meet the normal hard floor, demonstrate two connected
concept chapters, and include a full and faded example. It is a teaching model,
not placeholder copy. Clearly label any constructed facts.

- [ ] **Step 6: Run focused, quality, and full tests**

```powershell
python -m unittest deep-course/tests/test_lesson_template.py -v
python -m unittest deep-course/tests/test_lesson_quality.py -v
python -m unittest discover -s deep-course/tests -p "test_*.py" -v
```

- [ ] **Step 7: Commit**

```powershell
git add deep-course/assets/lesson-template/lesson.html deep-course/tests/test_lesson_template.py deep-course/tests/test_lesson_quality.py
git commit -m "feat: make lesson template content first"
```

---

### Task 6: Prove lesson quality with unseen forward evaluations

**Files:**
- Create: `deep-course/tests/scenarios/content-first-conceptual.md`
- Create: `deep-course/tests/scenarios/content-first-quantitative.md`
- Create: `deep-course/tests/scenarios/content-first-technical.md`
- Modify: `deep-course/tests/evaluation-log.md`
- Modify: `deep-course/tests/test_lesson_quality.py`
- Modify: `deep-course/tests/test_skill_package.py`

**Interfaces:**
- Consumes: the complete director, audit, and template contracts.
- Produces: three fresh lesson packages plus independent review evidence; only stable, reusable fixtures enter tracked tests.

- [ ] **Step 1: Author three behavior prompts and pass/fail rubrics**

Each scenario requests a normal lesson but does not mention word count or the new
implementation. The rubrics independently score:

1. correctness and source quality;
2. whole-to-parts organization;
3. prerequisite-to-transfer progression;
4. reading depth and continuity;
5. full and faded examples;
6. restraint and value of questions;
7. credible 30–45 minute activity evidence; and
8. usefulness without completing every interaction.

- [ ] **Step 2: Run each scenario with a fresh subagent**

Use unrelated topics so the implementation cannot overfit:

- conceptual: constitutional separation of powers or an equivalent sourced social-science topic;
- quantitative: duration and interest-rate sensitivity or an equivalent finance/science topic;
- technical: distributed-system replication or an equivalent systems topic.

Save outputs under the plan-scoped evaluation workspace, not inside the Skill
package. Record exact prompts, artifacts, audit JSON, and generation timestamp.

- [ ] **Step 3: Run independent content reviews**

Different reviewing agents must read the complete lesson rather than its summary.
They report Critical/Important/Minor findings and estimate actual learner time by
separating reading, example work, and required responses. A lesson fails if it is
primarily an interactive shell or if reading cannot carry the lesson on its own.

- [ ] **Step 4: Convert discovered regressions into tests**

For every reproducible failure, add the smallest fixture or assertion that would
have prevented it. Observe RED before changing the implementation, then make the
single corrective change and rerun the original forward scenario.

- [ ] **Step 5: Record evaluation evidence and commit**

```powershell
python -m unittest discover -s deep-course/tests -p "test_*.py" -v
git add deep-course/tests
git commit -m "test: evaluate content-first lessons"
```

---

### Task 7: Document, validate, review, and open the protected-branch PR

**Files:**
- Modify: `README.md`
- Modify: any package file required by verified Task 6 findings
- Verify: all files under `deep-course/`

**Interfaces:**
- Consumes: all previous tasks and forward-evaluation evidence.
- Produces: a complete reviewed branch and a PR from `codex/content-first-lessons` to `main`.

- [ ] **Step 1: Update README behavior claims**

Document the reading-centered pipeline, manuscript-first authoring, depth gate,
interaction restraint, and backward compatibility. Avoid presenting raw word
count as the definition of learning time.

- [ ] **Step 2: Run the official package validator**

```powershell
python C:/Users/fht74/.codex/skills/.system/skill-creator/scripts/quick_validate.py deep-course
```

Expected: `Skill is valid!`

- [ ] **Step 3: Run the complete verification suite**

```powershell
python -m unittest discover -s deep-course/tests -p "test_*.py" -v
git diff --check main...HEAD
git status --short
```

Expected: all tests pass, diff check is silent, and no intended file remains uncommitted.

- [ ] **Step 4: Request independent standards and spec reviews**

Run two reviews in parallel against `main...HEAD`:

- standards: Python safety, content audit correctness, HTML accessibility, tests, maintainability;
- spec: every section of `2026-09-15-content-first-lessons-design.md`, especially reading primacy and restrained interaction.

Fix all Critical and Important findings with one focused subagent and perform one
scoped re-review. Record any deliberately deferred Minor finding with its cost.

- [ ] **Step 5: Commit final documentation or review fixes**

```powershell
git add README.md deep-course
git commit -m "docs: document content-first lesson quality"
```

Skip this commit only if no tracked file changed after Task 6.

- [ ] **Step 6: Push and create the PR**

```powershell
git push -u origin codex/content-first-lessons
```

Create a non-draft PR targeting `main`. The body must include the original
384-word/35-minute failure, the new deterministic gate, reading-centered design,
backward compatibility, full test count, validator result, and links to the
three forward-evaluation summaries.
