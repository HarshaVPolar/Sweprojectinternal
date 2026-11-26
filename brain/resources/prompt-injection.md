---
title: prompt-injection
type: resource
created: 2026-11-26
tags: [security, prompt-injection, mcp]
requirements: [SEC-5, SEC-6, BR-1, SK-3, TQ-SEC]
sources: [https://owasp.org/www-project-top-10-for-large-language-model-applications/, SRS v1.0 SEC-5 and SEC-6]
status: distilled
---

# Summary

Prompt injection is text that tries to make an AI model follow an attacker's instructions instead of the user's. In this project the risk is indirect: titles, descriptions, tags and channel names written by strangers are returned to the model. A video description must never be able to cause a write to the user's account.

# Key facts

- Direct injection: the attacker talks to the model. Indirect injection: instructions are hidden in data the model reads, for example a video description that says to ignore instructions and create a playlist.
- Attack surface here: every string that originates from YouTube, such as titles, descriptions, tags, channel names and playlist names (SEC-6).
- Defences: sanitise text (remove control characters and markup, limit length); delimit untrusted text with marker lines and state in tool descriptions that it is data; least privilege (the only write is creating a new playlist); tool annotations are hints only; a server-side human-only approval gate that the model cannot satisfy (SEC-5, ADR-004); fail closed.
- The delimiter used by this project, shown in a code block so that it is not read as a link:

```
[[UNTRUSTED_YOUTUBE_TEXT]]
text that came from YouTube
[[/UNTRUSTED_YOUTUBE_TEXT]]
```

- Test corpus of at least 20 payloads in these families: instruction override, fake tool-call syntax, HTML or markdown markup, forged delimiters, zero-width and hidden unicode, role impersonation, encoded text such as base64.

# Implications for design

- Sanitise and delimit only at the tool boundary; services and domain code keep raw text.
- The skill still asks the user in chat (SK-3), and the server requires a separate human approval (ADR-004). Metadata can change neither.
- Tests must show that no payload in the corpus leads to a write, and a skill evaluation covers an injection attempt.

# Related

- [[mcp-overview]]
- [[agent-skills-format]]
