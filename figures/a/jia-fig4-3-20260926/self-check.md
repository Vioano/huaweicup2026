# fig-4-3 self-check（v1，2026-09-26）

## 数据来源与固定版本

- 唯一数据来源：固定提交 `059056ce1ee999e634049e5e5baf72566832effe` 的
  `results/a/q1-yuanzhifang-stage-j/stage-j-20260925/`（control/paced 配对）。
- 原始 Trace blob SHA256（`git cat-file blob | sha256sum` 逐字节计算）：
  - control `e0_trace.json` = `923f0d1fe01220580cf4d762114b1043c5de7c87904a5d6dddcdf9f4120e8963`
    （与该侧 run.json 记录的 e0_trace_sha256 一致，交叉验证通过）
  - paced `e0_trace.json` = `d034f8280e613aa8ed3358af769c7c429f6402eef48630feb35a7ee214560d9b`
- 提取脚本：一次性脚本（命令记录见 audit.command 备注与下方命令），
  读取两侧 e0_trace.json 生成 events.csv / results.csv / markers.csv；plot.py 只读三张 CSV。

```text
# 提取（仓库根执行，读 git show 导出的原字节 trace）
git show 059056ce1ee999e634049e5e5baf72566832effe:results/a/q1-yuanzhifang-stage-j/stage-j-20260925/run/051-k3-control/e0_trace.json > <tmp>/ctl_trace.json
git show 059056ce1ee999e634049e5e5baf72566832effe:results/a/q1-yuanzhifang-stage-j/stage-j-20260925/run/051-k3-paced/e0_trace.json  > <tmp>/paced_trace.json
python <tmp>/extract.py     # 内置断言，任一不符即中止
# 绘图（仅读交付包内三张 CSV）
.venv/Scripts/python.exe figures/a/jia-fig4-3-20260926/plot.py
```

## 已通过的检查

1. **makespan 与官方一致**：trace `otherData.makespan`（291222 / 278618）= comparison.csv
   makespan_cycles；events.csv 中两方案 max(end) 逐一等于各自 makespan（断言通过）。
2. **extra_ddr 与官方一致**：results.csv 取 comparison.csv 的 extra_ddr_bytes
   （9,045,304 / 9,045,350 B），spill 均为 0。
3. **标记值派生可复核**（extract.py 断言）：
   - input_done = 首轮 task 0..2 的 COPY_IN 最晚结束 = 6570（两方案相同；每核 4 条 32KiB 档大搬入）；
   - task_done = task 0..2 区间最晚结束 = 10028；
   - remote_return = 跨核收集 task 3 的 12 条 COPY_IN 最晚结束 = 11040；
   - reduce_tail_start = 末条 task 起点（control 291076 / paced 278472），区间终点 = makespan。
4. **事件表完整性**：events.csv control 2,469 行（96 task + 2,373 操作）、
   paced 2,515 行（96 task + 2,419 操作），与 trace X 事件逐一对应（plot.py 断言操作总数）。
5. **图面检查（165 mm 插入宽度）**：SVG 画布 468 pt = 165.1 mm；最小字号 8 pt
   （≥ 165mm 口径下 min_font 阈值）；面板内无文字/图例遮挡数据；标记说明置于底部图例。
   PNG 以 200 dpi 导出供预览。
6. **口径**：时间一律 cycles；字节一律 B（caption 中 DDR 用 B，不与 KiB 混写）；
   未出现「带宽利用率」「实测 DDR 等待」等禁用表述。
7. **状态真实**：本轮 0 新 solver/Task/E0/E1/E2，仅读取固定提交原件与派生表；
   无缺件（trace/E0 结果/计划身份 run.json 均在 sources 登记哈希）。

## 未完成项 / 待验收

- 视觉与科学结论待工作台 Agent 审查、用户总验收。
- 本图为 case051/3 核单例配对，不与 P1 全量均值混写（caption 已声明）。

## 版本

- v1：初版交付（本目录全部文件，哈希见 audit.json）。
