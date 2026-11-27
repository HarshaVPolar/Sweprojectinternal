# ADR-003: Similarity computed locally with our own TF-IDF and cosine code

Status: accepted
Date: 2026-11-28

## Context

The YouTube Data API has no related-videos or related-channels endpoint, and watch history is not available (SRS CON-3). Similarity must therefore be computed from metadata. The SRS asks for simple techniques: TF-IDF, cosine similarity over feature vectors and basic weighted scoring.

## Decision

- Implement the text vectoriser, cosine, Jaccard, proximity and the weighted rankers as pure Python functions in ytmcp.domain, with no machine-learning or numerical library.
- Formulas, field weights, score weights and tie-breaking are fixed in docs/design/build-contract.md section 11 and configured in config/default.toml (NFR-MNT-3).
- Rankings are deterministic: ties are broken by video ID, the same input always gives the same order.
- Popularity is never the primary ranking factor (BR-3).
- Playlist relevance is the cosine between the topic query and each candidate.

## Consequences

- The code is transparent, unit-testable and needs no extra dependency.
- Relevance is limited by the quality of titles, tags and descriptions (assumption A-2); the weights can be tuned and ablation tests can check each component.
- Pure Python is slower than a vectorised library, which is acceptable: 200 candidates must rank in under 1 second at the 95th percentile (NFR-PERF-1).
- Embeddings or other models are out of scope for release 1.0 and would need a new ADR.

## Brain notes cited

- [[tf-idf-cosine]]
