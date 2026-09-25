# P3 最后一轮：已完成500格，沿用Forest主算法

见 [FINAL_REPORT.md](FINAL_REPORT.md) 获取结论、指标定义、真实两段执行和证据边界。

- 固定求解器 `f6fd8153375a7fb64f9af2c8f36c35356fb7d878`，100图×1–5核全部有效；无失败、无重试、982次在线E0。
- 500份输出计划字节与旧Forest相同；五核均值4.7576166788448955，同计划G均值1.082917172693062；本轮没有提高质量。
- 主论文继续使用Forest；第五核选择器作为负消融与目标取舍证据保留。不再开启新Pro/新研发轮次。
- [机器汇总](final-export-20260926/summary.json)、[逐格数据](final-export-20260926/comparison.csv)、[图件](figures/p3-final-full500.pdf)、[实际第五核决策](FIFTH_CORE_DECISIONS.json)。
- 400+100是同算法两个互斥执行段，原run_id、每格墙钟与预算都保留；不是历史逐格选优。
- 大批次JSON使用同目录lossless gzip与archive清单保全，按清单可恢复原hash。
- [同计划P2/P3主对照图与附录](SAME_PLAN_FIGURES.md)：主图横轴核数，两条逐图mean(B/M)曲线；均由已审500格数据离线生成。
- 中央接收/镜像同步属于后续交付核验，不能从本地预检代签。

[最初冻结计划与预算](https://github.com/huaweibei123/huaweicup2026/blob/65c07e062ed9be78dda32ef4bb58a9891f373de9/results/a/q3-nikolastarx/r9f-final-full500-20260926/README.md) 保留于原固定版本；[缺格100单独执行说明](COMPLETION_100_PROPOSAL.md) 保留补段授权与范围。
