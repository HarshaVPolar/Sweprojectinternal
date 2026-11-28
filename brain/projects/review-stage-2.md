---
title: review-stage-2
type: review
created: 2026-11-28
tags: [review, stage-2]
requirements: [SB-2]
sources: []
status: distilled
---

# Summary

Stage 2 (Design) is complete when this note is merged and the tag stage-2 exists. Delivered: the build contract; ADR-001 to ADR-005; the architecture, schema, provider, scoring, security and tool catalogue documents and the Mermaid diagram sources; the elicitation spike and its result; the walking skeleton (configuration, errors and models, clock, provider interface with transport, mapping, API-backed and fixture providers, duration parser, and an MCP server that answers get_quota_status); the fixture recorder, sanitiser, synthetic and recorded fixtures with a scanner; local-check version 1; and the completed task briefs B01 to B33.

# Exit criteria check

| Criterion | Result |
|---|---|
| Design review held | yes |
| local-check runs on all three machines | 3 of 3 machines |
| ADR-001 to ADR-005 merged, each citing brain notes | yes |
| Elicitation spike result recorded | yes, see [[elicitation-spike]] |
| Fixture provider replays real recorded data | yes (tests/integration/test_real_fixtures.py) |
| Task briefs complete for B01 to B33 | yes |

# Design decisions added during Stage 2

- All YouTube access shares one request-building and mapping path: ApiBackedProvider over an ApiTransport (providers/transport.py and providers/api_provider.py).
- The fixture provider simulates writes in memory with failure injection; fixture fallbacks for calls that were not recorded are specified in docs/design/provider.md section 8 and built by the first feature that needs them.
- Playlist confirmation is asynchronous because MCP elicitation is asynchronous; propose_playlist does not send the language to the search API (it filters locally) so that fixture replay works.
- Tools may import only domain.sanitiser from the domain package (the first tool item adds the pyproject exception); infra/oauth.py is the only module besides providers/live.py that performs HTTP.
- live-smoke.yml belongs to build item B21 and release.yml to the release task.
- The brain-query skill was not used to draft the ADRs; they were written from fixed prompts and cite distilled notes.

# What worked

Stage 2 established a consistent architecture and build contract, completed all five ADRs, design documents, diagrams and 33 task briefs, and passed the required validation checks and CI workflows.

# What did not work

Some prompt assumptions did not match the repository exactly, particularly the T22 contract heading. The elicitation spike also exposed differences between MCP client support, and some manual decline behavior could not be independently tested.

# What to change

From Stage 3 onward, verify exact repository content before generating prompts, resolve source ambiguities during preflight, test MCP client compatibility earlier, and keep implementation, automated testing and manual verification clearly separated.

# Related

- [[review-stage-1]]
- [[elicitation-spike]]
- [[schedule]]
- [[team-workflow]]
