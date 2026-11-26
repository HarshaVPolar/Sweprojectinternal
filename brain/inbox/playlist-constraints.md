---
title: playlist-constraints
type: inbox
created: 2026-11-26
tags: [playlist, algorithm, fr-5]
requirements: [FR-5.5, FR-5.6, FR-5.7, NFR-PERF-3, TQ-1]
sources: [SRS section 4.5.4, https://en.wikipedia.org/wiki/Subset_sum_problem]
status: raw
---

# Summary

Building a playlist of a given total length is a bounded subset-sum problem with an objective: choose videos so that the total duration falls in a window around the target while the total relevance is as high as possible.

# Key facts

- Inputs: candidates with duration in seconds and a relevance score; target T; tolerance (default 5 percent); maximum single-video duration M; at most 3 videos per channel; no duplicates.
- Window in exact seconds: lo = T x (1 - tolerance) and hi = T x (1 + tolerance). For T = 7200 s the window is 6840 to 7560 s.
- Dynamic programming over duration in 10-second units on the 60 most relevant candidates. For two hours that is 7200 / 10 = 720 columns, so about 60 x 720 = 43,200 cells; for 24 hours it is 8,640 columns and about 518,400 cells. The unit window for the example above is 684 to 756.
- Each cell keeps the best total relevance for that duration sum plus a back-pointer, so the chosen set can be rebuilt. Rounding to units makes the result approximate, so the exact total in seconds must be checked against lo and hi.
- Per-channel cap: after selection remove the lowest-relevance excess videos of a channel, refill greedily from unused candidates, and check again.
- Fewer than 10 candidates: a greedy fallback is used.
- If no set fits, return the closest set with a shortfall message such as "only 1h38m found under 20 min" and never claim that the constraints were met (FR-5.6).
- Order the result by ascending difficulty, then relevance (FR-5.7).
- Determinism: ties are broken by the total closest to T, then by the sorted list of video IDs, so repeated runs give identical playlists.
- Required test boundaries: exactly T, just above hi, empty candidate set, a single video equal to M, all videos longer than M, per-channel cap repair.
- Performance target: 60 candidates and a 2-hour target in under 200 ms (NFR-PERF-3).

# Implications for design

- The solver is a pure function in src/ytmcp/domain/constraint_solver.py (build item B12) and takes all inputs as arguments.
- Use hypothesis to show that the result never violates a constraint, and mutation testing to prove the tests are strong.

# Related

- (links added during brain-refine)
