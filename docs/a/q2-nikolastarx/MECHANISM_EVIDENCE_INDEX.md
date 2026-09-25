# P2 机制试验证据索引

本页只索引固定原件，不把单格机制试验并入方案成绩台正式 500 格批次。数值来自生产者提交的回执；成绩台维护者未重新运行求解器或评价器。

| 固定原件 | 范围与回执 | 使用边界 |
| --- | --- | --- |
| [069/5 核 native 关键包 pilot 说明](https://github.com/huaweibei123/huaweicup2026/blob/89d87ba225f505d0cb3cb7437d24f10bd79ba380/results/a/q2-nikolastarx/native-packet-069-pilot-20260925/README.md)；[证据 ZIP](https://github.com/huaweibei123/huaweicup2026/blob/89d87ba225f505d0cb3cb7437d24f10bd79ba380/results/a/q2-nikolastarx/native-packet-069-pilot-20260925/results.zip)，SHA-256 `d14737694cbdb69295b812921ce11d4b56788e6204bb390988c81c4876f2c1aa` | 旧 c665 069/5 核计划的机制 pilot。回执记载 15 次 native、1 次独立 E0；Makespan 11962→11861，额外 DDR 321938 B 不变。维护者已核对固定提交可远端读取、ZIP 字节 SHA 和回执调用计数。 | 不是从原始图开始的完整求解器，也不是新全量 benchmark；未交 `board-feed*.json`，不导入正式成绩表，不替换 c665 的 500 格结果。 |

