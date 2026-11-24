---
title: quota-policy
type: area
created: 2026-11-25
tags: [quota, youtube]
requirements: [QTA-1, QTA-2, QTA-3, BR-2, BR-5]
sources: []
status: distilled
---
# Summary

YouTube quota is per day and per Google Cloud project. It resets at midnight Pacific Time (13:30 IST in winter, 12:30 IST in summer).

# Key facts

- Usable budget per day: 9,500 units (10,000 minus a 5 percent reserve).
- The sum of all machine budgets plus CI must stay at or below 9,500 units.
- Normal day: 3 laptops x 2,000 units + CI 500 units = 6,500 units, leaving 3,000 unallocated.
- Demo day: demo laptop 4,000, the other two 1,000 each, live smoke tests off.
- Local ledgers are soft controls. The Cloud Console quota page and the API quotaExceeded error are the only global truth.
- Habits: develop on fixtures, record each fixture once, one search query for FR-1 and two for playlists, batch videos.list at 50 IDs, cache for 24 hours.

# Implications for design

QuotaGuard enforces both the global reserve and machine_daily_budget (config/default.toml).

# Related
