# P1 v4 timeout and isolated diagnosis

The first fixed v4 window stopped at its first abnormality: official external E0 for 014/k4 exceeded the original 180 s cap. It left 149 valid cells, one timed-out cell, and 350 undispatched cells. The separate one-cell diagnosis reused only the saved 014/k4 plan and obtained official M=4,500,863 after 378.595 s. Both original runs remain distinct from the later independent full500 window.

`summary.json` records exact original SHA-256 hashes and call counts. `old-500-cell-ledger.json` records each cell status and raw receipt hash; it is a compact historical ledger, not a complete republication of all 149 old evaluator artifacts. The `.gz` files decompress to byte-identical failed plan/diagnostics and isolated official result/trace/plan. The official graph is identified by its frozen source manifest. No result from this archive was used to fill the later full500 score.
