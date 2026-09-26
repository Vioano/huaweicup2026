# fig-4-3 self-check（v2，2026-09-26）

## 数据来源与固定版本

- 唯一数据来源：固定提交 `059056ce1ee999e634049e5e5baf72566832effe` 的
  `results/a/q1-yuanzhifang-stage-j/stage-j-20260925/`（control/paced 配对）。
- 原始 Trace blob SHA256（`git cat-file blob | sha256sum` 逐字节计算）：
  - control `e0_trace.json` = `923f0d1fe01220580cf4d762114b1043c5de7c87904a5d6dddcdf9f4120e8963`
    （与该侧 run.json 记录的 e0_trace_sha256 一致，交叉验证通过）
  - paced `e0_trace.json` = `d034f8280e613aa8ed3358af769c7c429f6402eef48630feb35a7ee214560d9b`
- **复现方式（v2）**：交付包内三张 CSV（events / results / markers）即完整绘图输入，
  直接使用已交付的三张 CSV 复现图件；plot.py 不读取任何包外文件，内置断言
  （结果表官方值、事件表核编号规范化、markers 引用逐条核对），任一不符即中止。
  一次性提取脚本未随包交付，其产出已由上表与断言固化，不再提供占位命令。

```text
# 绘图（仓库根执行，仅读交付包内三张 CSV）
.venv/Scripts/python.exe figures/a/jia-fig4-3-20260926/plot.py
```

## 交付表口径（v2 变更）

- **events.csv 核编号规范化**：`core` 列为接口规范的 **1/2/3**；新增 `source_core_id`
  列保留原始 Trace 的 0/1/2。plot.py 逐行断言 `core == source_core_id + 1`（逆映射可还原），
  原始 Trace 不改动。
- **markers.csv 五类标记全部引用真实事件**：`event_id` 均为 events.csv 中存在的事件 ID，
  周期数值在独立 `cycles` 列（`endpoint` 列指明取该事件的 start 或 end）；
  `first_round` 另附 `range_start=0 / range_end=11174` 说明首轮底色范围。
  plot.py 逐条到事件表读取 start/end 与 cycles 核对，不从 event_id 字符串解析数值。

## 已通过的检查

1. **makespan 与官方一致**：trace `otherData.makespan`（291222 / 278618）= comparison.csv
   makespan_cycles；events.csv 中两方案 max(end) 逐一等于各自 makespan（断言通过）。
2. **extra_ddr 与官方一致**：results.csv 取 comparison.csv 的 extra_ddr_bytes
   （9,045,304 / 9,045,350 B），spill 均为 0。
3. **标记值引用可复核**（plot.py 断言，逐条对事件表）：
   - large_input_done = `COPY_IN##1433` 的 end = 6570（同值另有 ##1441/##1449）；
   - source_task_done = `task#0` 的 end = 10028（同值 #1/#2）；
   - remote_return = `COPY_IN##1465` 的 end = 11040（task 3 的 12 条 COPY_IN 最晚一条）；
   - reduction_start = control `task#95` / paced `task#118` 的 start = 291076 / 278472；
   - first_round = `task#3` 的 end = 11174，范围 [0, 11174]。
   五类 kind 在两方案下齐全（10 行），每个 (variant, event_id) 均可在事件表找到。
4. **事件表完整性**：events.csv control 2,469 行（**96 task + 2,373 操作**）、
   paced 2,515 行（**119 task + 2,396 操作**），与 trace X 事件逐一对应
   （v1 自查此处误写 paced"96 task + 2,419 操作"，v2 已更正；plot.py 断言操作总数 2373+2396）。
5. **图面检查（165 mm 插入宽度）**：SVG 画布 468 pt = 165.1 mm；最小字号 8 pt。
   v2 相对 v1 的视觉修正：左边距 0.085→0.115（核/Pipe 行标签完整不再被画布截边）、
   归约尾标签改为面板内引线式（文字与引线完全在面板内，不越右边界、不压放大面板）、
   删除与面板标题重叠的面板内 makespan 重复标注（标题已含该值）。
   preview-insert-width.png 为 165 mm 插入宽度实测渲染；标记数值仅出现在底部图例。
6. **口径**：时间一律 cycles；字节一律 B（caption 中 DDR 用 B，不与 KiB 混写）；
   未出现「带宽利用率」「实测 DDR 等待」等禁用表述。
7. **状态真实**：本轮 0 新 solver/Task/E0/E1/E2，仅读取固定提交原件与派生表；
   无缺件（trace/E0 结果/计划身份 run.json 均在 sources 登记哈希）。

## 未完成项 / 待验收

- 视觉与科学结论待工作台 Agent 审查、用户总验收。
- 本图为 case051/3 核单例配对，不与 P1 全量均值混写（caption 已声明）。

## 版本

- v1：初版交付（fixed commit 5b9541d21…）。
- v2：按工作台反馈 F43-R01..R04 修正（issuecomment-5846753317）——
  R01 core 规范化 + source_core_id；R02 markers 五类 kind 引用真实事件 ID + 独立 cycles 列；
  R03 边距/归约尾遮挡/标题重叠修正；R04 self-check 计数更正（119+2396）、
  audit.command 改纯命令（说明移 command_notes）、删除占位提取命令。
