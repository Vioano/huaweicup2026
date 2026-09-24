# 三问 seed 的实际适用域与缺口

**逐固定源码静态阅读；0 运行。** “接受某输入参数”不等于“该域都能产出可执行计划”；三者均未在本轮证明覆盖 100 图 × 1～5 核。下表只列源码事实与接入要求，不增加已验收范围。

| seed / 固定入口 | 实际构造与支持条件 | 已有验证/失败/回退 | 控制层的最小接法及缺口 |
| --- | --- | --- | --- |
| P1 `search.py`，`4dff90ef699fd51845cf482951e8477066f5f566` | CLI 要求正核数，无显式限定 1～5；使用仓库官方固定 config。官方随机 stub、可选历史 seed、single、chain、component、fixed64 及父计划编辑组成候选流；结构构造不等于全域安全 seed。[入口][p1proposal] | `derive_multicore_plan + validate_task_order`；搜索要求精确 evaluator checkout 为干净 `5bfe53a29c1ba05167239f51ea937e602f7f85b4`。proposal 失败/超时继续，评分 non-ok 也不终止整轮。E1 更低分就先写 `best_plan.json`；最终 E0 只在 summary 检查 Makespan 一致，失败不撤回此前 checkpoint。[控制流][p1search] | 先接 proposal 边界，冻结计划后单独取得精确接受证据；不能把整条 search CLI 的 checkpoint 直接当 confirmed I。单核和官方 stub 都没有源码层面的“必成功”证明。若改为首意外失败锁范围，属于新停止策略，不能称完全复现旧算法。 |
| P2 `contiguous_plan`，`0b58c123cccf02fc993b741d79dcd8511e4dd38f` | 正核数、官方有效 graph；去掉/收缩 COPY 关系后，按 min-ID ready 的 Kahn 拓扑顺序，将 `max(1,Cycles)` 累计权重连续分段；每个被用 core 一个子图，允许空核。[完整入口][p2] | 检查 cycle，再 `derive_multicore_plan`；没有 P2 事件模拟、容量/执行通过保证、性能选优或备用构造。CLI `open('x')` 拒绝覆盖，但没有原子临时文件发布。[构造与 CLI][p2] | 作为从图直接构造的 proposal，再用 P2 精确执行确认。不要把它和 Fang 已保存的 M1/M2 强 seed 或本机历史改进实验混作同一生产算法。失败时只有旧 I 可保留；无 I 就报告缺口。 |
| P3 `solve.prepare/select`，`a4e7ee13310d693ec4fb5cc236669ceb3b172d1f` | 正整数核数、官方 graph 校验、收缩 COPY 后 topo/弱连通分量；whole-component 管线负载分核。严格同构 M–V…V–M 链且 `b≤2a` 走 resource_word；其余由指定 guard 异常转 affine_eighth。[结构 guard][p3guard] | 只捕获 `UnsupportedStructure` 来换构造；Index/build/拓扑/官方执行异常不再回退。CLI 使用固定官方 config 做一次 P3 E0；成功才写 full evidence 和最终计划。没有失败后第二个 seed。[选择及验证][p3solve] | 最接近单候选确认后发布的入口，可保留这个低开销路径；接共享资源许可/receipt 和输入表示绑定即可，不强制先 E2 再 E0。其 affine 是结构回退，不是任意输入上的成功证书。 |

## P1 必须显式计算的成本与证据

`place_by_local_duration` 调用官方 `_build_scene_a_tasks`，包含每 Task Step1、spill/Step2、Step3 准备及局部 makespan，再估计分核完成时间。它并非单纯图遍历，也不是完整全局 E0 调用；两者要分别计数/计时。[prototype 55–77][p1local]

该放置函数还断言所有 predecessor task ID 小于当前 ID，不能将任意编号的结构直接传入并宣称已支持；不满足时是候选构造失败，需要保持失败证据。

