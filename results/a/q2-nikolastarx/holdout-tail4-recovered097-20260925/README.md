# P2 留出测试：097 原件接收

冻结求解器 `15d86e13b4a8abb4bce445ac241aecac13f553bf`。097 方案来自上一个窗口，本窗口只做一次独立 E0：Makespan **2102348**，额外 DDR **21311488 B**（其中 spill **4272128 B**），与 c665 同图同核结果相同。

官方子进程退出 0、无存活子进程。父脚本把相对输出交给了不同工作目录的子进程，随后在错误目录读取结果失败；原 `summary.json` 的 stopped/in_flight/count-incomplete 完整保留，本文是独立接收更正，未把失败批次改成成功批次。既有结果、trace、log 按原字节归档，没有重评；两个原目录都保留。

实际新增账为 **0 solver / 0 E2 / 1 独立 E0 / 0 fallback / 0 retry**；076、003、084 未派发。至此预先选定的 12 图有 9 图官方证据，全部持平，仍不是全量新成绩。

`readback.json` 含两目录身份、路径、哈希、过程记录和旧版配对；`originals.zip` 保留 producer、official-output-actual-cwd、saved-solver097、preparation 四类原件。旧求解耗时与本窗口 E0 耗时分列。
