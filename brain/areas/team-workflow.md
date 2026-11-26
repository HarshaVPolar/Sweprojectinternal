---
title: team-workflow
type: area
created: 2026-11-26
tags: [workflow, team, process]
requirements: [BR-7, SB-6, SE-5]
sources: [Team decision]
status: distilled
---
# Summary

How the three team members work together. Any member may take any task and review any change. A review is requested manually when a member wants one. The team does not use CODEOWNERS to assign or enforce ownership; the existing CODEOWNERS file remains untouched. The project does not use GitHub branch restrictions, mandatory approvals, milestones, due dates, labels or fixed assignments.

# Key facts

- Ownership: no task or file belongs to a fixed person. Any teammate can pick any build item (the briefs in docs/ai/briefs) and any teammate can review any pull request.
- Reviews: a member asks a teammate for a review manually when it is useful, for example for security-sensitive code such as the approval gate, the token store, the input validator, the sanitiser, the quota guard and the live provider. GitHub enforces no approval count.
- Human responsibility stays: the author is responsible for checking, understanding and being able to explain every AI-generated change before merging it.
- Pull requests are still used for changes to main, because CI (lint, types, layer rules, tests, secret scan, skill and brain validation) runs on them. The coding agent opens the pull request and never merges it. A human merges after CI is green.
- Planning is by stage and by dependency (the Needs line of each brief), not by calendar. The schedule note stays as information and is not a deadline.
- GitHub issues: one per build item or stage task. The title starts with the item ID and the body holds requirements, size estimate, dependencies and acceptance criteria. No labels, milestones or assignees are used.
- Authorship is visible in the git history. Each member authors at least three research notes in Stage 1 (SB-6).

# Implications for design

- Briefs, prompts and issues never name a required author or reviewer.
- A member who starts a build item says so in a comment on its issue, so that two people do not do the same work.
- Prompts for agents never touch CODEOWNERS, branch protection, labels, milestones or assignees.

# Related

- [[schedule]]
- [[quota-policy]]
