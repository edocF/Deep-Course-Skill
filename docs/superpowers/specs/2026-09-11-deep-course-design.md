# Deep Course v1 Design

## Purpose

`deep-course` is an explicitly invoked Codex skill for building and running long-form, adaptive courses. The skill acts as a course director: it coordinates Codex's native research, coding, visualization, image, document, PDF, spreadsheet, and browser capabilities instead of reimplementing them or calling a separate agent framework.

Version 1 supports one learner and one independently stored state directory per course. It is domain-neutral: no finance, programming, or other subject-matter pack is bundled with the skill.

## Invocation and User Experience

The skill is user-invoked with `$deep-course`; implicit model invocation is disabled. After invocation, the learner uses ordinary language. The skill infers one of these operations from the request and course state:

- create a course;
- continue or begin today's lesson;
- submit answers and receive feedback;
- inspect progress or the review queue;
- revise an approved course goal or schedule.

There are no mandatory slash commands or subcommands for the learner to memorize.

New courses default to `courses/<course-slug>/` under the active workspace. The learner may name another location. User course data is never stored inside the installed skill.

## Architecture

### Director layer

`SKILL.md` contains the shared lifecycle, routing conditions, safety boundaries, and completion criteria. It stays concise and loads only the reference needed for the current operation.

### Teaching-strategy layer

Focused files under `references/` define:

- onboarding and adaptive diagnostic behavior;
- curriculum and knowledge-dependency design;
- lesson composition and multimodal selection;
- research and source-quality policy;
- assessment, mastery evidence, and spaced review;
- artifact and state contracts.

These references contain process guidance, not subject knowledge. Domain research created for a course lives with that course.

### Deterministic state layer

A Python-standard-library command-line program owns state initialization, validation, atomic writes, attempt recording, and review scheduling. It does not research, author lessons, grade open-ended work, or call a model. Codex supplies pedagogical judgments as validated input; the program protects storage integrity.

The CLI exposes machine-readable JSON output and nonzero exit codes for invalid operations. Its public operations are:

- initialize a course state directory;
- validate the complete course state;
- inspect the next actionable lesson and due reviews;
- record a lesson artifact manifest;
- append an assessment attempt;
- apply a validated mastery update;
- propose the next session inputs.

## Course Lifecycle

### 1. Onboarding

Codex conducts a short interview covering the learner's goal, prior background, available time, constraints, preferred language, and desired application context. It then runs a small adaptive diagnostic whose next question depends on prior responses. A learner may explicitly skip the diagnostic, in which case the course starts from a conservative assumed level and records that the baseline has low confidence.

### 2. Curriculum architecture

Codex performs broad domain research, identifies authoritative source classes, defines outcomes, builds a prerequisite graph, and proposes a stable sequence of modules. Only the course skeleton is generated at this stage; future daily lessons are not prewritten.

The learner approves the course goal and backbone before normal lessons begin. Core outcomes remain stable afterward. Codex may reorder lessons, change pacing, or insert reinforcement and challenge lessons. A change to the approved goal, module backbone, or expected duration requires an explanation and learner approval.

### 3. Session planning

Before each lesson, Codex reads the learner profile, curriculum, current mastery evidence, due reviews, recent attempts, and unresolved misconceptions. It performs focused research for the lesson and creates a session plan based on learning value rather than a word count.

Supported session depths are:

- light: approximately 15 minutes;
- normal: approximately 30–45 minutes and the default;
- deep: approximately 60–90 minutes.

The time budget is allocated across retrieval, new concepts, visual or data exploration, a grounded example, problem solving, and final recall. Exact proportions remain adaptive.

### 4. Lesson production

Every lesson produces these core files:

- `lesson.html` as the primary learning experience;
- `lesson.md` as the portable narrative version;
- `exercises.md`;
- `answers.md`, with solutions separated from the normal learning path;
- `sources.md`;
- `state.json` describing the lesson contract and completion state.

Charts, diagrams, generated images, datasets, spreadsheets, PDFs, notebooks, or runnable experiments are created only when they materially improve the learning objective.

The default HTML is self-contained and works without a build step. It may use local companion assets and native SVG or Canvas. When a topic genuinely requires a complex simulation, the lesson may include a separate local experiment project with explicit launch instructions. The core lesson remains understandable when that optional experiment is unavailable.

### 5. Practice and feedback

The HTML lesson supports objective questions and immediate explanatory feedback. It exports a versioned JSON answer record rather than writing authoritative course state directly.

The learner gives the record or equivalent answers to Codex. Codex grades open responses against explicit rubrics, diagnoses misconceptions, distinguishes slips from conceptual gaps, gives actionable feedback, and proposes mastery evidence. The state CLI validates and records that evidence, appends the immutable attempt, and updates the review schedule.

### 6. Adaptation

Adaptation is driven by knowledge-level evidence and spaced review. Each knowledge node tracks:

