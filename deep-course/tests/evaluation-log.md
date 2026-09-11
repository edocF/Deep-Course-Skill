# No-Skill Baseline Evaluation Log

## Evaluation metadata

- Date: 2026-09-11
- Evaluator: fresh no-Skill evaluator recorded in .superpowers/sdd/2026-09-11-deep-course-v1/task-1-baseline-raw.md
- Independent assessment: .superpowers/sdd/2026-09-11-deep-course-v1/task-1-baseline-assessment.md
- Environment: empty temporary workspace with no deep-course Skill, source pack, or prior course assets
- Overall verdict: **RED**. Scenario A fails the learner-approval gate and Scenario C fails delayed retrieval; one failure is sufficient for a red baseline.

## Scenario A: Create a twelve-week course under time pressure

- Scenario path: deep-course/tests/scenarios/create-long-course.md
- Artifacts produced: course charter; twelve-week syllabus table; facilitator-pack outline; one Week 7 facilitation script; four-step technical review gate.
- Named but not produced: weekly slide decks, workbooks, photo/case files, answer keys, rubrics, templates, datasets, diagrams, checklists, and capstone pack.

| ID | Observable decision | Result | Observed evidence |
|---|---|---|---|
| A1 | Create a proposed backbone before full lesson and facilitator content. | PASS | The evaluator produced a course charter and twelve-week syllabus, then stopped at a facilitator-pack outline and one sample script rather than generating all named downstream materials. |
| A2 | Ask the learner to approve the backbone before expanding it into lessons. | FAIL | The response presented a package as ready for steering-committee review and supplied some downstream facilitation content, but never asked the learner to approve the backbone. Its release gates require technical owners, HSE, operations, and training owners rather than learner approval. |
| A3 | Avoid presenting unsupported standards, intervals, thresholds, and safety details as facts. | PASS | The response reserved these as controlled fields, named authoritative sources, and refused to fabricate values. |
| A4 | Make sequence, objectives, assessments, and unresolved evidence needs inspectable before downstream production. | PASS | The twelve-row table exposes week, objective, lessons, exercise, assessment, and facilitator material; the charter also lists the controlled source pack and visible approval placeholders. |

Short verbatim rationalizations:

- “Inventing those values could send supervisors into unsafe work or create an invalid maintenance decision.”
- “The proposed package is deliberately complete in instructional structure”
- “It can support a steering-committee review within 45 minutes”

## Scenario B: Build a quantitative bond-yield lesson

- Scenario path: deep-course/tests/scenarios/quantitative-lesson.md
- Artifacts produced: self-contained 35–45 minute lesson; explicit two-period pricing/YTM model; worked example with 6% and 6.10% trials and algebraic check; instructor talk track; four guided-practice items with answers; exit ticket with model response.

| ID | Observable decision | Result | Observed evidence |
|---|---|---|---|
| B1 | Produce an inspectable numeric model with inputs, cash flows, formula, method, and result. | PASS | The response identifies face value, coupon, term, price, both cash flows, the pricing equation, trial-yield method, algebraic check, and an approximate 6.10% YTM. |
| B2 | Use the supplied bond consistently and expose diagnostic intermediate values. | PASS | The 6% trial shows 47.17 + 934.62 = 981.79; the 6.10% trial shows 47.13 + 932.82 = 979.95; the positive-root check gives about 6.097%. |
| B3 | Include learner activity that requires quantitative action or explanation. | PASS | Guided practice asks learners to classify the bond, calculate price at 5%, predict price at 7%, estimate YTM at a new price, and explain the result in an exit ticket. |
| B4 | Provide observable responses and a feedback or checking mechanism. | PASS | Every practice item has an answer or worked check, and the exit ticket has a model response. |
| B5 | Connect price and yield through the numeric model. | PASS | The response uses the price calculated at 6% to infer that the market yield must be higher, then checks 6.10%; the 7% exercise applies the same relationship. |

Short verbatim rationalizations:

- “All required numerical inputs are supplied, and this is a low-risk educational calculation.”
- “those assumptions are named rather than hidden.”

## Scenario C: Adapt after weak present-value answers

- Scenario path: deep-course/tests/scenarios/adaptive-remediation.md
- Artifacts produced: 20–25 minute corrective micro-lesson; concrete counterexample; forward-versus-backward operations table; immediate retrieval practice with answers; two-period extension; three-item mastery gate; conditional Part 2 opening; facilitator notes.

| ID | Observable decision | Result | Observed evidence |
|---|---|---|---|
| C1 | Diagnose the specific misconception from the answer evidence. | PASS | The response identifies reversal of discounting and failure to distinguish multiplication by a growth factor from division by a discount factor. |
| C2 | Create targeted remediation requiring reasoning and application. | PASS | The micro-lesson uses a grow-to-100 counterexample, contrasts both operations, and asks the learner to calculate future value, present value, and direction of value. |
| C3 | Schedule a later retrieval opportunity for the corrected concept. | FAIL | All labeled retrieval practice occurs immediately inside the same 20–25 minute micro-lesson. No later, spaced retrieval event is scheduled. |
| C4 | Preserve the approved backbone while adapting within it. | PASS | The response repeats the three parts unchanged, contains remediation inside Part 1, and reserves bond pricing and duration for Parts 2 and 3. |
| C5 | Condition progression on evidence that the learner can apply present value. | PASS | The mastery gate requires three correct responses and a correct directional explanation before advancing; otherwise it calls for another example and timeline. |

Short verbatim rationalizations:

- “The learner’s errors are prerequisite errors”
- “Do not advance them to Part 2 yet.”
- “The response adds an adaptive remediation loop within approved Part 1”

## Coverage reconciliation

All fourteen observable decisions from the three scenario files appear once in the tables above: A1–A4, B1–B5, and C1–C5.

The independent assessment is also RED and explicitly identifies C3. For Scenario A, that assessment substituted an expert/release-gate decision for the scenario’s actual learner-approval decision. This log follows the source scenario: technical sign-off is not learner approval, so A2 is recorded as an additional baseline failure.
