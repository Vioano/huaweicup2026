# P3 Cartesian whole-tree ownership: band DP and certificates

## Provenance and execution boundary

Only the Vioano mirror at commit `92d454913ac4330646800cf51309a8b21842fa4f` was used as repository material. The four requested source/note/report files were read. Current P3 input-copy/Cache fragments and config were also read. No raw 058/079 graph was read in this turn. No official evaluator, Step2, or Step3 was run.

The examples are coordinate grids using the user's supplied parameters. They are NOT official submission plans. `forest_band_dp.py` is an integration adapter using the read interfaces; it was syntax-checked only. A team-side raw-graph run must perform the actual guards, plan derivation and official checks.

## Main construction

Divide an oriented grid into consecutive horizontal bands. Within each band traverse columns, reversing column direction from band to band; within a column traverse rows in increasing order. Concatenate all cells, then cut the word into the fixed q/q+1 core quotas (larger quotas first).

The exact restricted DP state comprises completed row count, next column direction and the width of the column support of the sole open core. The visited-cell count determines the open core and quota remainder. Row supports in later bands are disjoint; the open core's old and new column supports are nested at the shared end. Thus no other history is needed for D.

The DP optimizes D, then duplication of the heavier mean-size axis, then band count. Both orientations and reversals are compared algebraically. The original two plain-axis cuts are retained as controls. Output is one coordinate partition, with no evaluator sweep.

There are at most twice (m+1)(n+1) states for one orientation. Each tries at most m band heights, and each band intersects at most k quotas. Prefix sums handle unequal group bytes. Complexity is O(k*m*m*n) for one orientation, O(k*m*n*(m+n)) for both, O(m*n) state storage, plus output/recognition/official validation costs. This is NOT an exact solver for all balanced edge partitions, all rectangles, or all guillotine partitions.

## Coordinate certificates

For m=17, n=15, k=5, A=270336 bytes, B=135168 bytes:
- Band heights 3,1,5,2,6; begin at the low-column side, reverse each band.
- Quotas 51,51,51,51,51.
- Footprints (rows,columns): (4,15),(6,9),(7,9),(8,7),(6,9).
- D = 15003648 bytes. The independent all-balanced-partition lower bound is 14868480 bytes. Thus the D-optimality gap is at most 135168 bytes, at most 1/110 of the optimum.

For m=18, n=16, k=5, A=202752 bytes, B=135168 bytes:
- Band heights 6,3,3,6, same traversal rule.
- Quotas 58,58,58,57,57.
- Footprints (6,10),(9,7),(6,10),(9,7),(6,10).
- D = 13246464 bytes, equal to the independent all-balanced-partition lower bound. This is a global optimum of D for whole-tree balanced coordinate ownership, NOT an official P3 optimum.

## Independent lower-bound arguments

For the first example measure bytes in units of 135168. Every core supports at least 51 cells, hence row-support plus column-support is at least 15. Let R and S denote total row/column incidences, and t the number of cores supporting all 15 columns. A single-supported row can occur only on one of those t cores; each such core can own at most three full rows. Thus R is at least 34-3t. Each full-column core supports at least four rows, so total cost 2R+S is at least 109+t. If t is positive, cost is at least 110. With no full-column core, equality at 109 would force R=34 and each footprint sum=15. Its row supports then each lie between six and nine. The sum of any two is at most 16, so no two cores cover all 17 rows of a column: every column needs at least three cores. This requires S>=45, contradicting S=41. Hence the cost is at least 110.

For the second example measure bytes in units of 67584. Every core has at least 57 cells, so each footprint sum is at least 16 and its local weighted cost 3r+2s is at least 38. If no core touches all 16 columns, every row appears on at least two cores, giving R>=36; total cost R+2(R+S) is at least 196. If a full-column core exists, it needs at least four rows and costs at least 44; four other cores cost at least 38 each, again giving 196. The coordinate witness attains this bound.

## Tree-order model: deliberately not the official cache model

`row_block_word` keeps a fixed increasing order of A groups and chooses the first/last B of each A block by endpoint DP. It minimizes B reload bytes within that restricted word family. `pair_cache_bytes` assumes sequential whole trees, atomic full groups, and retention of only the current A and current B. It does not assume those properties hold under official COPY/Belady/Step3.

For uniform A>=B, every order of e distinct cells touching r A groups must load at least r*A+(e-r+1)*B bytes in this model. The proof counts coordinate changes between successive distinct cells. A row-block snake attains the bound on a full rectangle, and on a ragged part when every row transition retains the B endpoint. The saved example words attain it.

The conflict is real within this explicit model, even with optimal tree order:
- First example: the plain-axis owner needs 37982208 input bytes, the new D-better owner needs 39333888.
- Second: 41091072 versus 42037248.
These are model costs, NOT measured traffic or predictions of official makespan.

## Running the checks

Run `python make_certificates.py`. It writes full coordinate owner matrices, cell lists, footprints, group-order words, all 31 core-subset Hall compatibility checks per example, and the restricted model comparisons. Eleven small checks independently enumerate only tiny band compositions or fixed-row-block permutations, not official graphs or arbitrary large edge assignments.

`certificates.json` is the actual generated output. Code errors are not converted to performance failures. No benchmark or official outcome is asserted.
