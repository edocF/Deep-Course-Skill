# Deep Course content-first lesson redesign

Date: 2026-09-15
Status: proposed for implementation after user review

## Problem

Deep Course currently has a sound state engine and an accessible interactive
lesson shell, but its lesson-quality contract can accept material that is much
too thin. The repository's own fixed-income sample labels itself as a 35-minute
lesson while containing roughly 384 visible words. It presents one compact
model, one worked calculation, a calculator, and several questions. The page is
functional, but it is not a sufficiently developed lesson.

The existing checks verify structure, accessibility, response export, artifact
integrity, and state transitions. They do not reject a lesson that lacks:

- a top-down map of the subject;
- a prerequisite bridge;
- progressively developed explanations;
- enough high-quality reading material;
- multiple examples with gradually reduced support;
- synthesis across the lesson's concepts; or
- credible evidence for the claimed session duration.

The result is an HTML interaction shell that can look finished before the
teaching content is finished.

## Product decision

Deep Course will become **content-first and reading-centered**.

The main learning path is a carefully researched and edited explanation. The
learner is trusted to read, pause, think, and ask Codex when something remains
unclear. Interactive controls support the reading at a few high-leverage points;
they do not drive every paragraph or repeatedly demand proof of attention.

`lesson.md` is the canonical teaching manuscript. `lesson.html` is a faithful,
enhanced delivery of that manuscript, not a shorter substitute for it.

## Goals

1. Make a normal lesson genuinely capable of supporting 30–45 minutes of
   learning.
2. Explain from the whole to the parts, and from prerequisites to transfer.
3. Give the learner substantial uninterrupted space to read.
4. Prefer depth, clarity, examples, and source quality over interaction count.
5. Ask questions only where retrieval, prediction, diagnosis, or independent
   application materially improves learning.
6. Reject shallow lessons before they reach the `ready` lifecycle state.
7. Preserve the existing deterministic, standard-library-only runtime and the
   six core lesson artifacts.

## Non-goals

- Maximizing word count without improving understanding.
- Turning lessons into quizzes, games, or step-by-step wizards.
- Interrupting the learner after every concept or paragraph.
- Requiring an image, chart, spreadsheet, or simulation in every lesson.
- Automatically grading open reasoning inside the browser.
- Adding an agent framework, direct LLM API, or third-party runtime dependency.

## The reading-centered lesson experience

### Normal session: reference allocation

The default normal lesson targets about 36 minutes:

| Learning activity | Minutes | Purpose |
| --- | ---: | --- |
| Orientation and course position | 2 | Show the whole, the destination, and the prerequisite bridge. |
| Structured reading | 18 | Develop two or three connected concepts without needless interruption. |
| Worked examples or evidence exploration | 6 | Expose reasoning, assumptions, and intermediate steps. |
| Focused checkpoint | 3 | Ask at a genuine conceptual turning point. |
| Independent synthesis or transfer | 5 | Require the learner to use the complete model. |
| Closed-book recall | 2 | Consolidate the lesson and expose the next useful review target. |

This table is a planning reference, not permission to attach minute labels to
short sections. The quality gate requires inspectable content and activities
that support the allocation.

### Other session depths

| Depth | Reading-centered shape |
| --- | --- |
| `light` | One concept, a concise but complete explanation, one example, one focused check, and recall in about 15 minutes. |
| `normal` | Two or three connected concepts, sustained reading, at least two levels of example support, synthesis, and recall in 30–45 minutes. |
| `deep` | Three or four tightly related concepts, primary-source or data work where useful, several examples, an extended synthesis task, and a stopping point in 60–90 minutes. |

### Reading-volume guardrails

Reading volume is not a substitute for editorial quality, but abnormally small
content must not pass. The audit computes a language-neutral approximation:

```text
reading_units = CJK characters + 2 × Latin-script words
```

Target bands for authored instructional prose are:

| Depth | Target reading units | Hard floor |
| --- | ---: | ---: |
| `light` | 900–1,800 | 600 |
| `normal` | 2,500–5,000 | 1,800 |
| `deep` | 5,000–9,000 | 3,500 |

