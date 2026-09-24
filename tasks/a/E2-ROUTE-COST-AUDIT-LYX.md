# E2 调用路由与官方评价成本静态审计

负责人：@lyx0217，`lyx0217/s-89ad75751f054b6b9929e42d899246be`（本次本人报告 Codex / Windows）。
协调：NikolaStarx 队长；技术接收：E2 专项 `nikolastarx/s-55b66a31d7bd49019122a179563dc1d2`。
沟通：[Issue #15](https://github.com/huaweibei123/huaweicup2026/issues/15)。本卡发布表示已派发，成员确认理解后才记录接手。
分支建议：`codex/e2-route-cost-audit-lyx0217`，从共享 main `1b19960af15fce14c84e8e23f2ea6cff6bd910d0` 建本人独立 worktree。用 `git show <固定SHA>:<路径>` 读取下述旧实现，不把算法分支整体合入报告分支。

1. **任务目标**：为共享并发评估的费用预留提供独立静态证据，查清每条评分/full 路径会调用哪个后端、可能进入几次完整官方 E0，以及哪些成本无法事前确定。不是再跑性能测试，也不接管后端或 Windows 驱动实现。
2. **输入文件**：代码固定 `603b0741e21c449d3db652ebd67c94f2dc014cc9`。最小必读 `research/a/e2_search/P23_HANDOFF.md`、同目录 `engine.py`、`scene_b.py`、`pool.py`、`__init__.py`；按真实调用继续追到必要的 `_full_cli.py`、`_official_b.py`、`_local_b.py`、原生包装和 `src/eval_exact/`。不是要求30分钟通读全部仓库；追不到就列未覆盖。不 import 或执行模块，说明文档里的构建/测试命令在本任务中不执行。公共规则读取上述 main 的 AGENTS 和 `docs/GITHUB_FREE_COLLABORATION.md`。
3. **输出要求**：唯一写区 `docs/a/e2/audit-lyx-20260924/`，交 `ROUTE_COST_MATRIX.md` 和 `route-costs.json`。逐 problem（1/2/3）、score/full、native 开关与实际失败分支列：后端路由；单请求最大可能完整 E0 入口数；是否能在 started 前拒绝自动回退；超时/worker异常或取消竞争时何种成本仅能 unknown；缓存命中跳过或仍执行的步骤；固定文件/函数/行号证据。区分完整官方评价入口和准备阶段调用官方子过程，不能把两者混成同一个计数；区分 caller、worker 与包装层，避免重复计数。JSON 与 Markdown 同口径，未知不填0。附实际已读文件、未读范围、交付提交和复核建议。
4. **限制条件**：首检查点最多30分钟主动工作；E0/E1/E2调用、原生构建、worker/测试启动全部为0。只允许 Git/文件阅读与本任务文档编写，不执行源码、不装依赖。不得修改 `src/eval_exact/`、`src/eval_proxy/`、`research/a/e2_search/`、Fang门禁/驱动或公共文档，不续测封存C/D/E，不用队长凭据、镜像或付费GitHub服务。保留本地既有成果与旧FAST分支。
5. **验收标准**：矩阵覆盖已读实现的直接与间接路由、full/回退/缓存分支；可确定上界的有完整调用链依据，不可证明上界的明确 unknown 和缺口；标出所有发现的无法前置阻止自动回退的边界，不为了“发现问题”编造缺陷。代码哈希/作者报告不当作运行语义证明。技术接收者核对覆盖后再采用到共享调度设计；本任务通过不等于E2终验。
6. **截止与停止**：本人在原Issue确认理解、实际HEAD/写区和可用时间后开始；开始后30分钟给首个检查点（回报使用Asia/Taipei时间）。到点保存已有矩阵与未覆盖项，不自动延长；任何必须执行才知道的项保留unknown，反馈具体问题，不转正式实验。任务完成或无进一步可读证据时停止，等待具体反馈，无需空轮询。

## 交付记录

实际审阅时间与命令、输入SHA、报告提交、覆盖/未覆盖、unknown与建议：由负责人填入独立报告并通过Issue #15交接。

下一步：队长确认成员实际接手；E2专项消费矩阵并回答未知边界。没有新的明确授权，不恢复旧实现写入或扩大实验预算。
