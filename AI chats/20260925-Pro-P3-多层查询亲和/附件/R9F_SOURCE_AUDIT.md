# 实际阅读、身份及未读项

本轮是 R9 同一 session 的第五核续研，不使用另一理论会话的结论。
固定提交：`1f414ad4f086af6c972ec60bb46220ad90318933`。

## GitHub 连接实际读取

仓库均为 `huaweibei123/huaweicup2026`，ref 均为上述 SHA，未使用 Vioano 替代。

- `results/a/q3-nikolastarx/layered-capacity-question-20260926/PRO_BRIEF.md`：全文。
- `src/q3/layered_query_flow.py`：通过 1–260、260–590 两窗口读到全文，包括输入/分解守卫、分组、shared placement、priority_words、interval_certificate、path_stats、traffic_counts、construct_layered。
- `results/a/q3-nikolastarx/layered-fourtrack-frontier-diagnostic-20260926/RESULT.md` 和 `FROZEN.md`：全文；`result.json`：读取到分解、分量归属、负载、峰值等，工具截断了较后 top25 证据，未声称完整读完 JSON。
- `results/a/q3-nikolastarx/layered-shared-core-repair-20260926/RESULT.md` 和 `FROZEN.md`：全文；`result.json`：1–175，路径见证起始部分，非全文。
- `results/a/q3-nikolastarx/layered-shared-split-20260926/RESULT.md` 和 `FROZEN.md`：全文；`result.json`：1–210，包含 after 峰值、贡献排序和部分 before，非全文。
- `data/raw/a/official/code/multicore_cut_evaluate_problem_3.py`、`schedule_step2.py`、`schedule_step3.py`、`src/q3/attention_rows.py`：连接读取文件头和完整 Git blob SHA，再与本地已有全文计算出的 Git blob SHA 比对，四项完全一致。因此下述本地相关行段的阅读确实对应固定提交字节。

## 本地原件实际读取/解析

从当前对话已挂载 `通用神经网络处理器下的多核调度问题  附件.zip` 读取原始：

- `data/case_068.json`：完整 JSON 与全部原边解析，2,080,289 B，SHA256 `dfd9a58ef9d26a8a4567026b50af8b4499d87eebb3d98f8208b909b11e963c6d`，与 brief 相符。
- `data/case_088.json`：完整 JSON 解析、只做分解；未生成 088 计划。1,190,948 B，SHA256 `2ff71575ba33875431f54823fc1f2214e018edcfc9d568edfb7c47b0f264b825`。
- `data/config.txt`：全文，341 B，SHA256 `dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9`，与 brief 相符。
- 官方 P3 文件主要阅读 45–235（桶排序、Task COPY 插入）、310–415（最终P3状态与FIFO装载）、690–716（输出memory_peak来源；这段也经连接实际读取）；Step2 阅读 1–289、300–355、407–437（生命周期、alloc/check/free、后备与 incarnation）；Step3 阅读 118–305、445–535、588–625（实际消费者释放、FIFO credits、allocation_order、四管道顺序与补边）。没有调用这些函数。
- 本会话旧 `p3_r9_delivery/layered_affinity_r9.py`、`SOURCE_EXCERPTS.md`、`R9_REPORT.md` 的构造与容量/无环证明部分；新输入包中的 `src/q3/attention_rows.py` 1–226。

官方代码完整字节还与旧 `p3-r9-layered-inputs(1).zip` 中同名文件一致。
完整 SHA/Git blob 比对保存在 `metadata.json/fixed_file_identity_checks`。

## 运行身份

新候选使用本会话 R9 原型的纯静态 helper；固定提交相应实现已读，但远端原始源码直接下载未成功，未宣称对固定提交 CLI 原样执行。交付包剥离了不需要的 imports/CLI，并保留 reused definitions 的 AST；`helper_AST_identity.json` 记录一致性。源码没有官方导入。

只有一份冻结候选规则：首次静态构造后，打包 CLI 对同一输入作一次确定性回放，plan 字节完全相同。另有独立 incident-count 前沿检查和合成 toy。没有第二归属方案、参数网格或候选排名。曾在候选建立前遇到输出目录 PermissionError，修复权限后继续；没有据此改规则。未运行官方 Task/Step/P2/P3/E0。

## 未读/缺失

- 三份旧探针的 `diagnose.py`/`probe.py` 未读取；JSON 未读取范围如上。
- `rejected-idlecore-extension.patch.gz` 未读取。
- `nonattention-headroom-20260926/REPORT.md` 未读取；不据它做新断言。
- 用户另述的“15 分量迁移且取消全局相位”试验未有独立原件回读，本轮仅视作用户提供的静态事实。
- 没有读取旧 Forest 068 完整 plan、精确 M2/M3 官方 result/trace，历史 M3/G 仅引用 brief/用户陈述。
- 没有新的 prepared Task、Step1 sequence、Step2 spill/incarnation、Step3 内存边、E0 输出、DDR/cache 指标。
- 没有读取/假定另一会话 R10 的答复。
