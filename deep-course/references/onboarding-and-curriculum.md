# Onboarding and curriculum

Read when creating a course, resuming unfinished onboarding, requesting curriculum
approval, or revising goals, the backbone, or expected duration. State ownership
and metadata writes follow [state-contracts.md](state-contracts.md).

## Interview and diagnose

Collect the goal and observable application, prior knowledge, available time and
course duration, constraints, preferred language, and application context. Reuse
answers already supplied; ask only about missing information that affects scope,
prerequisites, or workload. Put learner statements in learner-profile.json and
distinguish them from inferred ability. Choose light (about 15 minutes), normal
(30-45 minutes, default), or deep (60-90 minutes) sessions to fit the budget.

Ask a small adaptive diagnostic before proposing the curriculum. Start with a
representative application and explanation of a prerequisite. Select the next
question from the evidence: probe a simpler prerequisite after a gap, or test
transfer after independent success. Stop when each prerequisite needed to choose
the starting module has either an observed usable response or an identified gap,
and another answer would not change that placement. Also stop at the learner's
time limit or explicit request to skip; mark unresolved prerequisites unknown.
Record questions, original answers, inference, and placement uncertainty in
research/diagnostic.md. Do not turn self-report or a single answer into mastery.

If the diagnostic is skipped, record `diagnostic_status: skipped` and
`baseline_confidence: low` as profile metadata, with conservative starting-level
assumptions and the reason. Leave progress evidence empty for untested nodes;
start at foundational prerequisites and check them during the first session.
After the knowledge graph exists, actual diagnostic responses may be mapped to
stable knowledge IDs and recorded through the assessment helpers. Preserve the
distinction between observed answers and assumed placement.

## Research and propose

Use [research-and-sources.md](research-and-sources.md) for broad research before
designing the course. Map major concepts, real applications, prerequisite chains,
authoritative source classes, and areas needing current or specialist evidence.
Save course-specific findings in research/; no subject curriculum belongs in the
installed skill. Research enough to justify the scope and sequence, leaving
lesson-specific investigation for the current lesson.

Build curriculum.json with observable learning outcomes, modules, knowledge nodes,
and a backbone of stable lesson IDs. Each node has an acyclic prerequisite list;
each backbone entry maps objectives to knowledge IDs and declares needed
prerequisites. Include assessment evidence for outcomes, pacing, and expected
duration in the proposal. Validate the graph before presenting it. Produce:

- syllabus.md: goal, outcomes, modules, proposed sequence and workload, assessment
  approach, duration, assumptions, and unresolved source needs.
- knowledge-map.md: prerequisite relationships and the evidence needed to advance.
- research/source-map.md: sources and coverage supporting the proposed architecture.

These files are views of the candidate curriculum, not independently authoritative
state. Cross-check them against curriculum.json. Set curriculum to `proposed` and
course to `awaiting_approval` only after candidate validation; provide links and
ask the learner to approve the goal, backbone, and duration. Produce the skeleton
at this stage; do not prewrite downstream lessons or facilitator packs.

## Approval is a boundary

Normal lesson generation starts only after the learner approves the concrete
proposal. An existing explicit approval of that same proposal remains valid;
do not ask again. A deadline, request to make the package look finished, or
technical-owner release review is not learner approval of an unseen curriculum.

| Pressure signal | Required result |
| --- | --- |
| A review deadline makes a full course seem urgent. | Deliver the inspectable proposal and request learner approval. |
| Technical review gates are already listed. | Still establish approval of learning goals and the backbone. |

Record the approval's date and the exact approved goal, backbone, and duration in
research/approval.md, then set curriculum `approved` and course `active` using the
metadata write protocol. A resume after partial activation checks the recorded
approval and exact curriculum; it never infers approval from `active` alone.

## Adapt within the approved course

Keep approved outcomes, core modules, duration, stable IDs, and prerequisite
meaning intact. Within those boundaries, adjust session depth, practice quantity,
review timing, or local lesson order when prerequisites permit and the learner
has not fixed that order. A reinforcement insertion addresses a specific observed
gap with an independent follow-up problem and a later retrieval opportunity.
A challenge insertion requires strong independent evidence and targets transfer
or a harder application of approved outcomes. Use new lesson IDs for insertions;
they need not replace backbone entries. Read
[assessment-and-adaptation.md](assessment-and-adaptation.md) to grade and schedule
retrieval, and [lesson-design.md](lesson-design.md) to produce the selected activity.

If the change affects approved goals, the module backbone, prerequisite meaning,
or expected duration, save a revision proposal in research/ with its rationale,
exact changes, evidence, and consequences. Keep the currently approved curriculum
until the learner accepts that proposal. Preserve knowledge and lesson IDs that
retain meaning; introduce new IDs for changed concepts, keep historical nodes
needed by existing evidence, and never relabel old evidence as new mastery.
Use the metadata protocol after approval and regenerate syllabus/map views.
If v1 cannot represent the revision without invalidating history, leave it as a
proposal and explain the concrete limitation rather than rewriting evidence.
