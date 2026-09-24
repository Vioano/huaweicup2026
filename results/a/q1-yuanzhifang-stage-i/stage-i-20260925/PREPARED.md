# Stage I five-cell pilot

The authorized pilot completed on 2026-09-24. Runner HEAD: `7993bafe22cbdbcd9ebc12b15dfecd4ef651563b`; solver: `397e7ca0b680f50336e4dd4eefb14831015107d8`. All five cells passed external E0: 051/k5 231551 cycles, 084/k2 792218, 084/k4 446068, 084/k5 399121, and 008/k5 100603. These are diagnostic pilot cells, not a full-suite mean or blind test.

Batch T0/T1 were `2026-09-24T20:16:57.234828Z` / `2026-09-24T20:17:45.062864Z` (47.816 s). Calls: 5 cold solver, 15 charged online E1 interface attempts, 5 external E0, 0 E2, 0 retries. Two workers; no supervision failure. Per-cell solver/E0 timing, full plans, traces, logs and process receipts are in `run/`; score feed is `board-feed.json`; byte-verified single-core baseline copies are in `baseline/`. See `tasks/a/q1-yuanzhifang-stage-i.md` for scope and acceptance limits.
