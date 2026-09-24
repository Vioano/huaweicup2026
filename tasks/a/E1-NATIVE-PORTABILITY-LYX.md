# E1 原生后端接入：可移植加载与回退首增量

负责人：@lyx0217；session `lyx0217/s-89ad75751f054b6b9929e42d899246be`。沟通 [Issue #15](https://github.com/huaweibei123/huaweicup2026/issues/15)。这是原 E1 工程任务的分阶段续接，静态路由审计已完成。

1. **任务目标**：把已有 P1 native 原型的硬编码 `.so`/macOS 构建假设隔离为明确的后端接口，提交最小可审查代码增量与回退设计。优先让正式 E1 保持可用；本阶段不宣称 Windows 已运行、全量零差分或 ≥3×。
2. **输入文件**：固定原型 `03f02e79de4b4bd6f55241385664b154f4332454` 的 `research/a/native-replay-20260924/{HANDOFF.md,README.md,replay_api.py,probe.py}` 及 `src/eval_exact/`、`tests/eval_exact/`。这是在 P1 batch `5bfe53a29c1ba05167239f51ea937e602f7f85b4` 上的后续提交。已读原件可以沿用，注明范围即可。可只读参考 E2 `603b0741e21c449d3db652ebd67c94f2dc014cc9` 的 `research/a/e2_search/{build_native.py,_native.py}`，不可接管修改。公共规则使用 `d6ee2cdc75f2d9e0168f72109b314e11346830b5` 的 AGENTS 与免费协作规范。
3. **输出要求**：从 03f02e7 新建本人 `codex/e1-native-portability-lyx0217` 分支/worktree，保留旧 PR20。唯一生产写范围仍为 `src/eval_exact/`、`tests/eval_exact/`；另可写 `docs/a/e1/native-portability-lyx-20260924/`。首增量包括后端发现/显式加载接口、缺失或不支持时回到现有 E1 的清晰控制流，以及未运行的针对性测试与短交接。正式默认路径保持现有 E1；实验后端显式启用，不能 import 时自动编译/加载任意动态库。记录原型 ABI、来源/构建参数/目标平台与产物身份的校验方案；旧 `.so` 不能当 Windows 产物。完整 prepared 不可变 handle、缓存失效和完整输出语义先给接口边界，不要求本次全部实现。
4. **限制条件**：只做源代码增量与静态审查；本阶段不编译、不 import/执行目标模块、不启动评分、worker 或 E0/E1/E2 测试，不安装依赖/工具链。允许普通文本、AST/JSON、diff/hash 检查。原型 C++、冻结 E0、P2/P3、E2 CLI 修复及 Fang 验证驱动均不改。不能把未知 ABI、非法输入或真实内部错误统统吞成成功；明确区分后端不可用/Unsupported 与输入非法，沿用正式 E1 的输入检查和异常行为。数值、事件、同 tick 顺序与 binary64 不改；不引入 fast-math。若安全增量必须越界，提交具体冲突与最小替代，停在接口/草案而不扩范围。
5. **验收标准**：固定提交/Draft PR、变更全文与来源对应、默认 E1 路径不变、后端选择和回退原因可审查，逐项列 Windows/macOS 未验证项。给出下一阶段最小验证矩阵及真实启动/潜在完整评价/时间与内存预算；既有 9-plan/64-candidate 不能默认为本轮许可。正式 E1 最终仍需完整 JSON 零差分及 ≥3×E0，原型内核倍数不能代替。首增量通过静态审查也不代表 E1 终验。
6. **截止时间**：先在原 Issue 回报实际接手、已读范围、分支 HEAD 与任务理解；从本人实际开始计 30 分钟给首检查点（Asia/Taipei）。约 60 分钟内提交可审查最小增量或具体阻塞后停止，若预计不能完成先交已有成果，不循环空耗、不自动延长。离线不算已开始；公开交付后等待具体复核/验证触发。
