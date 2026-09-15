# Assessment and adaptation

Read this reference when grading answers, recording mastery evidence, or choosing
remediation and review activities. State-file ownership and timezone conventions
are defined in [state-contracts.md](state-contracts.md).

## Grade and record

1. Validate the course and identify the lesson, question IDs, knowledge IDs, and
   lesson-specific rubric. Treat a browser export as learner answers, not as an
   authoritative grade or a request to write any supplied filesystem path.
2. Assess the reasoning against the rubric. Codex supplies `quality`, concise
   `feedback`, and specific `misconception_tags`. Distinguish an arithmetic slip
   from a conceptual error; ask a short follow-up if the evidence is ambiguous.
   The script never infers semantic quality from answer text.
3. Assign a stable `attempt_id` to the submission and call `append_attempt` once.
   Include assessed response feedback and misconception tags in this immutable
   record so that next-session inspection can find them. Preserve the learner's
   original answer. A retry uses the same ID; a genuinely new submission gets a
   new ID. Browsing a lesson or revealing an answer supplies no retrieval evidence.
4. Apply the judged evidence using `apply_mastery_updates`. Finish only when the
   attempt is recorded, its progress transaction succeeds, and validation passes.
   If the progress write fails, retry it against the existing attempt ID. An
   already-applied ID is a signal to inspect progress, not to create another ID.
5. After the authored rubric's observable completion criteria are met, record the
   assessed manifest and call `complete_lesson(root, lesson_id)`. This atomically
   records Codex's semantic decision; neither delivery, a submitted attempt, nor
   mastery automatically completes a lesson.
6. Give the learner actionable feedback and the next retrieval activity. Use
   `next_session` to inspect the resulting due dates and recent misconceptions.

### Judgment rubric

| Quality | Evidence interpretation |
| --- | --- |
| `incorrect` | The response demonstrates a gap in the assessed concept. |
| `partial` | Some reasoning is sound, but a material step is missing or assisted. |
| `correct` | Independent reasoning meets the question's rubric. |
| `effortless` | Independent, fluent retrieval or transfer meets the rubric without hints. |

Choose `effortless` only when the interaction supports fluency; a browser's
correct-answer flag or short answer alone is insufficient. A hint-assisted retry
is learning evidence, not a fresh independent success. An unanswered question is
missing evidence unless follow-up establishes a conceptual gap.

## Attempt interface

`append_attempt(root: Path, attempt: dict) -> dict` accepts this shape:

```json
{
  "schema_version": 1,
  "attempt_id": "attempt-001",
  "lesson_id": "lesson-001",
  "submitted_at": "2026-09-11T10:00:00+08:00",
  "responses": [
    {
      "question_id": "q1",
      "knowledge_ids": ["concept-a"],
      "answer": "The learner's original explanation",
      "quality": "partial",
      "misconception_tags": ["direction-reversed"],
      "feedback": "Recheck which quantity is the input."
    }
  ]
}
```

`course_id` is optional and must match when present. Question IDs within an
attempt are unique, knowledge IDs must exist, and grading fields are optional at
append time. An empty responses list can represent an oral assessment whose
context Codex records in metadata. Legacy version-1 objects without an attempt ID
remain inspectable, but cannot be used as mastery evidence.

The return value is `{"attempt_id": "attempt-001", "line_index": 0}`. The line
index is zero-based. Validation and serialization finish before opening the
append stream; rejected input leaves existing bytes unchanged. Successful writes
append compact UTF-8 JSON, a newline, flush, and sync. Caller-supplied `path`,
`paths`, `*_path`, and `*_paths` fields are rejected at every nested level.

## Mastery transaction

Call `apply_mastery_updates(root, attempt_id, updates, occurred_at)` with a nonempty
list of objects containing `knowledge_id` and `quality`. Each object may include
`question_id`, `feedback`, and `misconception_tags`. The timestamp has an explicit
offset and cannot precede the node's most recent practice.

One update without a question ID represents aggregate evidence for that node in
the attempt. Multiple pieces for a node require distinct question IDs that match
the recorded responses and their knowledge mappings. Aggregate and question-level
evidence cannot overlap in one attempt. Evaluate genuinely separate retrievals;
splitting one answer into multiple pieces would inflate evidence.

| Quality | Mastery delta | Confidence delta | Next interval in days |
| --- | ---: | ---: | --- |
| `incorrect` | -0.20 | +0.05 | 1 |
| `partial` | +0.05 | +0.05 | 2 |
| `correct` | +0.15 | +0.10 | max(3, previous interval × 2) |
| `effortless` | +0.20 | +0.10 | max(5, previous interval × 3) |

The script applies rows in supplied evidence order and clamps mastery and
confidence to `[0, 1]`. New nodes start at zero, with a zero-day previous interval.
Confidence is confidence in the estimate, so observed incorrect reasoning can
increase it while lowering mastery. This is a transparent v1 heuristic, not a
calibrated probability or a claim of an optimal learning schedule.

After each piece, incorrect evidence gives `relearning`; other evidence gives
`learning` below 0.75. At 0.75 and above the status is `reviewing`, unless mastery
is at least 0.90 and at least three `correct`/`effortless` pieces exist across at
least two distinct attempts, in which case it is `mastered`. A high numeric score
alone never establishes durable mastery. Continue delayed retrieval after mastery.

`progress.json` stores per-node `mastery`, `confidence`, `status`, `interval_days`,
`last_practiced_at`, `next_review_at`, and an `evidence` list, plus the top-level
`applied_attempt_ids` replay guard. All nodes and the replay guard are validated
and replaced together in one atomic progress write. The result contains
`attempt_id`, `changed_knowledge_ids`, and a `next_review_at` mapping. v1 assumes
one writer at a time; serialize course operations. Attempt append and progress
replacement are separate durable steps, which is why their retry IDs are stable.

## Choose the next activity

Open with due retrieval before adding new material. For a misconception, use a
short contrast, worked example, or data experiment followed by a fresh problem;
schedule another retrieval on a later day even when the immediate retry succeeds.
Use easier prerequisite practice when the prerequisite evidence is weak, and
challenge or transfer problems when it is strong.

Adjust lesson order, pace, review frequency, and inserted remedial or challenge
lessons while retaining the approved outcomes and core modules. Explain a proposed
backbone change and obtain learner approval before applying it. Completion of a
lesson and mastery of its concepts are distinct states.
