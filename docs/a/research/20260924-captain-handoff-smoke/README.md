# 队长Q2历史交接冒烟原件

原 [Q2交接回执](../../Q2_HANDOFF_SMOKE.json) 只保存了4文件的大小/哈希，原件仍在队长独立工作区。本次按用户共享要求补齐 [plan](originals/plan.json)、[完整result](originals/result.json)、[trace](originals/trace.json)、[运行日志](originals/run.log)，逐项与回执字节相同；[清单](manifest.json) 保存来源与全部哈希。

来源回执固定提交：`b85802f6c271eb48ebaab6ce07f9a3d26d63302c`；当时基线 `cd5ef2b8a9f3518579167bf8a9271d6a76403b30`。case002 / Q2 / 4核 / seed0，官方随机格式stub，Makespan=200352 cycles。原目录虽含yuanzhifang，但实际由队长本机运行，不是Fang算法或他的本机实验，不与P2新研究、StageB或本轮成绩混源。

原4文件2,938,371字节保持不变。只做字节/来源核查，无新增solver/E0/E1/E2；本次不入成绩台，不重跑、不补造旧计时或缺失环境。旧命令入口见 `docs/a/Q2_HANDOFF.md`。公开原件不等于队友已复现或算法提升。
