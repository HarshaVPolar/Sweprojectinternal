---
title: oauth-testing-mode
type: inbox
created: 2026-11-26
tags: [oauth, security, google]
requirements: [SEC-1, SEC-2, SEC-3, CON-4, CON-10, UI-7]
sources: [https://developers.google.com/identity/protocols/oauth2/native-app, https://developers.google.com/identity/protocols/oauth2#expiration]
status: raw
---

# Summary

While the OAuth consent screen is in Testing mode, only listed test users can authorise the app and refresh tokens expire after 7 days. Desktop applications use the authorisation code flow with PKCE and a loopback redirect. The server asks for the smallest scope that does the job.

# Key facts

- Consent screen: user type External, publishing status Testing. Every team member and the instructor must be added as a test user.
- Refresh tokens issued in Testing mode expire after 7 days (CON-4). After expiry Google answers invalid_grant and the user must authorise again.
- Flow for installed applications: authorisation code with PKCE (a code verifier and its challenge), a random state value that must be checked on return, and a redirect to http://127.0.0.1 on a random free port.
- Scopes: https://www.googleapis.com/auth/youtube.readonly for reading; https://www.googleapis.com/auth/youtube (manage account) only when a playlist is created (SEC-1, CON-10).
- Incremental authorisation: request the extra scope only when the write step is about to run.
- Tokens must never be logged, committed or placed in fixtures (SEC-2, SEC-3).

# Implications for design

- On a 401 answer or invalid_grant: make one refresh attempt, then return REAUTH_REQUIRED and start a new consent flow on the next authorised call.
- Record the issue date of the token and warn on day 6. Re-authorise every demo account the day before the demo.
- Store refresh tokens in the operating system keyring, with an encrypted-file fallback (ADR-005).
- The scheduled CI live test uses only an API key, because user tokens would expire.

# Related

- (links added during brain-refine)
