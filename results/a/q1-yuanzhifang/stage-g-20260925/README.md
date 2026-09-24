# Stage G：051/k5 整链根核预取，准备阶段

新族 `q1-guarded-intact-prefetch / fixed-root-four-two-v1`，作者固定 `e29685da0268420f2d881246603763d6bf8baf5b`。只准备这一个真实单格，没有求解、评分或Task编译，F预算保持封存；完整零评分身份预检后仍需父审阅与START。

固定构造假说：首轮12条四节点重链按3/3/2/2/2分配，之后4/2/2/2/2，独立归约尾固定核0；预计144 Tasks，计算+Task门控模型R208152。保留大tensor链并利用根核可早900周期启动是否改善实际DDR时间线，必须经过官方E0证伪，不能由模型值预言胜负。

本轮新授权至多1solver+1E0，1worker，30/90秒、全批180秒、0retry/E1/E2。等待父审阅runner与明确START；不自行抢窗口。旧C051/k5的253856周期和9438614B调度搬运只引用 `88e95e28f6b6fdfe7e4d0b91a7b124740dc5006a` 原件，不重跑。

任务六字段见 `tasks/a/q1-yuanzhifang-stage-g.md`。本目录只含准备文档，`run/`尚未创建；后续必须独立首次创建、保留全部正负结果和失败、分别记录cold solver wall与外部E0wall。标准feed仅在实际尝试后生成；source/runner/输入/官方byte哈希、完整原件与固定Git预检保全，不直接写中央服务。

[零评分预检收据](preparation-checks.json) 已通过：5算法源码依赖、10官方源、051/config及旧C原件固定字节；AST语法与旧计划静态DDR分析通过，0solver/E0/Task compiler、0全图扫描。准备耗时19.948239秒包含硬件清单，不是算法性能。父审阅与明确START仍是下一步，未执行本轮预算。
