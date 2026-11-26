# Traceability matrix

Seeded from SRS Appendix E and maintained alongside implementation. Columns are filled progressively through the planned stages. A star marks a brain note that is planned and written later.

| Requirement | Design element | Build item | Issue | PR | Test | Skill | Brain note |
|---|---|---|---|---|---|---|---|
| FR-1 | SimilarityService, TfIdfVectoriser, WeightedRanker | B10, B14, B23, B26 | | | unit scoring; system FR-1; negative invalid ID and missing tags | video-to-playlist (step 2) | [[tf-idf-cosine]], [[youtube-api-quota]] |
| FR-2 | SimilarityService, ChannelProfileBuilder | B27 | | | unit; system FR-2; negative handle not found | - | [[channel-similarity]] * |
| FR-3 | RecommendationService, TasteProfile | B28 | | | unit; integration provider; system FR-3 | - | [[taste-profile-design]] * |
| FR-4 | EngagementService | B29 | | | unit stats; system FR-4 | - | [[engagement-metrics]] * |
| FR-5 | PlaylistService, ConstraintSolver, ConfirmationGate | B11, B12, B13, B22, B24, B25 | | | unit constraints and durations; system FR-5; negative channel required and partial resume | video-to-playlist (steps 3 to 5) | [[iso8601-durations]], [[playlist-constraints]] |
| QTA, TQ-6 | QuotaGuard, QuotaLedger | B16 | | | unit and system reject-before-call; negative quotaExceeded | video-to-playlist (SK-6) | [[youtube-api-quota]] |
| SEC-1, SEC-2 | OAuthManager, TokenStore | B19, B20 | | | security scopes and storage; negative expired token | - | [[oauth-testing-mode]] |
| SEC-4 | InputValidator, Sanitiser | B10 | | | unit; security fuzz | - | [[prompt-injection]] |
| SEC-5, SEC-6 | ConfirmationGate, Sanitiser | B10, B22, B25 | | | security gate bypass and injection corpus; system FR-5 | video-to-playlist (SK-3) | [[prompt-injection]], [[approval-gate-design]] * |
| SEC-11, NFR-REL-1, NFR-REL-2 | RateLimiter, LiveYouTubeProvider | B15, B21, B30 | | | unit; negative rate limit and API errors | - | [[rate-limiting-backoff]] * |
| SE-6, TQ-5 | YouTubeProvider and implementations | B04, B06, B21 | | | integration contract tests | local-check | [[provider-pattern]] *, [[fixture-recording-strategy]] |
| SK-1 to SK-8 | skills/video-to-playlist | B31, B33 | | | skill evals | video-to-playlist | [[agent-skills-format]] |
| SK-9 to SK-12 | scripts/local_check.py | B32 | | | skill eval | local-check | [[local-check-design]] * |
| SK-13 to SK-16 | brain/ vault and skills | Stage 1 | | | CI brain-note validation | brain-ingest, brain-refine, brain-query | [[para-method]] *, [[second-brain-schema]] * |
| NFR-PERF-1 to NFR-PERF-6, NFR-MNT-2, NFR-POR-1 | benchmarks and CI | B18, H1 | | | benchmarks; 3-OS matrix; coverage gates | - | [[sqlite-wal]] |
