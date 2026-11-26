---
title: agent-skills-format
type: resource
created: 2026-11-26
tags: [skills, agents, format]
requirements: [SK-1, SK-13, SK-14, SK-15, CON-11]
sources: [https://agentskills.io, SRS section 4.6]
status: distilled
---

# Summary

An Agent Skill is a folder with a file called SKILL.md that teaches an AI agent one workflow. The agent first sees only the name and description, and reads the rest when the skill is relevant.

# Key facts

- Required: a folder skills/NAME/ containing SKILL.md that starts with a frontmatter block between lines of three dashes.
- Frontmatter fields name and description are required. name must equal the folder name, use only lower-case letters, digits and single hyphens, and be at most 64 characters. description must say what the skill does and when to use it, in at most 1024 characters.
- The body is Markdown instructions. Optional folders: scripts for code the agent can run, references for longer documents, assets for other files.
- Progressive disclosure: only name and description are loaded at start; the body is loaded when the skill is used; referenced files are read only when needed.
- This project validates every skill in CI with scripts/validate_skills.py. It checks the frontmatter, the name rule and the description length. A missing SKILL.md is a warning, or an error when STRICT_SKILLS=1.
- Skills in this project: video-to-playlist and local-check (product skills), and brain-ingest, brain-refine and brain-query (second-brain skills).

# Implications for design

- Write description lines as a single line without a colon followed by a space, so every YAML reader accepts them.
- Every skill cites at least one distilled brain note (SB-3, SK-7).
- A skill instruction is a promise the agent may follow imperfectly, so safety rules such as the confirmation gate must also be enforced by the server.

# Related

- [[mcp-overview]]
