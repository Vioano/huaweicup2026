# P2 机制试验证据索引

本页只索引固定原件，不把单格机制试验并入方案成绩台正式 500 格批次。数值来自生产者提交的回执；成绩台维护者未重新运行求解器或评价器。

| 固定原件 | 范围与回执 | 使用边界 |
| --- | --- | --- |
| [069/5 核 native 关键包 pilot 说明](https://github.com/huaweibei123/huaweicup2026/blob/89d87ba225f505d0cb3cb7437d24f10bd79ba380/results/a/q2-nikolastarx/native-packet-069-pilot-20260925/README.md)；[证据 ZIP](https://github.com/huaweibei123/huaweicup2026/blob/89d87ba225f505d0cb3cb7437d24f10bd79ba380/results/a/q2-nikolastarx/native-packet-069-pilot-20260925/results.zip)，SHA-256 `d14737694cbdb69295b812921ce11d4b56788e6204bb390988c81c4876f2c1aa` | 旧 c665 069/5 核计划的机制 pilot。回执记载 15 次 native、1 次独立 E0；Makespan 11962→11861，额外 DDR 321938 B 不变。维护者已核对固定提交可远端读取、ZIP 字节 SHA 和回执调用计数。 | 不是从原始图开始的完整求解器，也不是新全量 benchmark；未交 `board-feed*.json`，不导入正式成绩表，不替换 c665 的 500 格结果。 |
| [005/069/071 的关键包插入 pilot 说明](https://github.com/huaweibei123/huaweicup2026/blob/3e6b6bf36a2da99ac3c400407b79bfa88915b088/results/a/q2-nikolastarx/shifted-packet-three-20260925/README.md)；[证据 ZIP](https://github.com/huaweibei123/huaweicup2026/blob/3e6b6bf36a2da99ac3c400407b79bfa88915b088/results/a/q2-nikolastarx/shifted-packet-three-20260925/results.zip)，SHA-256 `a4092d5beff77e2a53a233f173aacac7571d97f90cf393398d389d7eb522a3aa`；[逐候选 CSV](https://github.com/huaweibei123/huaweicup2026/blob/3e6b6bf36a2da99ac3c400407b79bfa88915b088/results/a/q2-nikolastarx/shifted-packet-three-20260925/candidate-scores.csv) | 旧 c665 三个 5 核计划的另一机制 pilot。回执记载 3 次 propose、26 次 native、3 次独立 E0；005：33515→33436，额外 DDR 1410582→1410486 B；069：11962→11849，321938 B 不变；071：9465→9394，273776→271472 B。维护者已核对远端提交、ZIP/CSV 发布字节 SHA、回执调用计数和 CSV 中 23 个候选含退化项。 | 三格增益均不足 1%，且从保存的旧计划出发；不是完整求解器或全量 benchmark。未交 `board-feed*.json`，不导入正式成绩表，不替换 c665 的 500 格结果。069 的两份 pilot 独立以同一旧工期 11962 为对照，不视为连续改进。 |

