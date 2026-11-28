# Scoring and algorithm design

Version 1.0 (Stage 2). The specification of record is docs/design/build-contract.md section 11; this page gives precise definitions and worked examples that unit tests can reproduce. Items marked (added) were not fixed there. Brain note: tf-idf-cosine.

## 1. Tokenisation

1. Normalise to Unicode NFKC and lower-case.
2. A token is a maximal run of letters and digits (non-ASCII letters count; the underscore is a separator).
3. Remove stop words. The list is exactly these 36 words: a, an, and, are, as, at, be, but, by, for, from, how, i, if, in, is, it, of, on, or, so, that, the, this, to, was, we, what, when, where, which, who, will, with, you, your. (added)
4. No stemming. Tokens of one character that are not stop words are kept.

## 2. TF-IDF and cosine

- A document has a title, a list of tags and a description. Its tokens are counted with the title tokens multiplied by field_weight_title (default 3), the tag tokens by field_weight_tags (2) and the description tokens by field_weight_description (1). Tags are tokenised like text.
- tf = weighted count of the term divided by the weighted total number of tokens. idf = ln((1 + N) / (1 + df)) + 1, where N is the number of documents and df the number of documents that contain the term. weight = tf x idf. The vector is divided by its Euclidean length. An empty document gives the empty vector.
- cosine(a, b) is the dot product of two normalised vectors; it is 0.0 if either vector is empty.
- Worked example (one field, all weights 1, N = 3): d1 = "linear algebra basics", d2 = "linear algebra vectors", d3 = "cooking pasta basics". idf of a word in two documents is 1.2877; idf of a word in one document is 1.6931; every tf is 1/3. Normalised d1: 0.5774 for each of its three words. Normalised d2: 0.5179 for linear and for algebra, 0.6809 for vectors. Normalised d3: 0.4736 for basics, 0.6227 for cooking and for pasta. cosine(d1, d2) = 0.5980. cosine(d1, d3) = 0.2735.

## 3. Other measures

- jaccard(a, b) = size of the intersection divided by size of the union; undefined (None) when both sets are empty. Tags are compared as lower-cased, trimmed whole tags.
- proximity(x, y, factor) = 1 - min(1, abs(ln(x / y)) / ln(factor)); undefined (None) when x or y is 0 or less; factor must be greater than 1.
- Category match: 1.0 when both categories exist and are equal, 0.0 when both exist and differ, undefined when either is missing. Language match: the same rule with the language codes.

## 4. Video score (FR-1.7)

S = 0.50 C + 0.20 J + 0.15 K + 0.10 D + 0.05 L, with the weights of similarity.video: C text cosine, J tag Jaccard, K category match, D duration proximity with factor 4, L language match. A component that is undefined is dropped and the remaining weights are divided by their sum (FR-1.12). Results are sorted by score descending, then video ID ascending; the seed itself is never returned.

Worked example: C = 0.6, J = 0.5, K = 1, durations 600 s and 900 s (D = 1 - 0.4055 / 1.3863 = 0.7075), L = 1 gives S = 0.3 + 0.1 + 0.15 + 0.0708 + 0.05 = 0.6708. When the tags are missing J is dropped: S = (0.3 + 0.15 + 0.0708 + 0.05) / 0.80 = 0.7134.

## 5. Channel score (FR-2.6)

S = 0.55 C + 0.20 T + 0.15 K + 0.10 Z with the weights of similarity.channel: C cosine of the profile vectors, T Jaccard of topic_ids, K cadence, Z size.

- Profile text (added): title = the channel title; tags = the channel keywords plus the tags of up to 15 recent uploads; description = the channel description followed by the titles of those uploads.
- Cadence (added): with the upload dates sorted, uploads per day = (count - 1) divided by max(span in days, 1), where span is newest minus oldest; fewer than 2 dates means undefined. K = proximity(rate of the seed, rate of the candidate, 4).
- Size: Z = proximity(subscribers of the seed, subscribers of the candidate, 100); a hidden count means undefined.
- Undefined components are dropped and the rest renormalised.

Worked example: C = 0.4; topic sets {a, b, c} and {b, c, d} give T = 0.5; the seed has 15 uploads over 140 days (0.1 per day) and the candidate 7 uploads over 30 days (0.2 per day), so K = 0.5; 1,000,000 against 100,000 subscribers gives Z = 0.5. S = 0.22 + 0.10 + 0.075 + 0.05 = 0.445. With a hidden subscriber count on the candidate: S = (0.22 + 0.10 + 0.075) / 0.90 = 0.4389.

## 6. Candidate search queries (added)

- FR-1: one query made of the 6 highest-weighted terms of the seed vector (weight descending, ties alphabetical) joined by single spaces.
- FR-2: the same rule on the seed channel profile vector.
- FR-3: two queries from the taste profile: terms 1 to 6 and terms 7 to 12 of its top terms.
- FR-5: two queries: the topic, and the topic followed by the words " course lecture".
- The language is never sent to the search API; it is applied as a local filter (this also keeps recorded fixtures replayable).

