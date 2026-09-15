---
name: deep-course
description: Build and continue adaptive courses when the learner explicitly invokes $deep-course for sustained learning, practice, or course progress.
---

# Deep Course

Direct one learner's course using evidence, a stable curriculum, and Codex-native
capabilities. Activate only through explicit invocation of `$deep-course`; then
accept ordinary-language requests. Invocation policy lives in
[agents/openai.yaml](agents/openai.yaml).

## Start with state

Resolve the learner's course root; new courses default to `courses/<course-slug>/`
in the active workspace, outside this installed skill. Reuse the selected course;
if several match and selection is unclear, ask which one before mutation.

Read [state-contracts.md](references/state-contracts.md) before accessing state.
Use [course_state.py](scripts/course_state.py) for initialization, validation,
inspection, and deterministic writes. For existing courses, run `validate` and
inspect its JSON before any mutation or lesson generation. Read the profile,
curriculum, progress, and relevant attempts, then use `next-session` with the
current offset-aware time. Infer the operation from this state and the request.

## Route and finish

| Operation | Read and act | Checkable completion |
| --- | --- | --- |
| Create | [Onboarding and curriculum](references/onboarding-and-curriculum.md); initialize only an empty root, interview, diagnose, research, and propose the backbone. | Valid state; linked syllabus, knowledge map, and research; learner approval requested. Until that approval arrives, remain `awaiting_approval` and generate no normal lessons. After approval, record the approved proposal and activate the course. |
| Teach | Require approved curriculum and active course; use [lesson design](references/lesson-design.md) plus [research and sources](references/research-and-sources.md). Include due retrieval and prerequisite repair. | Core artifacts inspected, hashes accepted by `record_lesson`, and ready lesson linked to the learner; then record `delivered`. Delivery is not mastery or completion evidence. |
| Assess | [Assessment and adaptation](references/assessment-and-adaptation.md) for submitted answers, grading, misconceptions, or remediation. | Attempt persisted, mastery transaction applied, later retrieval dates inspected, feedback given, and assessed lesson manifest accepted when applicable. Call `complete_lesson` only after observable rubric evidence supports semantic completion. |
| Progress | Inspect validated state and `next-session`; read assessment guidance when interpreting evidence. | Report completed lessons separately from mastery, due reviews, misconceptions, and the next eligible activity, without changing state. |
| Revise | [Onboarding and curriculum](references/onboarding-and-curriculum.md) for changes to goals, backbone, or duration. | A linked change proposal awaits learner approval, or the approved revision is saved and validates; stable IDs and evidence remain intact. |

If no backbone lesson is unlocked, inspect prerequisite evidence and due reviews;
offer targeted practice. An empty next-session result alone never means completion.

Invoke available visualization, image, PDF, document, or spreadsheet skills only
when the lesson decision identifies a learning objective and learner activity that
benefit. Read that skill's instructions before use. Adapt the
[HTML shell](assets/lesson-template/lesson.html) for the core lesson; keep optional
experiments independently usable. Return direct links only to actual artifacts.

## Recover without inventing results

Invalid or unknown-version state stops mutation: report the helper's code, path,
and field; preserve bytes and repair only with known data and authorized scope.
Root validation does not verify lesson artifacts: use `record_lesson` for manifest
and file-integrity validation after generation and before lifecycle transitions.
Keep partial lessons at draft and retry uncertain writes with the same stable
identifiers. Read the operation reference for recovery details. Unavailable tools
call for an inspectable simpler activity; unavailable research follows the source
reference's uncertainty rules. Never fabricate files, citations, grades, or state.