The measurement excludes navigation, buttons, answer keys, source lists, and
repeated UI text. Code, equations, diagrams, data inspection, and substantial
calculation time may justify falling below the target band, but instructional
prose must never fall below the hard floor. Every below-target justification
must name the compensating activity, its estimated learning time, and why more
prose would harm rather than improve learning.

Passing the volume check never proves that a lesson is good. It only prevents
the current failure mode in which a few paragraphs are presented as a complete
normal session.

## Required top-down content architecture

Every normal or deep lesson follows this reading spine.

### 1. Position and whole-model preview

- Identify where the lesson sits in the approved curriculum.
- State the practical or intellectual problem the lesson resolves.
- Show a compact whole-model preview before introducing details.
- Connect required prior knowledge to the new model.
- Tell the learner what can be ignored until a later lesson.

### 2. Progressive concept chapters

A normal lesson contains two or three closely connected concept chapters. Each
chapter must contain:

1. a guiding question that focuses reading but does not require form input;
2. an intuitive explanation in plain language;
3. the formal definition, mechanism, notation, or procedure;
4. an example with visible reasoning and intermediate steps;
5. a boundary, counterexample, or common misconception when relevant; and
6. a forward connection explaining why the next chapter follows.

The sequence must be dependency-aware. Later chapters may use earlier ideas;
earlier chapters must not quietly rely on material that has not been introduced.

### 3. Faded support

The lesson moves through three levels rather than jumping from exposition to a
test:

- **fully worked**: every reasoning step is visible;
- **partially worked**: the learner predicts or supplies one meaningful step;
- **independent transfer**: the learner applies the combined model in a changed
  context.

For a normal lesson, at least one fully worked example and one partially worked
example are required. The independent transfer task belongs near the end.

### 4. Synthesis and boundaries

Before independent work, reconnect the parts into one model. Include an
authentic sourced case, constructed case, comparison, derivation, code trace,
or data interpretation as appropriate. State assumptions and limits.

### 5. Consolidation

End with:

- a compact conceptual synthesis, not a list of copied headings;
- one independent application or transfer problem;
- a short closed-book recall prompt; and
- a note explaining how the response will affect the next session.

## Interaction policy: trust the learner

Questions are scarce and purposeful.

- Expository guiding questions may appear as prose and do not require a form.
- Required response controls appear only for retrieval, a major conceptual
  checkpoint, independent application, or final recall.
- A normal lesson usually has three to five required responses; a light lesson
  two to three; a deep lesson five to eight.
- There is no required response merely to unlock the next reading section.
- The learner can read the complete lesson continuously and ask Codex follow-up
  questions at any time.
- Immediate browser feedback is reserved for objective items where authored
  feedback is useful. Open reasoning remains available for later assessment.
- When in doubt, add a clearer paragraph or example before adding another quiz.

## Research and editorial quality

Research must improve the manuscript, not merely populate `sources.md`.

For each major concept, the lesson author will identify the best available
explanatory basis: primary documentation, a respected textbook or university
course, a standard, a high-quality paper, or authoritative data. The manuscript
must synthesize the material in its own structure and language. It must not copy
long passages or use citations as a substitute for explanation.

The content review checks:

- factual and mathematical correctness;
- source authority and claim-to-source traceability;
- explanatory clarity and appropriate prerequisites;
- coherent ordering from whole model to detail;
- examples that illuminate the concept rather than decorate it;
- sufficient depth for the learner's stated level;
- explicit assumptions, scope, and uncertainty; and
- removal of filler, repetition, and unsupported claims.

## Content-first generation pipeline

### Stage 1: select and bound the lesson

Read validated course state, the approved curriculum, prerequisite evidence,
due reviews, recent mistakes, and the learner profile. Select one coherent
lesson and decide what is deliberately out of scope.

### Stage 2: build the teaching blueprint

Before authoring artifacts, produce an internal blueprint containing:

- the whole-model preview;
- prerequisite bridge;
- ordered concept dependency chain;
- objective-to-explanation/example/practice mapping;
- likely misconceptions;
- sources and evidence needs;
- reading and activity time budget; and
- planned points of interaction.

