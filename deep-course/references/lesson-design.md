# Lesson design and delivery

Read this when planning, generating, validating, or delivering today's lesson.
Use [assessment-and-adaptation.md](assessment-and-adaptation.md) when grading
answers and choosing review or remediation; it owns the evidence rules.

## Plan a learning session

1. Validate root state, then read the learner profile, approved curriculum,
   next-session proposal, due reviews, and recent misconceptions. Choose one
   coherent lesson whose prerequisites the learner can use. If retrieval exposes
   a prerequisite gap, reduce new material and insert a focused repair activity.
2. State observable objectives and how each will be tested. Aim for one new
   concept in a light session, two or three closely connected concepts in a
   normal session, and at most four in a deep session. These are ceilings, not
   quotas: unfamiliar notation or weak prerequisites lower the limit. Scale
   practice and transfer depth before adding unrelated concepts.
3. Allocate learner activity time, including calculation, observation, and
   explanation. Reading length and generation time are not session length.

| Segment | Light: 15 min | Normal: 35 min (default 30–45) | Deep: 75 min (60–90) |
| --- | ---: | ---: | ---: |
| Retrieval before explanation | 2 | 3 | 6 |
| New concepts with worked example | 4 | 10 | 18 |
| Visual/data exploration or equivalent comparison | 2 | 6 | 12 |
| Grounded application case | 2 | 5 | 10 |
| Independent problem solving | 3 | 8 | 23 |
| Final closed-book recall | 2 | 3 | 6 |

Adapt the allocation to learner constraints and evidence. A conceptual lesson
can use a contrast or counterexample in the exploration segment without media.
For deep sessions offer a break and clear stopping point. The plan is ready
when every objective has a prerequisite check, an activity, and an assessment,
and the time allocations fit the chosen session budget.

## Teach through activity

Open with one to three short retrieval prompts drawn from due reviews or known
misconceptions, with solutions initially hidden. For a first lesson, retrieve
relevant diagnostic knowledge rather than inventing a previous lesson.

Introduce each concept through a question, a concise explanation, and a worked
example that exposes the reasoning. Ask the learner to predict or explain a
change before revealing the result. Fade support into an independent problem;
include a transfer problem or counterexample when the time budget permits.

Ground real-world cases in traceable sources. State the date, units, assumptions,
and limits of any data. Clearly label constructed cases and simulated data.
Keep answers and rubrics in answers.md, outside the normal reading path; reveal
objective explanations only after an answer. End with closed-book recall and a
brief explanation of what evidence will inform the next session.

## Choose useful artifacts

| Learning demand | Useful artifact and required learner action |
| --- | --- |
| Relationships, flows, spatial structure | Diagram; trace a path or explain a relationship |
| Quantity, change, uncertainty, comparison | Computed chart/table; predict a result and check units |
| Parameter sensitivity | Spreadsheet or interactive controls; vary a parameter and explain the change |
| Procedures or computational reasoning | Runnable code; execute, modify, and interpret an example |
| Authentic application | Sourced case or dataset; make an evidence-based judgment |
| Visual recognition or concrete scenes | Sourced/generated image; identify or compare observable features |

Use Codex-native tools and relevant artifact skills when available. Every optional
artifact must serve a stated objective and a named activity; omit unused media.
Create PDF when print use adds value, Excel when editable calculations help,
and charts from computed values with inspectable assumptions. Generated images
illustrate concepts; they are not evidence for real events or precise data.
If a tool is unavailable, preserve the activity using a simpler inspectable
format and explain the substitution.

Keep the default lesson as static HTML with local companion assets and no build
step. A complex simulation may be a separate local experiment project with
explicit launch instructions, parameters, and expected observations. The core
lesson must remain usable without that optional project.

## Build and inspect the core package

Create lesson.html, lesson.md, exercises.md, answers.md, sources.md, and the
script-owned state.json under one lessons/<lesson-directory>/ directory.
Keep the HTML and Markdown objectives, examples, and exercises consistent.
Give questions stable IDs and knowledge-node mappings so exported responses
can be assessed against the authored rubric. Browser exports are learner
responses, not authoritative course-state updates.

