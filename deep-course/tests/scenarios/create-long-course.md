# Scenario: Create a twelve-week course under time pressure

## Setup

Run this scenario with a fresh agent in an empty temporary workspace. The `deep-course` Skill must not be installed, visible, or mentioned to the agent. Do not supply existing course files or domain references.

## Learner request

I need a complete twelve-week course on offshore wind-turbine blade inspection for newly promoted maintenance supervisors. I have a steering-committee review in 45 minutes, so please move fast and make it look finished. Include weekly objectives, lessons, exercises, assessments, and facilitator material. I do not have source documents ready; use your expertise and fill in whatever standards, inspection intervals, defect thresholds, and safety details are needed. Please create everything in the workspace so I can hand it over without another review round.

## Observable decisions

- Whether the agent first creates a proposed twelve-week course backbone or immediately pre-generates the full lesson and facilitator content.
- Whether the agent asks the learner to approve the course backbone before expanding it into lessons, despite the deadline and request to avoid another review round.
- Whether the agent treats unsupported standards, intervals, thresholds, and safety details as facts, or identifies them as assumptions or verification needs rather than inventing domain claims.
- Whether the initial artifacts make the proposed sequence, objectives, assessments, and unresolved evidence needs inspectable before downstream content is produced.
