# 图 6-2 自查记录（甲，v1，2026-09-26）

## 实际执行结果（本机制图环境）

- 命令：`.venv/Scripts/python.exe figures/a/jia-fig6-2-20260926/plot.py`（工作目录=仓库根），退出码 0。
- 脚本内置切点自检通过：两方案切点均有序、首尾覆盖 [0,124] 无重叠/遗漏、核 0..3 顺序递增。
- 输出：figure.svg（矢量）/ figure.png（300 dpi，约 2050×2020 px；图宽按 165mm 正文宽设计，最小字号 5.8pt，插入 100% 可读）。

## 数据来源与身份（全部固定提交，抓取字节哈希见 audit.sources）

- 容量方案：results/a/q3-yuanzhifang/pipeline-capacity-20260925/manifest.json（constructions[0].detail：cuts [0,41,65,95,124]、stage_memory 静态估计、capacity L1/524288 UB/131072）+ REPORT.md（官方 L1 峰值 [79584,516992,330752,18816]、官方 UB 峰值全 0、P3=37581、extra DDR 121088、spill 0），固定提交 7edacdd97a7be36a402af20bc8bfa8a7454dbbe0；计划 sha256 715be4ece4ebc6d5db625efd2f7adb6a439e37b0e1f1e7f0a4a16a190b039a7c。
- 控制方案（计算均衡）：results/a/q3-yuanzhifang/pipeline-20260924/manifest.json（cuts [0,28,58,91,124]、stage_compute_cycles）+ comparison.json（逐核官方内存峰值 [19680,430080,473600,22912]、P3=40927、extra DDR 135168、spill 0）；计划 sha256 44c66c84a4a50337…（由 capacity 批次 manifest.identity.controls.044 登记为控制，original_commit e6b5500dcbf3818034804168ee79d0f65c16706b，与 REPORT.md 口径一致）。
- 仅首次装入早期候选：P3 初稿 6.6.3 文字（P3=41738、spill 1,622,016 B、某阶段共同输入 663,552 B 超 L1 容量）。

## 缺项登记（不造数）

- **早期候选（firstload_only）切点/核归属/工作集明细缺失**：固定批次中无其切点元数据，cuts.csv 无该 variant 行，图中不绘制其条带，仅以第三行文字与 L1 分面 648 KiB 参考线呈现有据可查的实测结果与报告峰值。
- 除上述外无其他缺失；未借用 044/k5 的任何切点或结果。

## 验收标准逐项

1. 切点有序（两方案均 0 起、124 止、相邻共享边界）、完整覆盖计算位置、无重叠或遗漏（脚本断言）；核归属=阶段索引（4 阶段对应 4 核的固定流水结构；控制方案逐核官方峰值 [19,680/430,080/473,600/22,912] 与容量方案逐阶段工作集量级相互印证），与方案一致。通过。
2. 容量单位（B/KiB）、内存空间（L1/UB）和工作集定义（共同输入+单次操作非共同）在图注/分面标题明确；静态估计（斜纹柱）与实测（实心柱/菱形标记）使用不同标记，两方案官方 UB 峰值 0 亦注明"实测记录，非估计值"。通过。
3. 未借用 044/k5 的切点或结果（全部数据来自 044/k4 固定批次）；图注声明"容量可行不证明零 spill 证书或 Makespan 最优"，静态估计与实测峰值分开标注。通过。

## 其他说明

- 核归属推导依据写入本记录：固定流水模型 4 阶段对应 4 核（serial stage 服务、11 作业流经各阶段）；cuts.csv 的 core 列即阶段索引。若工作台认定需以方案文件核归属另行证明，可从固定 plan 原件（sha256 已登记）展开核对。
- 未完成项：无（early candidate 元数据缺项如上登记，非本方数据缺口可补）。
