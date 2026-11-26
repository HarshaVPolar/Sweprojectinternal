---
title: iso8601-durations
type: inbox
created: 2026-11-26
tags: [youtube, duration, parsing]
requirements: [FR-5.3, FR-5.4, TQ-1]
sources: [https://developers.google.com/youtube/v3/docs/videos, https://en.wikipedia.org/wiki/ISO_8601#Durations]
status: raw
---

# Summary

YouTube reports the length of a video in the field contentDetails.duration as an ISO 8601 duration string. Playlist building adds up lengths, so the parser must be exact.

# Key facts

- Normal form: PT then optional hours H, minutes M and seconds S, for example PT15M33S. Parts that are zero are left out.
- Examples: PT59S = 59 seconds; PT1M = 60; PT1H2M3S = 3600 + 120 + 3 = 3723; PT0S = 0.
- Very long videos may contain days: P1DT1H = 86400 + 3600 = 90000 seconds.
- Live and upcoming broadcasts are reported with a zero duration such as P0D. They are not normal videos and must be excluded from playlists by the live status filter (FR-5.3).
- Anything else (empty text, lower case, PT with no parts, negative values, unknown letters) is invalid and must raise an error. Never guess.
- Display format: mm:ss for lengths under one hour (125 seconds is 02:05) and h:mm:ss from one hour (3723 seconds is 1:02:03).
- The parser returns whole seconds as an integer and has no I/O, so it is a pure function.

# Implications for design

- Build item B11 (moved to Stage 2) holds parse_iso8601_duration and format_mmss in src/ytmcp/domain/duration.py; the mapper that turns API JSON into models calls it.
- Tests: the examples above, zero-length cases, garbage input, and a hypothesis round-trip property between parsing and formatting a number of seconds.

# Related

- (links added during brain-refine)
