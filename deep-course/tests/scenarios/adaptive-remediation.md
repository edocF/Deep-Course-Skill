# Scenario: Adapt after weak present-value answers

## Setup

Run this scenario with a fresh agent in an empty temporary workspace. The `deep-course` Skill must not be installed, visible, or mentioned to the agent. Treat the course backbone below as already reviewed and approved; no other learner history is available.

## Learner request

The approved three-part backbone is: (1) present value and discount factors, (2) bond pricing from discounted cash flows, and (3) duration and interest-rate sensitivity. Do not change that sequence.

After part 1, the learner gave these answers:

1. “$100 received one year from now is worth $100 today because the amount on the check is still $100.”
2. “At a 5% discount rate its present value should be $105, because interest adds 5%.”
3. For the formula `PV = FV / (1 + r)^n`, the learner substituted `100 × 1.05` and said division or multiplication are interchangeable if the rate is small.

Please adapt the course and keep us moving. Prepare whatever should happen next.

## Observable decisions

- Whether the agent diagnoses a specific misconception from the answer evidence, including the reversal of compounding and discounting, rather than labeling performance only as weak or incorrect.
- Whether the agent creates targeted remediation that requires the learner to reason about present versus future value and apply the discount factor, rather than simply repeating the original explanation.
- Whether the agent schedules a later retrieval opportunity for the corrected concept instead of treating one immediate correction as sufficient.
- Whether the agent preserves the approved three-part backbone and makes the adaptation within it, rather than silently reordering, replacing, or expanding the course structure.
- Whether progression to bond pricing is conditioned on observable evidence that the learner can correctly apply the present-value relationship.
