# Calendar P3 full-500 feedback

Calendar revision `unified-attention-calendar-e0` is one fixed solver commit across all 500 P3 coordinates. This report compares it cell-by-cell with the prior expanded full-500 feed. The reproduction script checks exact 100×5 coverage, successful P3 status, graph/config/official hashes, one new solver commit, and reads each paired baseline gzip to verify its SHA-256, scene A, one core, and makespan. All 100 old/new baseline gzip hashes match.

| Cores | Mean speedup old → calendar | M improved / equal / worse | Calendar solver wall mean / max (s) |
|---:|---:|---:|---:|
| 1 | 1.199407 → 1.199407 | 0 / 100 / 0 | 3.795 / 52.109 |
| 2 | 2.287559 → 2.308188 | 24 / 76 / 0 | 3.962 / 36.640 |
| 3 | 3.184366 → 3.239165 | 26 / 74 / 0 | 3.816 / 38.859 |
| 4 | 3.987203 → 4.053230 | 24 / 76 / 0 | 3.957 / 40.504 |
| 5 | 4.595235 → 4.673441 | 24 / 76 / 0 | 4.355 / 41.944 |

Speedup is the arithmetic mean of each case's single-core baseline makespan divided by that multicore makespan. Calendar improves 98 cells, ties 402, and regresses none. Against screenshot numbers 2.28 / 3.23 / 4.09 / 4.76 for 2–5 cores, calendar is above the first two and below the last two; these are numeric comparisons only because screenshot algorithm/config/denominator identity is unverified.

DDR extra-copy bytes, spill bytes, cache-hit rate, and solver wall time are separate measures in `summary.json` and `cells.csv`; changes across these measures are mixed and this report makes no all-metric dominance claim. Solver wall figures are one observation per cell under shared-host batch conditions. The producer is still auditing complete result artifacts; this report does not replace that audit or prove plan legality. Root readback reports 500 solver calls, 861 E0 calls, zero E1/E2, and no retries. This analysis did not rerun E0.

Reproduce (read-only; no scoring calls):

```sh
python3 reproduce.py \
  --old-root <expanded-producer-checkout> \
  --new-root <calendar-producer-checkout> \
  --old-feed <expanded-board-feed.json> \
  --new-feed <calendar-board-feed.json> \
  --output <output-directory>
```

Outputs are `cells.csv` (500 paired rows) and `summary.json`. Feed inputs and producer checkouts are passed explicitly; no personal path is embedded in the script.

## Per-cell tradeoffs

Each triple is improved / equal / worse, comparing calendar with the frozen expanded algorithm. Lower extra DDR/spill is better; higher per-case byte hit rate is better. These are separate comparisons, not a composite score.

|Cores|Extra DDR|Spill|Byte hit rate|
|---:|---:|---:|---:|
|1|0/100/0|0/100/0|0/100/0|
|2|23/76/1|6/89/5|17/76/7|
|3|23/74/3|3/93/4|23/74/3|
|4|20/76/4|5/95/0|16/76/8|
|5|20/76/4|4/96/0|16/76/8|

At5cores, summed extra DDR decreases from 1,717,733,234 to 1,568,498,768 bytes; spill decreases from 757,086,460 to 750,578,324 bytes. The arithmetic mean of per-case byte hit rates increases from 0.301649 to 0.304436; it is not a global byte-weighted hit rate. Four improved-M cells have worse extra DDR and eight have worse hit rate. Thus improved aggregate traffic does not establish per-case dominance.