- mastery estimate and confidence;
- evidence count and evidence recency;
- error or misconception tags;
- last practiced time and next review time;
- prerequisite relationships;
- status such as unseen, learning, reviewing, or mastered.

One answer never establishes durable mastery. The scheduling algorithm is deterministic and simple in v1: successful retrieval expands the interval, partial performance keeps it short, and a demonstrated conceptual gap resets it to relearning. Codex determines the semantic quality of evidence; the script applies the documented schedule consistently.

## Research and Source Policy

Research is layered:

- course creation uses broad research to design the domain map and source strategy;
- each lesson uses focused research for the current concepts and examples;
- time-sensitive facts, real-world data, case studies, and contested claims require traceable sources and appropriate cross-checking;
- stable explanations do not receive decorative citations.

Primary and authoritative sources are preferred. Sources record title, publisher or author, URL or local identifier, access date when relevant, and which lesson claims or data they support. The course records uncertainty and source disagreement instead of silently choosing a convenient claim.

## Multimodal Decision Policy

The director chooses artifacts by the structure of the learning problem:

- relationships, flows, systems, or spatial structures favor diagrams;
- quantities, functions, change over time, comparison, or uncertainty favor charts and tables;
- parameter exploration favors spreadsheets, notebooks, or interactive controls;
- procedures and computational reasoning favor runnable code;
- authentic application favors sourced cases and real datasets;
- visual recognition or concrete scenes may justify generated or sourced images.

An artifact must support a stated learning objective and be referenced by an activity. Decorative artifacts are omitted.

## State and File Contracts

```text
courses/<course-slug>/
|-- course.json
|-- learner-profile.json
|-- curriculum.json
|-- syllabus.md
|-- knowledge-map.md
|-- progress.json
|-- attempts.jsonl
|-- research/
`-- lessons/
    `-- <sequence>-<lesson-slug>/
        |-- lesson.html
        |-- lesson.md
        |-- exercises.md
        |-- answers.md
        |-- sources.md
        |-- state.json
        |-- assets/
        `-- data/
```

All JSON documents carry a schema version. Identifiers are stable and independent of display titles. Timestamps use ISO 8601 with an explicit offset. Attempts are append-only JSON Lines. Mutable JSON files are written atomically through a temporary sibling and replace operation. Unknown schema versions fail validation without being rewritten.

`curriculum.json` owns learning outcomes, modules, knowledge nodes, prerequisites, and the stable backbone. `progress.json` owns current evidence summaries and review timing. `state.json` owns lesson-local status and its artifact manifest. Derived summaries such as the next-session proposal are computed rather than duplicated across files.

## Failure and Recovery

- Missing or malformed state stops mutation and reports the exact file and field.
- An interrupted write leaves the last valid state intact.
- A partially generated lesson remains marked `draft`; it cannot be recorded as delivered until all core artifacts validate.
- Missing optional tooling causes a simpler artifact choice, not a fabricated result.
- Unavailable research access is disclosed; claims requiring current verification are deferred or clearly marked.
- Imported answer records are treated as untrusted input and cannot name arbitrary output paths.
- Existing learner files are never overwritten during initialization without explicit approval.

## Skill Package

```text
deep-course/
|-- SKILL.md
|-- agents/
|   `-- openai.yaml
|-- references/
|   |-- onboarding-and-curriculum.md
|   |-- lesson-design.md
|   |-- research-and-sources.md
|   |-- assessment-and-adaptation.md
|   `-- state-contracts.md
|-- scripts/
|   `-- course_state.py
|-- assets/
|   `-- lesson-template/
`-- tests/
    `-- test_course_state.py
```

The HTML template supplies accessible structure, navigation, response export, and print styling. It does not impose a generic visual theme on every subject. Empty placeholder directories and unused templates are excluded.

## Verification Strategy

Development follows test-first behavior for both the state program and the skill instructions.

State tests cover initialization, schema validation, path containment, atomic-update failure, append-only attempts, mastery transitions, review intervals, imported response validation, and draft-to-delivered lesson transitions.

Skill behavior is evaluated first without the new skill to capture baseline failures, then with the skill against realistic scenarios:

1. a broad new course request that tempts the model to generate every lesson at once;
2. a quantitative lesson that should create an explanatory chart and editable data artifact;
3. a conceptual lesson where extra media would be decorative;
4. weak learner performance that should insert reinforcement without silently rewriting the approved curriculum;
5. unsupported current claims when research access is unavailable;
6. malformed or malicious answer-record paths.

Acceptance requires valid package metadata, passing script tests, a successful state round trip, and one generated sample course outside the skill tree whose lesson artifacts are visually inspected. The sample is disposable test output and is not bundled as domain content.

## Non-Goals for v1

- hosted accounts, authentication, synchronization, or multi-user support;
- a database or cloud backend;
- a custom agent framework or direct LLM API integration;
- a bundled subject curriculum;
- automatic modification of authoritative state from browser JavaScript;
- generating every possible artifact for every lesson;
- pre-generating an entire long course before learner evidence exists.