当前 search 的预算守卫预留 proposal + worker startup + 一次评分，没有把末尾 best 和 baseline 两次 E0 合进同一个搜索 budget；`total_seconds` 自 search 函数开始计，也不含解释器/模块导入前开销。新端到端契约不能拿这个 search timer 直接充当冷启动完整耗时。[search 143–145、193–214][p1search]

`known_seed` 只复制提供的文件；此前生产该 seed 的工作不是本次从图构造已完成。`plan_key` 保留 mapping 插入次序；重复跳过不能升级为“重编号/排序后也等价”。从 search 拆出控制层会改变预算和确认行为，需要新算法版本；旧实验结果仍留在原版本下。

## P3 guard 的精确范围

`word_descriptor` 要求每个弱连通分量：至少 3 个 op；首尾均为 M、中间全 V；拓扑相邻 op 间存在直接边；首尾 M 时长相等；各分量完整 duration tuple 相同；`b=sum(V时长)≤2a`。时长取 `max(1,Cycles)`，`h=1+ceil(b/a)`。[construct 82–126][p3guard]

resource_word 添加资源顺序边后仍做拓扑检查；build 输出 singleton 子图并检查 derive。该资源 DAG guard 不证明 DDR、容量、真实 FIFO Cache 下的成绩或全部合法性。affine_eighth 也需官方复核。[construct 128–184][p3build]

现 CLI 在内存 plan 上调用 E0 后序列化，receipt 含 graph/config/plan/result hash，却未包含共享 operation/祖先预算/逐字段准入。接入时核清 Python 输入与最终 JSON 的类型/顺序关系，不能由“已有 hash”推出共享契约已满足。其 `publish_new` 用同目录临时文件和 hard-link 原子创建、拒绝覆盖；未 fsync，不声称掉电持久性，文件系统不支持 hard-link 可失败。[solve 36–93][p3solve]

## 接入前必须保留的未决项

- 任一种 seed 在全图域 1～5 核、固定配置下的成功率/首解最坏时间，本次均未测；“计划可生成”“官方可执行”“质量不错”“限时可完成”分列。
- 公共包装器需要显式拒绝不同 config/context 的证据复用。P2 构造本身没有 config 参数，只能说明忽略硬件配置的候选生成，不能因此宣称支持任意配置。
- 安全退出取决于已有 confirmed I 及落盘资源。全部 seed 失败时，当前源码没有可直接继承的通用保底；需后续构造证明/授权测试，不能先在文档中承诺全域。
- 追加空核、跨核重排及 Q2→Q3 移植都是新候选上下文；不继承旧分数/合法性，不用 Q2 排名硬剪 Q3。
- 三者历史运行证据和本轮静态事实分开。本轮没有创建新成绩、全域测量、故障实验或任何接口实现。

[p1proposal]: https://github.com/huaweibei123/huaweicup2026/blob/4dff90ef699fd51845cf482951e8477066f5f566/src/q1/search.py#L25-L96
[p1search]: https://github.com/huaweibei123/huaweicup2026/blob/4dff90ef699fd51845cf482951e8477066f5f566/src/q1/search.py#L117-L235
[p1local]: https://github.com/huaweibei123/huaweicup2026/blob/4dff90ef699fd51845cf482951e8477066f5f566/src/q1/prototype.py#L55-L77
[p2]: https://github.com/huaweibei123/huaweicup2026/blob/0b58c123cccf02fc993b741d79dcd8511e4dd38f/src/q2/construct.py#L14-L74
[p3guard]: https://github.com/huaweibei123/huaweicup2026/blob/a4e7ee13310d693ec4fb5cc236669ceb3b172d1f/src/q3/construct.py#L51-L126
[p3build]: https://github.com/huaweibei123/huaweicup2026/blob/a4e7ee13310d693ec4fb5cc236669ceb3b172d1f/src/q3/construct.py#L128-L184
[p3solve]: https://github.com/huaweibei123/huaweicup2026/blob/a4e7ee13310d693ec4fb5cc236669ceb3b172d1f/src/q3/solve.py#L21-L93
