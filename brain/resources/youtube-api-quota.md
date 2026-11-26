---
title: youtube-api-quota
type: resource
created: 2026-11-26
tags: [youtube, quota, api]
requirements: [QTA-1, QTA-2, QTA-3, QTA-4, QTA-5, BR-2, BR-5, TQ-6]
sources: [https://developers.google.com/youtube/v3/determine_quota_cost, SRS v1.0 section 3.3.2 and Appendix D.3]
status: distilled
---

# Summary

Every YouTube Data API call costs quota units. A Google Cloud project gets 10,000 units per day by default and the counter resets at midnight Pacific Time. This project must estimate the cost of a workflow before it runs and refuse the workflow if it does not fit.

# Key facts

- Default daily quota: 10,000 units per project (SRS CON-2). Extra projects must not be created to get more (BR-5).
- Costs used in this project (SRS 3.3.2, held in configuration): search.list 100; videos.list, channels.list, subscriptions.list, playlists.list, playlistItems.list and videoCategories.list 1 each; playlists.insert 50; playlistItems.insert 50.
- When the quota is used up the API answers HTTP 403 with the reason quotaExceeded until the next reset.
- A 5 percent safety reserve leaves 9,500 usable units per day (QTA-3).
- Worked example, a two-hour playlist: 2 searches (200) + 2 videos.list calls (2) + 1 channels.list (1) + 1 playlists.insert (50) + 8 playlistItems.insert (400) = 653 units, about 6.5 percent of a day (SRS D.3).
- Reset time: midnight Pacific Time, which is 13:30 in India during winter (Pacific Standard Time) and 12:30 during summer.

# Implications for design

- Build a call plan, estimate the worst-case cost and reject before any API call if it does not fit (QTA-2, BR-2).
- Record every call in a ledger by Pacific-time day (QTA-1). A cache hit costs 0 units and is recorded as such (QTA-5).
- The ledger is local to each machine, so the shared project quota is only protected by per-machine budgets. The API answer quotaExceeded is the only global signal.
- Develop against fixtures and keep search.list calls to a minimum.

# Related

- [[quota-policy]]
- [[oauth-testing-mode]]
- [[fixture-recording-strategy]]