The blueprint is generation state, not a seventh required learner artifact.

### Stage 3: research and write `lesson.md`

Write the complete canonical manuscript first. Do not create the HTML shell
while the conceptual chapters are still summaries or placeholders. The
manuscript includes the overview, progressive chapters, examples, synthesis,
and consolidation path. Exercises and hidden solutions remain in their
respective core files.

### Stage 4: semantic content review and revision

Codex rereads the manuscript as a skeptical editor and answers the quality
rubric with cited section anchors. Any failed item returns the lesson to draft.
When subagents are available, a fresh reviewing subagent performs this review;
otherwise Codex performs a separate skeptical second pass after authoring.
The review must specifically ask:

- Could a motivated learner understand the subject by reading this without
  clicking every control?
- Does each section earn its place and prepare the next?
- Is the explanation deep enough for the claimed session duration?
- Are examples doing explanatory work?
- Are questions concentrated at high-value moments?
- Has the text trusted the learner rather than micromanaged attention?

### Stage 5: derive the remaining artifacts

Create `lesson.html` as a faithful presentation of the full manuscript. Add
navigation, optional media, calculators, and response controls without replacing
the reading with summaries. Then create or reconcile `exercises.md`,
`answers.md`, and `sources.md`.

### Stage 6: deterministic quality audit

Run the standard-library quality module. It measures and cross-checks the
artifacts, then returns structured errors and warnings. Only a passing audit can
enter `ready`.

### Stage 7: visual and functional inspection

Inspect wide, narrow, and print layouts; test one objective response, one open
response, and export. This remains necessary but occurs after content approval.

## Deterministic quality module

Add `deep-course/scripts/lesson_quality.py` as a focused standard-library module.
`course_state.record_lesson()` calls its public audit boundary for every new
`ready` candidate.

The candidate manifest adds immutable `quality_evidence` for new lessons:

```json
{
  "contract_version": 1,
  "session_depth": "normal",
  "planned_minutes": 36,
  "reading_minutes": 18,
  "objectives": [
    {
      "objective_id": "obj-price-from-cash-flows",
      "text": "Price a bond by discounting each promised cash flow."
    }
  ],
  "concept_blocks": [
    {
      "content_id": "discounting-cash-flows",
      "objective_ids": ["obj-price-from-cash-flows"],
      "prerequisite_knowledge_ids": ["time-value-of-money"],
      "markdown_heading": "Discount each cash flow",
      "html_id": "discount-each-cash-flow"
    }
  ],
  "worked_examples": [
    {"example_id": "bond-price-full", "support": "full"},
    {"example_id": "bond-price-faded", "support": "faded"}
  ],
  "response_question_ids": ["prior-retrieval", "price-check", "transfer", "recall"],
  "semantic_review": {
    "passed": true,
    "reviewed_at": "2026-09-15T12:00:00+08:00",
    "revision_summary": "Expanded the prerequisite bridge and added a faded example."
  }
}
```

The audit derives evidence from the actual files rather than trusting reported
counts. It verifies:

- planned session duration is 12–20 minutes for `light`, 30–45 minutes for
  `normal`, and 60–90 minutes for `deep`;
- visible instructional reading meets the hard floor;
- required content roles and ordered concept blocks exist, with exactly one
  concept block for `light`, two or three for `normal`, and three or four for
  `deep`;
- every objective has a stable ID, its evidence text exactly matches the
  corresponding `learning_objectives` text, and it maps to explanation,
  example, and assessment evidence;
- required full and faded examples exist for normal/deep lessons;
- required response controls number two or three for `light`, three to five for
  `normal`, and five to eight for `deep`;
- planned response time is at most 35% of planned session duration;
- Markdown headings and HTML section anchors agree;
- visible HTML instructional reading units are at least 90% of the canonical
  Markdown manuscript's instructional reading units; and
- all question IDs referenced by quality evidence exist in lesson data.

Representative error codes include:

