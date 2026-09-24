# 首轮研发反馈批次接收回执（2026-09-24）

这是接收端原件核验与当时历史赢家的比较，不是新增solver/E0/E1/E2调用或算法终验。四批全部28条均有固定Git原件、冻结身份及可核单核分母，记录由2827追加至2855，原1500个有效格保持完整。每份JSON记录固定来源commit/feed、接收时间、追加计数及逐格候选/原赢家/新赢家。

| 批次 | 新增 | 原件准入 | 严格改善当时赢家 | 回执 |
| --- | ---: | ---: | ---: | --- |
| P1 component | 8 | 8 | 5 | [q1-component8.json](q1-component8.json) |
| P2 structural portfolio | 6 | 6 | 5 | [q2-feedback6.json](q2-feedback6.json) |
| P3 guarded tree | 10 | 10 | 7 | [q3-feedback10.json](q3-feedback10.json) |
| P1 tree frontier | 4 | 4 | 3 | [q1-tree4.json](q1-tree4.json) |

当前赢家是同problem/case/cores的历史组合，不是统一fixed64控制。`winner=true`可能仅为同分后的稳定哈希选择；严格改善须比较`after < before`。退化和同分保留，旧较优记录不覆盖。P3新10条未交同计划P2配对，CacheGain留空。P1/051候选607628只优于当时中央634666，作者另提旧336057尚待同条件原件补交，不能称优于全部历史。

生产方的算法/runner、在线与最终E0调用、端到端耗时和资源限制仍以各固定feed和原始运行收据为准。成员原有PR97固定2697条快照后有增量，不将旧快照称为最新；同步来源见docs/benchmarks/board-sources.json。
