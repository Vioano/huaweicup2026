# 图 6-2 自查记录（甲，v3，2026-09-26）

## 实际执行结果（本会话为该目录唯一写者，写者声明 5845988314）

- 命令：`.venv/Scripts/python.exe figures/a/jia-fig6-2-20260926/plot.py`（工作目录=仓库根），**退出码 0**；同一次运行产出 figure.svg 与 figure.png（无 tight bbox，画布 6.5×7.8 in，SVG 实测 468×561.6 pt = 165.1×198.1 mm，与源 figsize 设置一致）。
- 脚本内置自检通过：三方案切点各 4 段、有序、首尾覆盖 [0,124]、核 1..4 连续；静态数组键为源索引 0..3（resident modeled [79584,516864,330752,17792]；first_load shared-input [73440,663552,186368,7040]，其中源索引 1 = 663,552 B 断言通过）。

## v3 修订核对（逐项对应 5845867240）

1. **F62-R02 残项（列名）**：capacity.csv 首行改回标准 `variant,space,working_set,capacity,evidence_type`，6 行数值不变（balanced/resident/first_load × L1/UB）；audit.table_columns 同步标准名；含义（各方案最大单核官方峰值，非跨核相加、不证明零 spill）在 caption 说明。plot.py 第 63 行读取的 r["working_set"] 真实存在，运行退出码 0。已完成。
2. **F62-R04（源码混版与索引/单位错误）**：plot.py 全量重写为与成图同源的单一版本——ROWS 顺序=balanced/resident/first_load（图面/图例/caption 统一此顺序）；figsize=(6.5,7.8)、刻度 0/25/50/75/100/124 与源设置一致（SVG 实测 468×561.6pt 吻合）；内部索引一律源索引 0..3，展示核=索引+1（图内"核1..4"）；static_model_res[i] 取源索引 0..3（修复 v2 的 [i+1] 越界与错移）；first_load 静态共同输入以字节保存、绘图时仅一次 B→KiB，取源索引 1=663,552 B → 648 KiB（修复 v2 的重复换算与取到源索引 2=186,368 B 的错误）。由本 plot.py 与提交 CSV 单次运行重导出 SVG/PNG，无旧图混入。已完成。
3. **F62-R01 残项（标注同步）**：L1 分面紫色三角与图例统一为"③ 阶段2（源索引1）静态共同输入 663,552 B（非官方峰值）"；capacity_detail.csv 证据类型后缀统一为源索引 0..3（static_shared_input_stage1 即源索引 1 = 展示阶段 2）；caption 同步"阶段 2（源索引 1）"。图内、caption、细表三者指向同一阶段。已完成。
4. **回归检查（F62-R03 已关闭项）**：新导出无长标题越界、图例独立于 UB 分面、切点 91/95 由各自条带标注（未合并刻度）、容量线与文字无遮挡——本次单次重导出目检通过。

## 数据来源与身份（全部固定提交 7edacdd97a7be36a402af20bc8bfa8a7454dbbe0，哈希见 audit.sources）

- balanced：pipeline-20260924 批次 manifest（cuts [0,28,58,91,124]）+ comparison.json（逐核官方峰值 [19680,430080,473600,22912]、P3=40927）；计划 sha256 44c66c84…（capacity 批次 controls.044 登记，original_commit e6b5500d…）。
- resident：pipeline-capacity-20260925 批次 manifest detail + REPORT.md（官方峰值 [79584,516992,330752,18816]、P3=37581、搬运 121088、spill 0）；计划 sha256 715be4ec…。
- first_load：pipeline-setup-followup-20260924 批次 manifest（cuts [0,41,70,98,124]、stage_compute_cycles [2822,1709,1577,1564]、shared_input_bytes_by_stage [73440,663552,186368,7040]）+ plan（7fdad2c6…）+ P3 result.gz（a12f8762…：makespan 41738、spill 1,622,016、added_copy 1,731,840、逐核峰值 [79584,516992,188160,15744]、hit/miss 1,622,016/1,007,840）。三个原件已抓取并逐一核对审阅方哈希（全部 MATCH）。
- Cache 语义：仅 first_load 有命中；caption 已不出现"三方案命中 0"表述。

## 验收标准逐项

1. 切点有序、完整覆盖、无重叠遗漏（三方案脚本断言）；核归属=阶段（4 阶段对应 4 核固定流水结构，cuts core 1..4=源索引+1），与方案一致。通过。
2. 容量单位（B/KiB）、空间（L1/UB）、工作集定义明确；静态估计（斜纹）与实测（实心/菱形语义即实心柱）分标记；UB=0 注明实测记录。通过。
3. 未借用 044/k5；静态容量满足不证明零 spill 或最优调度（图注声明）。通过。

## 历史稿

v1=59d4cb4b0（首版）；v2=7b07c99b2（并行会话混版，已退回）；v3=本版（唯一写者）。均保留于 git 历史。

未完成项：无。