- `insufficient_reading_depth`
- `missing_progression`
- `objective_uncovered`
- `missing_worked_example`
- `interaction_overweight`
- `invalid_time_evidence`
- `html_content_loss`
- `invalid_quality_evidence`

An audit failure leaves the lesson in draft and does not change authoritative
state.

## Backward compatibility

The six required lesson artifacts remain unchanged:

- `lesson.html`
- `lesson.md`
- `exercises.md`
- `answers.md`
- `sources.md`
- `state.json`

Existing ready, delivered, and assessed lesson manifests without
`quality_evidence` remain valid as legacy records. New transitions from draft to
ready require the content-first evidence. Once accepted, quality evidence is
immutable with the rest of the ready lesson identity.

Previously created learner courses need no destructive migration. Their next
new lesson uses the new quality contract.

## Template changes

The HTML template will stop presenting six equal-weight UI slots as though the
slots themselves were the lesson. Its primary `<main>` becomes a reading-first
article with:

- curriculum position and whole-model preview;
- nested concept navigation;
- long-form concept chapters;
- visually distinct examples, boundaries, and synthesis;
- optional figures and calculators embedded beside the relevant explanation;
- sparse response controls at chosen checkpoints; and
- a final application and recall section.

All current accessibility, local-resource, responsive, print, and response
export guarantees remain.

## Testing strategy

### Red regression fixture

Use the current 35-minute fixed-income sample as the initial shallow fixture. A
single quality-audit command must reject it for insufficient reading depth and
missing progression even though its HTML is valid and interactive.

### Positive fixtures

Create content-rich conceptual and quantitative normal lessons that pass only
when they contain the complete reading spine, objective coverage, full and
faded examples, credible time evidence, restrained questions, and HTML/Markdown
parity.

### Required automated cases

1. A minute label attached to short content fails.
2. Repeated filler cannot satisfy distinct concept-block coverage.
3. A missing prerequisite bridge or whole-model preview fails.
4. An objective without explanation, example, or assessment mapping fails.
5. A normal lesson without full and faded examples fails.
6. A quiz-heavy lesson fails `interaction_overweight`.
7. HTML that compresses or omits substantial manuscript content fails.
8. A rejected audit preserves existing lesson and course bytes.
9. Legacy completed lessons remain valid.
10. Existing state, export, accessibility, and responsive tests remain green.

### Forward evaluation

Generate at least three unseen normal lessons:

- a conceptual humanities or social-science lesson;
- a quantitative finance or science lesson; and
- a technical systems lesson.

Independent reviewers score each lesson for:

- content correctness and source quality;
- top-down organization;
- progressive explanation;
- reading depth and continuity;
- example quality;
- restraint and usefulness of questions;
- authenticity of the 30–45 minute claim; and
- usefulness without interacting with every control.

Any lesson that is primarily an interactive shell, or that cannot support a
substantial uninterrupted reading path, fails the release evaluation.

## Files expected to change

- `deep-course/SKILL.md`
- `deep-course/references/lesson-design.md`
- `deep-course/references/research-and-sources.md`
- `deep-course/references/assessment-and-adaptation.md`
- `deep-course/references/lesson-quality.md` (new)
- `deep-course/assets/lesson-template/lesson.html`
- `deep-course/scripts/lesson_quality.py` (new)
- `deep-course/scripts/course_state.py`
- lesson-quality, lifecycle, template, package, and forward-evaluation tests
- `README.md`

## Acceptance criteria

The redesign is complete when:

1. The current shallow 35-minute sample deterministically fails the new gate.
2. A normal lesson cannot become ready without the complete top-down reading
   spine and credible time evidence.
3. `lesson.md` contains the full teaching manuscript and `lesson.html` preserves
   substantially all instructional content.
4. Reading and examples occupy most of a normal lesson; required interaction is
   limited to a few high-value points.
5. Three unseen forward evaluations pass independent content-focused review.
6. Existing learner state remains readable and existing lessons remain valid.
7. The runtime continues to use only the Python standard library.
8. All existing and new tests, the official Skill validator, and diff checks
   pass before the branch is offered for PR.
