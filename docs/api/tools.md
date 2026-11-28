# MCP tool, resource and error catalogue

Version 1.0 (Stage 2). Matches docs/design/build-contract.md sections 6 and 9; the build contract wins on any conflict. Items marked (added) were not fixed there.

## 1. Conventions

- Every tool returns the result envelope of section 2. Integers named total_duration and max_video_duration are seconds.
- Parameters are validated by ytmcp.domain.input_validator before any API call. A failed validation gives INVALID_ID or INVALID_PARAMETER. Unknown parameters are rejected (additionalProperties false). Parameters not listed under required are optional.
- Every string that comes from YouTube is passed through sanitise_text and then wrap_untrusted by the tool or resource (build contract section 9).
- Annotations are hints for clients. The approval gate is the real control for writes (docs/adr/004-human-approval-gate.md).
- (added) published_after is a date YYYY-MM-DD and is used as a local filter on the publication date, not as a search parameter.
- (added) granularity of analyse_engagement defaults to month.

## 2. Result envelope

```json
{
  "type": "object",
  "properties": {
    "ok": { "type": "boolean" },
    "summary": { "type": "string" },
    "data": { "type": "object" },
    "quota": {
      "type": "object",
      "properties": {
        "spent": { "type": "integer", "minimum": 0 },
        "remaining": { "type": "integer" },
        "estimate": { "type": ["integer", "null"] }
      },
      "required": ["spent", "remaining", "estimate"],
      "additionalProperties": false
    },
    "notices": { "type": "array", "items": { "type": "string" } },
    "error": {
      "oneOf": [
        { "type": "null" },
        {
          "type": "object",
          "properties": {
            "code": { "type": "string" },
            "message": { "type": "string" },
            "next_step": { "type": "string" }
          },
          "required": ["code", "message", "next_step"],
          "additionalProperties": false
        }
      ]
    }
  },
  "required": ["ok", "summary", "data", "quota", "notices", "error"],
  "additionalProperties": false
}
```

Rules: ok true means error is null; ok false means error is an object. quota.spent is the units spent by this call, quota.remaining the units left today under the global budget, quota.estimate the estimate made before the call (or null).

## 3. Tools

### 3.1 find_similar_videos

Annotations: readOnlyHint true, destructiveHint false, idempotentHint true, openWorldHint true. Cold quota about 102 units.

```json
{
  "type": "object",
  "properties": {
    "video": { "type": "string", "minLength": 1, "maxLength": 2048 },
    "limit": { "type": "integer", "minimum": 1, "maximum": 50, "default": 10 },
    "max_duration_s": { "type": "integer", "minimum": 1 },
    "language": { "type": "string", "pattern": "^[a-z]{2}$" },
    "published_after": { "type": "string", "format": "date" },
    "exclude_channels": {
      "type": "array",
      "items": { "type": "string", "pattern": "^UC[A-Za-z0-9_-]{22}$" },
      "maxItems": 50,
      "uniqueItems": true
    }
  },
  "required": ["video"],
  "additionalProperties": false
}
```

data: results, a list of {video_id, title, channel, duration_mmss, url, score, components}, where components has the keys text, tag, category, duration, language, each a number or null. notices says when tags are missing and weights were renormalised. Errors: INVALID_ID, INVALID_PARAMETER, NOT_FOUND_OR_PRIVATE, QUOTA_BUDGET_EXCEEDED, QUOTA_EXHAUSTED, RATE_LIMITED, UPSTREAM_ERROR.

### 3.2 find_similar_channels

Annotations: readOnlyHint true, destructiveHint false, idempotentHint true, openWorldHint true. Cold quota about 210 units, at most 350.

```json
{
  "type": "object",
  "properties": {
    "channel": { "type": "string", "minLength": 1, "maxLength": 2048 },
    "limit": { "type": "integer", "minimum": 1, "maximum": 30, "default": 10 },
    "exclude_subscribed": { "type": "boolean", "default": false }
  },
  "required": ["channel"],
  "additionalProperties": false
}
```

data: results, a list of {channel_id, title, score, shared_topics, example_videos (at most 3 of {video_id, title, url})}. Errors: INVALID_ID, NOT_FOUND_OR_PRIVATE, AUTH_REQUIRED and REAUTH_REQUIRED (only when exclude_subscribed is true), QUOTA_BUDGET_EXCEEDED, QUOTA_EXHAUSTED, RATE_LIMITED, UPSTREAM_ERROR.

