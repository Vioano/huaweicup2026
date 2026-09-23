# 情况 B 给 yuanzhifang 的启动交接包

2026-09-24，由队长与 A 核心开发会话确认拆分。行动入口：[任务卡](../../tasks/a/Q2-CORE-SEARCH.md)、[Issue #33](https://github.com/huaweibei123/huaweicup2026/issues/33)。本文只携带执行所需上下文，不要求读取队长私人聊天。A 负责人另已发布 [技术交接与准确反例路径](https://github.com/huaweibei123/huaweicup2026/blob/d6bf5c353c1de71ec0e6fafb7be38fd48c9dc12e/docs/a/research/20260924-pro-archive/Q2_HANDOFF.md)；这是本包的技术附件，按固定提交读取。

## 结论与 A/B 边界

**B 可独立开始核心研发，不需要等 A 最优。** 理论上有连续性，软件接口可分开；同一个原始图/方案格式并不意味着相同执行图、成本或可行性。

| 项目 | Q1 / A | Q2 / B |
| --- | --- | --- |
| Task 形成 | 每个子图一个 Task | 同一核心上的子图合成一个 Task |
| 子图顺序 | 同核 Task 顺序与 Task 依赖/等待 | 核内子图优先级稳定分桶，需保持核内拓扑；展开后的 Pipe FIFO/COPY 影响全局执行 |
| 主要等待配置 | 同核/跨核 Task 等待 | 跨核 COPY delay |
| 可执行性 | 数据依赖与同核 Task 链组合图检查 | 本地执行依赖、内存复用边、Pipe FIFO 与跨核 COPY 全局检查 |
| 可复用 | 图/张量关联、结构特征、官方格式、实验记录方法、部分候选思想 | 按同一输入复用，但每个推导与收益都重新核对 Q2 适用条件 |
| 不直接移植 | A 的 Task 屏障模型、cover 合并收益或 P1Evaluator | 自己调用冻结 Q2 E0；不把核归属不变或纯计算词相同当作完整执行等价 |

该表根据冻结 README、`multicore_cut_evaluate_problem_2.py` 的 `_prioritize_task_seq` / `_build_scene_b_tasks` 和全局校验整理，不是完整形式化证明。B 先对“相同核心归属、不同子图优先级/粗细”做最小对照；构造之外的源码调度语义不要另行发明。

## 固定材料清单：只读 main 不够

所有资料已在**组织主库**的 main 或已发布分支；队友无须 ChatGPT 网页登录或 Vioano 权限。需要的是本交接索引和固定版本，不需要另发一套未经版本控制的压缩包。尚未合入的研究/实现保持独立读取，不为拿资料把整个研究分支合进自己的代码。

| 材料 | 固定 SHA / 入口 | 使用边界 |
| --- | --- | --- |
| 公共规范与冻结官方材料 | `cd5ef2b8a9f3518579167bf8a9271d6a76403b30`；当前任务卡/本文则以派发评论指定的新提交为准 | `AGENTS.md`、`docs/TEAM_WORKFLOW.md`、`docs/SESSION_PROTOCOL.md`、`docs/a/CAPTAIN_RESOURCES.md`，再读题面/官方 README、Q2/config/Step1–3/validation |
| FORM 规则与固定件 | `65d6c0e6facee2ec8ce9694c30dd805de99abf7e`，分支 `a-r1-farmeruncle123`，PR17 | `formal/SPEC.md`、`rules.jsonl`、`ambiguities.md`、`tests/adversarial/README.md`；仍非全部终验，按规则版本与 Q2 范围核对 |
| FORM 的定点独立复核 | `e1575a1de5e3b921aef350e920720f0584fb1719`，PR28 历史固定点 | `results/a/review/q1-form-65d6c0e/REVIEW.md`；先核勘误，再使用旧规则。Q1 探针不能直接改标签算 B 验证 |
| 四路 Pro 原物、源码、报告和勘误 | `3a4505d4101e23d54580d15560da3820e02d05da`，分支 `codex/q1-core-prototype-20260924`，PR31 | [固定入口](https://github.com/huaweibei123/huaweicup2026/blob/3a4505d4101e23d54580d15560da3820e02d05da/docs/a/research/20260924-pro-archive/README.md)，研究作者报告，不等于队内复现 |
| A 构造与预算搜索 | 初版 `3a4505d`；最新实现/五例证据 `d2e60539417f92803e9796dcd68b6e21173fafdf`；技术交接 `d6bf5c353c1de71ec0e6fafb7be38fd48c9dc12e`，分支 `codex/q1-bounded-search-20260924`，PR34 | `src/q1/search.py`、`docs/a/Q1_SEARCH.md`、研究目录的 `Q2_HANDOFF.md`；只作参考。mapping 插入顺序不能未经证明从去重键中丢掉；A 数值不当成 B 成绩 |
| P1 精确批量接口 | `5bfe53a29c1ba05167239f51ea937e602f7f85b4`，PR30 | `docs/a/exact/P1_BATCH.md` 仅用于理解边界；它不支持 Q2，不是 B 启动前提 |

最短阅读顺序：任务卡和本表 → 官方题面/README/Q2 源码 → FORM 定点复核/勘误及实际相关规则 → Pro 短索引与勘误 → 技术附件中的准确反例与候选源码。共同契约 `contract-v1.md` 和 `EVALUATOR_AMENDMENT_20260923.md` 同时核对。长历史 `AI chats/` 可按问题补读，不要求先吞下所有私人讨论；研究原话不扩大授权。

有干净目录时可建立独立阅读 worktree（下列目录已存在则核对并复用，不覆盖）：

```sh
git fetch origin main codex/q1-core-prototype-20260924 codex/q1-bounded-search-20260924 a-r1-farmeruncle123 codex/q1-form-review-20260923
git worktree add --detach ../huaweicup-q2-research-read 3a4505d4101e23d54580d15560da3820e02d05da
git worktree add --detach ../huaweicup-q2-form-read 65d6c0e6facee2ec8ce9694c30dd805de99abf7e
```

开发 worktree 从派发评论指定的任务包提交建 `codex/q2-core-yuanzhifang`；已有分支先报告实际 HEAD/改动，不重建、不清空。首次实质回复同时确认自己实际取到哪些 SHA，不能用 fetch 成功代替已读。

## 官方格式与 Q2 冒烟命令

以下在自己的任务工作区执行；示例输出目录必须未占用，每轮换新目录。官方 stub 只是随机格式示例，随后另做明确的确定性构造作为比较基线。所有原件保持只读。

```sh
uv sync --locked
uv run python -B scripts/a_materials.py --extract
uv run python -B -c "from pathlib import Path; Path('results/a/q2-yuanzhifang/smoke-001').mkdir(parents=True, exist_ok=False)"
uv run python -B data/raw/a/official/code/stub_multicore_cut_and_schedule.py data/raw/a/official/data/case_002.json -n 4 --seed 0 -o results/a/q2-yuanzhifang/smoke-001/plan.json
uv run python -B data/raw/a/official/code/multicore_cut_evaluate_problem_2.py data/raw/a/official/data/case_002.json results/a/q2-yuanzhifang/smoke-001/plan.json --config data/raw/a/official/data/config.txt -o results/a/q2-yuanzhifang/smoke-001/result.json --trace-output results/a/q2-yuanzhifang/smoke-001/trace.json --log-output results/a/q2-yuanzhifang/smoke-001/run.log
```

若候选被 Q2 拒绝，保存完整错误与环边；若超时则单列，不能改参数/真值来换取“成功”。算法产物保持官方 `node_to_subgraph` / `core_schedules` 方案格式，额外诊断单独保存，不强改公共输入输出。

队长已在独立工作区实际跑通以上命令：Python 3.12.13/macOS，114 原件与 100 cases 校验通过；case002、4 核、seed0 的随机格式示例经官方 Q2 得到 200352 cycles。[冒烟回执及输出哈希](Q2_HANDOFF_SMOKE.json) 只证明这条起步路径在该环境可运行，不是新算法成绩、成员本机复现或跨平台验收。

## Pro 线索与反例导航

以下路径均相对 `3a4505d` 阅读工作区。完整 archive 约 292 MB；先读小索引/文本，按需要解包所选证据，按 manifest 核验。已取得字节不代表数学/实验已验收，旧 295 份历史 result 仍缺失。

1. `docs/a/research/20260924-pro-archive/README.md`、`PRO123_ERRATA_SUMMARY.md`、`PRO4_FOLLOWUP_REVIEW.md`：先读使用边界和未闭合勘误。
2. `results/a/pro-research-20260924/reports/pro1-r3/RESEARCH_MEMO.md`：串行包与窗口/阶段细化；报告 case002 Q2 的收益，但 case044 更大窗口可退化。不把理想计算矩阵当完整含 DDR/spill 的真值。
3. `results/a/pro-research-20260924/reports/pro2-r2-prototype/RESEARCH_MEMO_ROUND2.md`：子图优先级驱动资源词/阶段交错；case008、044 是可复跑线索。过密交错可能反增 spill；商图无环不等于展开后无等待环。
4. `results/a/pro-research-20260924/reports/pro3-r2/REPORT.md`：完整执行词及次序边界。仅计算词相同不足：COPY_OUT/FIFO 次序会改结果；浮点事件结算重排可出现 1 cycle 差异。不是允许容差的理由。
5. `results/a/pro-research-20260924/reports/pro4-followup/RESEARCH_REPORT.md`：内存压力/无 spill 充分条件的候选思想。初稿“充要”等说法已受勘误限制，最终审计仍未闭合；定理应用逐条对条件，不强制神经网络。

可先复跑第三路 `pro3-r2.tar.xz` 内 `route3_round2/results/counterexamples/head_blocking/`（`graph.json`、`plan_0.json`、`plan_1.json`）与 `fork/`（`graph.json`、`plan0.json`、`plan1.json`）；准确包路径、浮点反例、Pro2/4 源码入口均见技术附件。先审查脚本和依赖，再在自己的目录解包与执行；官方 Q2 逐计划输出为本机依据。

以上是候选搜索空间，不是必须实现的名词清单。优先让实际 E0 小实验区分“归属收益、优先级收益、搬运/内存变化”，再选有证据的方向深入。若发现更强路线可自主替换，并说明比较依据。

## 如何协同

- **各自单写**：A 会话负责 `src/q1/`；yuanzhifang 负责 `src/q2/` 等任务卡列出的范围；共享精确 evaluator 留给现有实现者。不要直接 import 另一个未冻结工作区的可变文件。
- **共享候选与知识**：交换官方格式计划 JSON、固定 graph/config/代码 SHA、单条复现命令、完整结果与具体反例。需要共用工具时先定义输入输出和归属，再由队长整合小 PR，不为去重立即重构 A/B 全部代码。
- **交叉复核**：第一可跑检查点后，A 会话对 B 固定样例独立调用 Q2，B 对约定 A 固定样例调用 Q1；每次队长路由具体提交/范围与预算，不自动启动无边界复核，也不把参考过的代码审查称作盲审。
- **通信**：B 进展都在 Issue #33，引用固定证据与 `session/to/task`；A/B 可以在本 Issue 直接讨论技术问题，队长协调公共决定和其他本地会话。无实质变化不互发空 ACK。
- **Pro/算力**：队长有相关账户的授权，本地数学工具/Colab 是可选资源。B 交待证命题、已知条件/反例、可运行最小输入和预算；队长代问/代跑，结果以主库固定文件返回，不把网页或镜像权限当作队友已有。

没有必须等待的 A 算法硬依赖；真正共同的依赖是冻结语义和官方数据。B 的候选构造可现在开始，后续按实测瓶颈决定是否值得另提 P2 评估加速任务。
