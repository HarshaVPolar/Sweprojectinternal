---
title: google-cloud
type: area
created: 2026-11-25
tags: [google-cloud, oauth, setup]
requirements: [BR-5, CON-2, SEC-1]
sources: []
status: distilled
---
# Summary

The team uses exactly ONE Google Cloud project (BR-5, CON-2). Creating extra projects to obtain more quota is forbidden.

# Key facts

- YouTube Data API v3 is enabled in that project.
- OAuth consent screen: External, Testing mode. All team members and the instructor are Test users.
- Scopes configured: youtube.readonly and youtube.
- OAuth client type: Desktop app. The client JSON and the API key are stored in a password manager, never in the repository.
- Refresh tokens expire after 7 days in Testing mode; re-authorise before demos.

# Implications for design

Secrets stay outside the repository (SEC-3). Tokens use the OS keyring (ADR-005).

# Related
