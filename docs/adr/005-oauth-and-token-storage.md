# ADR-005: OAuth flow and token storage

Status: accepted
Date: 2026-11-28

## Context

The server acts for one authorised user (SRS 3.3.3). While the consent screen is in Testing mode, refresh tokens expire after 7 days (CON-4). Scopes must be the minimum needed (SEC-1, CON-10) and tokens must never reach the repository, logs or fixtures (SEC-2, SEC-3). The server is a desktop-style application.

## Decision

- Authorisation code flow with PKCE (S256), a random state value that is checked on return, and a redirect to http://127.0.0.1 on a random free port.
- Incremental scopes: youtube.readonly for every read; the youtube scope is requested only when a playlist is about to be created. The requested scopes are shown to the user.
- On a 401 answer or invalid_grant the server makes one refresh attempt and then returns REAUTH_REQUIRED and starts a new consent flow on the next authorised call. The issue date of the token is recorded and a warning is given on day 6.
- The refresh token is stored in the operating system keyring (library keyring). The table oauth_token keeps metadata only.
- Fallback when no keyring is available: an encrypted file using Fernet, with a key derived by scrypt from a passphrase taken from the environment variable YTMCP_TOKEN_PASSPHRASE or an interactive prompt. The passphrase is never stored. Files get mode 0600 on Linux and macOS.
- The scheduled CI live test uses only an API key, because user tokens would expire and must never be in CI.

## Consequences

- While in Testing mode every user must authorise again at least every 7 days, and every demonstration account is re-authorised the day before the demo.
- The encrypted-file fallback depends on the user remembering a passphrase.
- On Windows the file permissions rely on the user profile ACL and are not tested by mode bits.
- Only infra/token_store.py touches token secrets.

## Brain notes cited

- [[oauth-testing-mode]]
- [[google-cloud]]