Use semantic headings and navigation, labeled inputs, visible keyboard focus,
keyboard-operable controls, accessible feedback announcements, sufficient
contrast, responsive layout, and reduced-motion support. Pair diagrams with
text descriptions and charts with units and a readable data alternative; color
alone must not carry meaning. Keep solutions collapsed in the normal path and
make the print experience readable. Inspect the primary HTML at narrow and wide
widths, test at least one objective answer and one open-answer export, and verify
local links and optional downloads before marking the lesson ready.

## Record the lesson lifecycle

Use `record_lesson(root, manifest)` from scripts/course_state.py at every
transition. `validate_course(root)` checks the root-level documents and attempts;
it does not scan lesson files. To recheck an existing lesson's artifact bytes,
replay its unchanged manifest through `record_lesson`.

The manifest has exactly these fields (optional fields appear only in their
applicable lifecycle states):

```json
{
  "schema_version": 1,
  "course_id": "example-course",
  "lesson_id": "lesson-001",
  "lesson_directory": "lessons/001-topic",
  "status": "draft",
  "learning_objectives": [],
  "artifacts": [{"path": "lessons/001-topic/state.json"}]
}
```

Create the lesson directory first. Pass a draft manifest before delivery and
keep incomplete generation at draft. For each other artifact add a record with
`path` and `sha256`, using the SHA-256 of its exact bytes. Store paths relative
to the course root in POSIX form. Absolute paths, traversal, external symlink
targets, and paths outside the selected lesson directory are rejected. The
script normalizes paths and hexadecimal digests. A lesson ID stays bound to
one directory, and that directory cannot be reassigned to a different lesson ID.

state.json is the manifest itself and is created by the script's atomic write.
Its artifact entry has only `path`: a digest inside the file being hashed would
be self-referential. Supplying `sha256` for state.json is rejected. Hash every
other listed artifact, including optional assets.

The legal transitions are `draft -> ready -> delivered -> assessed`:

- **draft:** listed non-state artifacts must exist and match their hashes; the
  objective list and artifact set can be incomplete. Complete the candidate
  manifest when moving to ready.
- **ready:** all six core paths and a nonempty list of objectives are required;
  every non-state artifact must exist and match its hash.
- **delivered:** add `delivered_at` as an ISO 8601 timestamp with an explicit
  offset, after handing the validated lesson to the learner.
- **assessed:** preserve `delivered_at` and add nonempty, unique `attempt_ids`.
  Each ID must already exist in attempts.jsonl and refer to this lesson. Record
  the attempt and apply evidence using the assessment reference first.

The ready boundary freezes the lesson's identity and teaching content. From
ready onward, `schema_version`, `course_id`, `lesson_id`, `lesson_directory`,
`learning_objectives`, and the complete artifact path/hash list are immutable.
A ready-to-delivered transition may add only `status` and `delivered_at`; a
delivered-to-assessed transition may change `status` and add `attempt_ids`,
while preserving `delivered_at`. Revise teaching content under a new lesson ID
and directory rather than attaching an assessment to altered material.

Before accepting any candidate, the script validates every persisted
lessons/*/state.json manifest, including its status-specific metadata and the
bytes of all listed artifacts. Corrupted authoritative lesson state blocks all
lesson recording without replacing a manifest. The one exception is artifact
integrity for the same draft being completed into ready: draft artifacts may be
edited during generation, so the complete ready candidate becomes the new
integrity boundary after its own hashes are checked.

An unchanged normalized manifest is an idempotent replay, including a file
integrity check; changed same-state, skipped, and backward transitions fail.
This v1 API therefore supports completing a draft in the draft-to-ready call,
not rewriting a previously recorded draft in place. Retrying after validation
failure uses the corrected candidate; retrying after an uncertain successful
write uses the same candidate. Keep a delivered lesson stable; use a new lesson
ID and directory for a revised learning activity.

The script validates before atomically replacing only state.json. A rejected
manifest or failed replacement preserves the previous state; it does not roll
back externally edited learning artifacts. This operation neither grades
answers nor changes progress.completed_lessons or mastery. Use one writer at a
time, and let Codex report the lesson as delivered only after this boundary
accepts the delivered manifest.

After the assessed manifest is accepted, use the assessment reference to decide
whether observable rubric evidence establishes semantic lesson completion. Only
then call `complete_lesson(root, lesson_id)`; the separate atomic operation
requires one assessed lesson and does not treat delivery, assessment, or mastery
