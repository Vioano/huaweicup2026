# 图 6-6 自查记录（甲，v1，2026-09-26）

## 实际执行结果（本会话为该目录唯一写者，开工回执 5847410262）

- 命令（两步，工作目录=仓库根，退出码 0）：
  1. `.venv/Scripts/python.exe figures/a/jia-fig6-6-20260926/extract_inputs.py --audit-json <021 audit.json> --p2-result-gz <P2 result.json.gz> --p3-result-gz <P3 result.json.gz> --p3-plan-json <case_021_multicore_res.json>`——显式路径参数，五项固定哈希核对（audit e50a97d7… / P2 gzip e7b6d54d… / P3 gzip f6e460a7… / plan 13362774…，audit 内 official_result_sha256 与 P2 gzip 同值交叉验证），不符即中止不产表，生成三张交付 CSV。
  2. `.venv/Scripts/python.exe figures/a/jia-fig6-6-20260926/plot.py`——只读交付包内三张 CSV 复现图件；内置断言（两端 makespan 2,140,720/2,140,863、+143、8,881 对齐、变化数 7,485/7,808/2,392 与 audit 一致、movement 五字段相等、全部条形终点 ≤ 各端 makespan、关键事件坐标与 audit 逐一相等）。

## 逐项对应派发单（5847356866）

1. **两端 plan hash 一致与固定配置**：plan SHA 1336277457…（P3 原件 case_021_multicore_res.json 实算 == 配对摘要 source_plan_sha256）；P2 为同字节复用拷贝（gzip 原字节 e7b6d54d… 与旧 c2 配对摘要一致）；两端 scene=B、3 核、P3 read_only。计划身份由 audit source 绑定记录。
2. **按真实操作 ID 匹配、不平移**：8,881 条操作按 (core_id,task_id,op_id) 对齐，身份/op/pipe 零错配（extract 断言）；全部事件 start/end 直接取自两端 per_core_timeline 原件，对齐表 aligned_ops.csv 含 start_diff/end_diff/duration_diff，不平移任何事件。
3. **相同核/Pipe 行序两个配置时间线**：面板 1（P2）/面板 2（P3）均为 3 核 × 4 管道 12 行，行序完全一致（核1/2/3 × MTE2/M/V/MTE3 自上而下）；12 行行序由同一 ROW_KEYS 常量生成，不会漂移。
4. **两个局部放大窗口同一绝对范围**：窗口 1 [4,900, 7,000]（首次命中相关变化——op 1000004905 命中 17cy vs P2 207cy、op 1000006255 起点 5,163→4,973）；窗口 2 [443,050, 443,250]（后续 DDR 读取变化——op 1000006089 同起点 443,077，P2 69cy / P3 138cy 走 DDR）。每行上半 P2（灰）、下半 P3（橙），命中操作绿色；标注文字与图例分层置于面板顶部留白，引线指向真实事件位置。
5. **全局负收益保留**：面板 2 标题明示"+143 cycles，CacheGain 0.99993（非单调）"；未隐藏、未裁剪末端退化。
6. **图注证据范围**：caption 仅写"事件观察"，明确同起点变慢与 Cache 改变交错/共享 DDR 相容但非完整因果链；搬运字节不变（五字段相等断言通过）；单格不外推 500 格/真机。
7. **操作对齐表**：aligned_ops.csv（8,881 行 × 17 列）随包交付；key_events.csv 记录 5 个关键事件（两 makespan 端点、首完成差异、首开始差异、同起点变慢）；summary_metrics.csv 记录全部数值身份（makespan/CacheGain/变化数/movement 五字段/cache 六项统计）。

## 图面检查（165 mm 插入宽度）

preview-insert-width.png（624px）目检：两全量面板行标签完整、图例位于顶部留白不压条形、makespan 端点线可见；放大面板标注文字与图例分层（图例右上竖排、标注左上）、引线指向真实事件位置、核 3 MTE2 行可见绿色命中点（17cy）与灰色 P2 条（207cy）对比；面板 4 可见 443,077 同起点两色条（69cy vs 138cy）。PNG 300 dpi 局部放大复核两处窗口。

## 缺口

- 无（五项固定哈希核对一致；0 新 solver/Task/E0/E1/E2，未重跑任何官方评价）。

## 版本

- v1：初版交付（本目录全部文件，哈希见 audit.json）。
