# 图 5-4 自查记录（甲，v2，2026-09-26）

## 实际执行结果（v2 返工，针对反馈 5846754015 的 F54-R01..R07）

- 命令（两步，工作目录=仓库根）：
  1. `.venv/Scripts/python.exe figures/a/jia-fig5-4-20260926/extract_inputs.py --r05-zip <S15 result.zip> --s16-report <S16 report.json>`——显式路径参数，两项固定来源 SHA-256 不符即中止，生成五张交付 CSV；本机实测读入的 zip SHA=c90065d9…、report SHA=86347e8a…，均与固定提交（e6ae3699 / 70f2e8bd）登记值一致。
  2. `.venv/Scripts/python.exe figures/a/jia-fig5-4-20260926/plot.py`——只读交付包内五张 CSV 复现图件，退出码 0；同一次运行产出 figure.svg 与 figure.png（300 dpi，6.5×8.0 in，165 mm 版心）。
  plot.py 不读取任何包外文件；不依赖个人隐含缓存。
- 数据完整性断言通过：两方案事件表最晚结束 == 各自官方 makespan（248,166 / 254,508 cycles）；S16 恰 500 格、四类计数 55/199/14/232；两方案 spill=0。

## v2 相对 v1 的修正（逐项对应 F54-R01..R07）

1. **R01 规范化事件/标记**：events.csv 的 `core` 改为接口规范 1/2，新增 `source_core_id` 保留原 0/1，逐行断言 `core==source_core_id+1`；markers.csv 六条（3 kind × 2 variant）全部引用 events.csv 中真实存在的 event_id——makespan_end=end 最大事件（seed 23858 / rec 57557，SUBGRAPH）、last_copy_in_end=PIPE_MTE2 end 最大事件（34227 / 50808）、first_op_start=非 SUBGRAPH 最早 start 事件（并列取最小 event_id：6727 / 40996，cycles=0）；周期数值放独立 `endpoint`/`cycles` 列，plot.py 逐条对事件表核对，不再把周期当事件 ID。
2. **R02 相对变化全精度**：tradeoff.csv 的 relative_ddr 由 round(·,6) 改为完整精度（如 005/k2 = −0.6378792659740218）；380 个非零分母格全部通过 math.isclose(rel_tol=1e-7, abs_tol=1e-9) 复核；120 个旧 DDR=0 格保持空值（绝对量展示），未当作返工错误改动。
3. **R03 总量与额外列分列**：results.csv 的 extra_ddr 改为新增 COPY（added_copy_bytes：5,067,158 / 3,923,290），总量另设 scheduled_copy_bytes 列（6,351,422 / 5,207,554）；bytes.csv 保持 base+extra==total 断言；图中"新增 COPY −22.57%"与"总 COPY −18.01%"分别表述。
4. **R04 热条改真实时间条**：面板 1 弃用 500-cycle 活跃桶热条（v1 把 26,910 个 Task 区间与 40,475 个真实操作混计、每行各自归一化、桶边界规则未定义），改为同轴真实核/Pipe 操作时间条——每方案每核一行，按 PIPE_MTE2/MTE3/V/M 真实 start/end 画条，task（SUBGRAPH）仅作浅灰背景不入计数；零时长事件 0 个（已核），无桶边界歧义；末桶/端点不做外推，端点线即官方 makespan。不称带宽利用率。
5. **R05 裁切/图例/字号**：面板 1 行标签缩短（seed 核1/rec 核1）+ 标题解释全称；全部字号 ≥7.5 pt（图例 7.5、其余 8，165 mm 下可读）；面板 2 图例移右上空白区（柱顶最高 6.35+标签，y>7 无数据）不再盖 seed 总量数值；面板 3 图例移右上（Δcycles≤0，右半轴无数据点）不再遮散点与原点；面板 1 图例置于顶部留白（ylim 扩展），6 项 2 列。preview-insert-width.png 为 165 mm 插入宽度实测渲染，逐面板目检无裁切、无遮挡。
6. **R06 复现依赖**：新增独立提取脚本 extract_inputs.py（随包交付），显式 --r05-zip/--s16-report 参数并核对两项固定来源 SHA-256（不符即中止、不产表）；plot.py 只读交付 CSV；原始 Trace 不复制入图包，ZIP 固定链接保留于 audit.sources。
7. **R07 面板版本标签**：面板 1/2 标题标注"S15 R05 @e6ae369"，面板 3 标题标注"S16 @70f2e8bd（2794ceba→c665）"；完整 SHA 留图注与本 audit sources。

## 缺口

- 无（S15/S16 固定原件哈希核对一致；0 新实验，未重跑 solver/E0/E1/E2）。

## 版本

- v1：初版交付（97dd14fb1）。
- v2：按工作台反馈 F54-R01..R07 修正（issuecomment-5846754015），见上。