### 3.3 recommend_videos

Annotations: readOnlyHint true, destructiveHint false, idempotentHint true, openWorldHint true. Quota about 210 units, at most 250.

```json
{
  "type": "object",
  "properties": {
    "limit": { "type": "integer", "minimum": 1, "maximum": 50, "default": 10 },
    "sources": {
      "type": "array",
      "items": { "type": "string", "enum": ["likes", "playlists", "subscriptions"] },
      "minItems": 1,
      "uniqueItems": true,
      "default": ["likes", "playlists", "subscriptions"]
    },
    "max_duration_s": { "type": "integer", "minimum": 1 },
    "language": { "type": "string", "pattern": "^[a-z]{2}$" },
    "topic": { "type": "string", "minLength": 1, "maxLength": 200 }
  },
  "additionalProperties": false
}
```

data: results, a list of {video_id, title, channel, score, because (at most 3 titles)}. Errors: AUTH_REQUIRED, REAUTH_REQUIRED, EMPTY_PROFILE, QUOTA_BUDGET_EXCEEDED, QUOTA_EXHAUSTED, RATE_LIMITED, UPSTREAM_ERROR.

### 3.4 analyse_engagement

Annotations: readOnlyHint true, destructiveHint false, idempotentHint true, openWorldHint true. Quota 10 to 30 units.

```json
{
  "type": "object",
  "properties": {
    "period": { "type": "string", "enum": ["last_30d", "last_90d", "last_365d", "all"], "default": "last_90d" },
    "compare_to": { "type": "string", "enum": ["previous_period", "none"], "default": "previous_period" },
    "dimensions": {
      "type": "array",
      "items": { "type": "string", "enum": ["channels", "categories", "trend", "duration"] },
      "minItems": 1,
      "uniqueItems": true,
      "default": ["channels", "categories", "trend", "duration"]
    },
    "top_k": { "type": "integer", "minimum": 1, "maximum": 50, "default": 10 },
    "granularity": { "type": "string", "enum": ["month", "week"], "default": "month" }
  },
  "additionalProperties": false
}
```

data: statistics for each requested dimension, comparison (absolute and relative change per metric), timestamp_used (which timestamp each source uses), limitations (no watch history; liked videos have no like timestamps) and narrative. An empty period returns zero values and a notice, not an error. Errors: AUTH_REQUIRED, REAUTH_REQUIRED, QUOTA_BUDGET_EXCEEDED, QUOTA_EXHAUSTED, RATE_LIMITED, UPSTREAM_ERROR.

### 3.5 propose_playlist

Annotations: readOnlyHint true (no YouTube write; the proposal is stored locally), destructiveHint false, idempotentHint false (each call stores a new proposal), openWorldHint true. Quota about 203 units.

```json
{
  "type": "object",
  "properties": {
    "topic": { "type": "string", "minLength": 1, "maxLength": 200 },
    "total_duration": { "type": "integer", "minimum": 300, "maximum": 86400 },
    "max_video_duration": { "type": "integer", "minimum": 60, "maximum": 86400 },
    "language": { "type": "string", "pattern": "^[a-z]{2}$" },
    "title": { "type": "string", "minLength": 1, "maxLength": 150 },
    "visibility": { "type": "string", "enum": ["private", "unlisted", "public"], "default": "private" }
  },
  "required": ["topic", "total_duration", "max_video_duration", "language"],
  "additionalProperties": false
}
```

max_video_duration must not exceed total_duration (checked by the server). Set visibility only when the user said so. data: proposal_id, state ("PROPOSED"), items (a list of {position, video_id, title, channel, duration_mmss, score}), total_s, feasible, constraint_report (a list of sentences, one per constraint, saying whether it is met), shortfall_message (string or null), expires_at (ISO 8601), estimated_confirm_cost (integer), proposal_text (the numbered list and the confirmation prompt). No secret, token or code is ever returned. Errors: INVALID_PARAMETER, AUTH_REQUIRED, REAUTH_REQUIRED, CHANNEL_REQUIRED, QUOTA_BUDGET_EXCEEDED, QUOTA_EXHAUSTED, RATE_LIMITED, UPSTREAM_ERROR.

### 3.6 confirm_playlist

Annotations: readOnlyHint false, destructiveHint false, idempotentHint false, openWorldHint true. Quota 1 + 50 + 50 per item (resume: 1 + 50 per missing item).