## 7. Taste profile and MMR (FR-3)

- Sources and item times (added): likes use the video publication time; playlists use the time the item was added; subscriptions use the subscription time. A subscription is described by its channel text.
- decay = 0.5 to the power (age in days / half_life_days), age at least 0; with the default 180 days: 0 days gives 1, 90 days 0.7071, 180 days 0.5, 360 days 0.25.
- Per source: v_s = sum of decay x vector divided by the sum of decay. Centroid = sum of weight_s x v_s divided by the sum of the weights of the non-empty sources, using taste.likes 0.5, taste.playlists 0.3, taste.subscriptions 0.2; then normalised. top_terms are the 20 highest centroid weights (ties alphabetical). All sources empty means no profile (the service raises EMPTY_PROFILE).
- Recommendation score = cosine(centroid, candidate vector). Popularity is only a tie-break or a quality floor (BR-3).
- MMR (added): MMR(c) = lambda x rel(c) - (1 - lambda) x max over selected s of cosine(vec(c), vec(s)), with the max term 0 when nothing is selected; lambda = taste.mmr_lambda (0.7). Select greedily; skip a candidate whose channel already has taste.per_channel_top10 (2) selected items; ties by video ID.

## 8. Playlist relevance and hard filters (FR-5.3)

- Relevance = cosine(topic vector, candidate vector) with the topic as a document of its own in the corpus.
- A candidate must have a known duration between playlist.min_item_s (60) and max_video_duration, privacy public, live_status none, and embeddable not false.
- Language (added): a candidate passes when its language equals the requested language or is unknown (None). The proposal states how many chosen items have an unknown language.

## 9. Difficulty and ordering (FR-5.7, TBD-4)

- d = 0.6 x min(1, duration / max_item_s) + 0.4 x level; a missing duration counts as 0 for the first part (added).
- level is 0 when the lower-cased title or tags contain a whole word or phrase of: intro, introduction, basics, beginner, overview, 101, crash course; otherwise 1 when they contain: advanced, deep dive, proof, theory, masterclass, graduate; otherwise 0.5. The beginner list is checked first.
- Order by d ascending, then relevance descending, then video ID ascending.
- Examples with max_item_s = 1200: "Introduction to linear algebra" at 600 s gives 0.3; "Advanced proofs in algebra" at 1200 s gives 1.0; "Linear algebra lecture" at 900 s gives 0.65.

## 10. Constraint solver (FR-5.5, FR-5.6)

- Window in whole seconds (added): lo = ceil(T x (100 - tolerance_pct) / 100), hi = floor(T x (100 + tolerance_pct) / 100). For T = 7200 and 5 percent: 6840 to 7560. With dp_unit_s = 10 the unit window is ceil(lo / 10) to floor(hi / 10): 684 to 756.
- Candidates with a duration of 0 or less or above max_item_s are ignored; duplicate video IDs keep the one with the highest relevance. Keep the dp_top_n (60) candidates with the highest relevance (ties by video ID).
- Durations are rounded half up to units of dp_unit_s. The dynamic programme maximises the sum of relevance over exactly reachable unit sums. Examine unit sums inside the unit window in descending value; accept the first set whose exact total in seconds lies in [lo, hi].
- Per-channel cap: remove the lowest-relevance excess of a channel, refill greedily from unused candidates in relevance order without breaking the cap or the upper bound, and verify again.
- Fewer than 10 usable candidates: greedy in relevance order, adding a candidate when the total stays at most hi and the channel cap holds.
- If no set fits: return the set with the largest total at most hi (ties by relevance), feasible false, shortfall_s = max(0, lo - total).
- Messages (added): format_hm(s) is "<h>h<mm>m" with two-digit minutes when there is at least one hour and "<m>m" otherwise (5880 s gives 1h38m, 3600 s gives 1h00m, 2280 s gives 38m). Feasible: "target met: total <format_hm(total)>". Not feasible: "only <format_hm(total)> found under <max_item_s // 60> min", or "no video found under <max_item_s // 60> min" when the set is empty. Example: "only 1h38m found under 20 min".
- Deterministic: ties are broken by the total closest to T, then by the sorted list of video IDs.

## 11. Configuration keys used

similarity.field_weight_title, field_weight_tags, field_weight_description; similarity.video.* and similarity.channel.*; similarity.default_candidates and max_candidates; taste.likes, playlists, subscriptions, half_life_days, source_cap, per_channel_top10, mmr_lambda; playlist.tolerance_pct, per_channel_cap, dp_unit_s, dp_top_n, search_queries, min_item_s. Domain functions never read the configuration; the calling service passes the values as arguments.
