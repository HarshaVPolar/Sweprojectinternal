---
title: tf-idf-cosine
type: resource
created: 2026-11-26
tags: [similarity, tf-idf, cosine, fr-1]
requirements: [FR-1.6, FR-1.7, FR-2.6, FR-3.2, FR-5.5]
sources: [SRS v1.0 Appendix B.2, https://en.wikipedia.org/wiki/Tf%E2%80%93idf]
status: distilled
---

# Summary

TF-IDF turns a text into a vector in which words that are characteristic of that text weigh more than common words. The cosine of the angle between two such vectors measures how similar the texts are. The YouTube API has no related-videos endpoint, so this project computes similarity itself from metadata.

# Key facts

- Term frequency: tf(t, d) = number of occurrences of t in d divided by the number of tokens in d.
- Inverse document frequency (smoothed): idf(t) = ln((1 + N) / (1 + df(t))) + 1, where N is the number of documents and df(t) the number of documents that contain t.
- Weight = tf x idf. Each vector is then divided by its Euclidean length (L2 normalisation). For normalised vectors the cosine similarity is just the dot product.
- Tokenisation: lower case, Unicode NFKC, split on every non-alphanumeric character, remove a small English stop-word list, no stemming. The same code must be used for every text so results are deterministic.
- Field weights (project decision, to be fixed in the B14 brief): the term counts of the title are multiplied by 3, of the tags by 2 and of the description by 1 before tf is computed, so a title word counts three times.
- Worked example with one field and N = 3 documents: d1 = "linear algebra basics", d2 = "linear algebra vectors", d3 = "cooking pasta basics". Words that occur in two documents have idf = ln(4/3) + 1 = 1.2877; words that occur in one document have idf = ln(4/2) + 1 = 1.6931. Every tf is 1/3. After normalisation d1 has 0.5774 for each of its three words; d2 has 0.5179 for linear and for algebra and 0.6809 for vectors; d3 has 0.4736 for basics and 0.6227 for cooking and for pasta. cosine(d1, d2) = 2 x 0.5774 x 0.5179 = 0.5980. cosine(d1, d3) = 0.5774 x 0.4736 = 0.2735, because they share only "basics".
- Uses in this project: text cosine with weight 0.50 in the video score (FR-1.7), profile cosine with weight 0.55 in the channel score (FR-2.6), taste-profile centroid (FR-3.2) and topic relevance for playlists (FR-5).
- Ties in a ranking are broken by video ID so the same input always gives the same order (FR-1.8).

# Implications for design

- The corpus is the seed plus its candidates (FR-1) or the topic query plus its candidates (FR-5). The idf values therefore change with the candidate set, which is expected.
- Empty text must give an empty vector and cosine 0.0, never a division by zero.
- The worked example above is the first unit test of build item B14.

# Related

- [[playlist-constraints]]
- [[fixture-recording-strategy]]
