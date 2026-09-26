# 图 6-2 自查记录（甲，v2，2026-09-26）

## 本版变更（回应返工单 F62-R01/R02/R03，意见 5845635769）

- F62-R01：补齐第三条切分带。来源为固定提交 7edacdd97a7be36a402af20bc8bfa8a7454dbbe0 下
  results/a/q3-yuanzhifang/pipeline-setup-followup-20260924/：manifest.json（constructions[0].detail：
  cuts [0,41,70,98,124]、jobs=11、positions=124、stage_compute_cycles [2822,1709,1577,1564]、
  shared_input_bytes_by_stage [73440,663552,186368,7040]）、044/pipeline_cold_setup/case_044_multicore_res.json
  （逐核操作数 [451,319,308,286]）、044/pipeline_cold_setup/P3/result.json.gz（makespan=41,738、
  added_copy 1,731,840 B、spill 1,622,016 B、官方 L1 峰值 [79584,516992,188160,15744]、UB 全 0、
  cache 命中 1,622,016 B / miss 1,007,840 B）。删除"缺失，未绘条带"声明与 audit.parameters.missing 缺项登记。
  663,552 B 保留为该候选阶段 2（索引 1）的共享输入静态量并明确标注"静态量，非官方峰值"。
- F62-R02：cuts.csv 规范为 12 行（variant=balanced/resident/first_load，core=1..4，case=044、cores=4、
  位置 0..124）；capacity.csv 重写为 6 行唯一 (variant,space) 规范汇总（取各方案官方逐核峰值的最大值：
  balanced 473,600、resident 516,992、first_load 516,992，UB 均 0，evidence_type=measured），并明确这是
  "各方案最大单核官方峰值"，非跨核相加、不说明零 spill；原逐核/静态细表移入 capacity_detail.csv
  （继续供主图使用，含 first_load 四阶段共享输入静态量行）。audit.sources 每文件一条真实 path、
  完整 40 位 commit、64 位 SHA256；拆开 manifest.json 与 comparison.json；移除"见固定提交 blob"占位；
  新增第三方案 manifest/plan/result 来源。command 只保留实际可执行命令，解释与工具版本移至 environment 字段。
- F62-R03：行标题缩短为方案名+关键结果（阶段计算量/长解释移入 caption 或分行说明）；第三行改为真实条带；
  图例移至专用底部图例区（不再覆盖任何面板），"UB 容量 128 KiB"留在 UB 分面左上空白处；
  相近切点（91/95、41/65/70）通过各条带上方自己的切点数值标注区分，共享轴只留常规刻度 0/25/50/75/100/124，
  不在 91 处伪装两个刻度；改用 figsize=(6.5,7.8)+constrained_layout 导出，弃用 bbox_inches="tight"，
  避免长文本把画布横向撑大。

## 实际执行结果（本机制图环境）

- 命令：`.venv/Scripts/python.exe figures/a/jia-fig6-2-20260926/plot.py`（工作目录=仓库根），退出码 0。
- 脚本内置断言全部通过：cuts 12 行、3 方案各 4 段、连续覆盖 [0,124]、core=1..4；
  capacity.csv 恰 6 个唯一 (variant,space)、L1=对应方案 detail 逐核官方峰值最大值、UB=0、evidence_type=measured；
  first_load 阶段共享输入静态量 4 行在案（stage1=663,552 B）。
- 输出：figure.svg 宽 468 pt = 165.10 mm（与 6.5 in 设计宽一致，无 tight-bbox 撑宽）、高 561.6 pt≈198.12 mm；
  figure.png 300 dpi 1950×2340 px。最小字号 6.0 pt（165 mm 插入 ≈6.0 pt，无缩放）。

## 与固定原件逐键核对（全部取自 7edacdd97a7be36a402af20bc8bfa8a7454dbbe0 的 Git 字节，SHA256 见 audit.sources）

| 项 | balanced | resident | first_load |
|---|---|---|---|
| 切点 | [0,28,58,91,124] | [0,41,65,95,124] | [0,41,70,98,124] |
| 逐核操作数（索引0..3） | [308,330,363,363] | [451,264,330,319] | [451,319,308,286] |
| 合计操作 | 1364 | 1364 | 1364 |
| 官方 L1 峰值（索引0..3） | [19680,430080,473600,22912] | [79584,516992,330752,18816] | [79584,516992,188160,15744] |
| 官方峰值最大值（→capacity.csv） | 473,600 B | 516,992 B | 516,992 B |
| UB 峰值 | 全 0 | 全 0 | 全 0 |
| P3 makespan | 40,927 | 37,581 | 41,738 |
| 额外搬运 / spill | 135,168 / 0 B | 121,088 / 0 B | 1,731,840 / 1,622,016 B |

三方案条带各覆盖 [0,124] 无缝、无重叠；每条 4 段；结果数值逐键与各 manifest / case_044_multicore_res.json /
P3/result.json.gz 原件一致（本表数值即本轮从固定提交独立读回复核所得）。

## 审查方待处理项知悉

- 在线机检 v1.1 将 Matplotlib 标准 SVG 1.1 跨行声明误报为 DTD：本图保留标准声明，未为其改动；
  由审查方 v1.2 引擎处理重检。

## 验收标准逐项

1. 切点有序，完整覆盖计算位置（三方案均 [0,124] 无缝无重叠）；核归属与方案一致（三份计划原件逐操作核对口径，
   乙已独立比对 1364 操作归属；本轮补充核验 first_load 切点与逐核操作数）。通过。
2. 容量单位（B/KiB）、内存空间（L1/UB）和工作集定义明确；静态估计（斜纹/点线）与实测（实心柱/菱形/空心圈）
   使用不同标记。通过。
3. 未借用 044/k5 的切点或结果；不以静态容量满足证明零 spill 或最优调度（图注/标题保留限定）。通过。

## 数据口径

- 数值全部来自固定提交实测/登记记录；capacity.csv 6 行为"各方案最大单核官方峰值"汇总口径，
  capacity_detail.csv 保留逐核峰值、静态估计与共享输入静态量细表。
- 未完成项：无。