```json
{
  "type": "object",
  "properties": {
    "proposal_id": {
      "type": "string",
      "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
    }
  },
  "required": ["proposal_id"],
  "additionalProperties": false
}
```

data: state (CREATED or PARTIALLY_CREATED), playlist_url (string or null), items_added, items_missing. When the human approval is still pending the result is an error with code APPROVAL_PENDING and no address or code in any field. Errors: PROPOSAL_INVALID (unknown, expired, altered, used or declined), APPROVAL_PENDING, CHANNEL_REQUIRED, AUTH_REQUIRED, REAUTH_REQUIRED, QUOTA_BUDGET_EXCEEDED, QUOTA_EXHAUSTED, RATE_LIMITED, UPSTREAM_ERROR (with the partial progress in notices).

### 3.7 summarise_video

Annotations: readOnlyHint true, destructiveHint false, idempotentHint true, openWorldHint true. Quota 1 unit.

```json
{
  "type": "object",
  "properties": {
    "video": { "type": "string", "minLength": 1, "maxLength": 2048 }
  },
  "required": ["video"],
  "additionalProperties": false
}
```

data: video_id, title, channel, duration_mmss, published (date), tags (at most 10), description_excerpt (at most 300 characters), chapters (a list of {start_s, title}, possibly empty) and basis, always the text "metadata". Errors: INVALID_ID, NOT_FOUND_OR_PRIVATE, QUOTA_BUDGET_EXCEEDED, QUOTA_EXHAUSTED, RATE_LIMITED, UPSTREAM_ERROR.

### 3.8 get_quota_status

Annotations: readOnlyHint true, destructiveHint false, idempotentHint true, openWorldHint false. Quota 0 units.

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

data: used_today, remaining, reserve, machine_remaining, reset_at (ISO 8601 UTC), exhausted. Errors: none expected.

### 3.9 get_auth_status

Annotations: readOnlyHint true, destructiveHint false, idempotentHint true, openWorldHint true. Quota about 1 unit (only when a token exists).

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

data: has_token, scopes (a list), expires_at (ISO 8601 or null), channel_present (true, false or null when unknown). No token value is ever returned. Missing authorisation is reported with has_token false, not as an error.

## 4. Resources

| URI | Content | Notes |
|---|---|---|
| youtube://quota/status | the data of get_quota_status as JSON | read-only |
| youtube://video/{id} | cached normalised video metadata as JSON | untrusted text is delimited; if the video is not cached the resource says so and makes no API call |
| youtube://playlist/proposal/{id} | state, expiry, items and totals of a stored proposal | never contains approval data |
| youtube://auth/status | the data of get_auth_status | no token values |

## 5. Error codes

| Code | Retryable | Default message | Default next step |
|---|---|---|---|
| INVALID_ID | false | The video, channel or playlist identifier is not valid. | Check the URL or ID format. |
| INVALID_PARAMETER | false | A parameter is missing or out of range. | Check the parameter values against the tool description. |
| NOT_FOUND_OR_PRIVATE | false | The item does not exist or is private. | Use a public video or channel. |
| AUTH_REQUIRED | true | Authorisation is required. | Authorise this app in the browser window, then retry. |
| REAUTH_REQUIRED | true | The authorisation has expired or was revoked. | Re-authorise in the browser, then retry. |
| CHANNEL_REQUIRED | true | This Google account has no YouTube channel. | Create a YouTube channel, then retry. |
| EMPTY_PROFILE | false | There are no likes, subscriptions or playlists to learn from. | Provide a topic or a seed video. |
| QUOTA_BUDGET_EXCEEDED | true | The estimated cost exceeds the remaining quota budget. | Reduce the request or wait until the quota resets. |
| QUOTA_EXHAUSTED | true | The YouTube API quota is used up for today. | Wait until the quota resets (midnight Pacific Time). |
| RATE_LIMITED | true | Too many requests. | Wait a moment, then retry. |
| APPROVAL_PENDING | true | Waiting for the human approval. | Approve in the browser window opened on your computer, then ask me to continue. |
| PROPOSAL_INVALID | false | The proposal is unknown, expired, altered, already used or was declined. | Ask for a new proposal. |
| UPSTREAM_ERROR | true | YouTube or the network failed after retries. | Try again shortly; partial progress is reported if any. |
