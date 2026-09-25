# One sequence-difference check

Hypothesis: the safe merge may advance managed allocations despite unchanged target MTE2 ordinal. Inspect all four FIFO words, changed arcs and allocation order through target. No runtime prediction. Inputs have in-script fixed SHA. Source SHA 5960da010a711ae30bf41c8e5f24e3151f6122c8fc6afabed81fe985bd878187. One pure static process, 30 seconds, 1 worker, no retry, 0 Task/Step/E0. Command: `python3 -B results/a/q3-nikolastarx/convex-safe-prefix-20260925/analyze.py`.
