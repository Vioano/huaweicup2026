# R7 044 静态初审（未执行构造）

范围：只读归档的 `R7_OUTPUT_UNEXECUTED_CONSTRUCTION.md`、`R7_OUTPUT_results__STATIC_AUDIT_FINAL.json`、`R7_OUTPUT_SOURCE_EXCERPTS.md` 和输入包 `output/p1-r7-shared-input-20260925/P1_R7_shared_input_static_20260925.zip:case044/case_044.json`。归档三件 SHA-256 依次为 `da049d5d008811398ee87f0138176d0a2be52e8b82dcc8a7ea03959c28851f2f`、`0d79a50ef0ce006eef6ebc0f8b80566cc9f45b6272b81b4ee8e8c26eeeba0275`、`189bbccef95658d14a2a508ed813e8fd9e4e7bf34eef54d1ec44bca18b123370`。独立原图解析数字见 [static-checks.json](static-checks.json)。无作者代码执行，无新 plan、Task 编译、response 或 E0/E1/E2 调用。

**成立的静态前提。** 原图计算节点为 11 个互不相连的 124-op 组件；按各组件原 ID 的零基秩检查到 1,617 条计算边，跨组件或非前向边为 0；全部原 tensor 的生产者最多一个。因而若 R7 严格按原秩连续切为前缀、A、B、后缀，同阶段的不同组件无计算依赖，所有跨 Task 计算边只会走向更晚阶段。外围核顺序“前缀→后缀”、聚合核“A→B”也按阶段上升，故**在所声明的切片/核序及覆盖下**联合数据边与核序边无环；跳跃残差仍须保留直接的跨 Task 数据边。rank 是合法性证书，不等于全局同步 barrier 或执行时间证明。

**独立字节复算。** 50 个共同外部输入 tensor 合计 930,400 B，与作者一致。代表组件在四个固定切片之间恰有六个跨片 tensor：2048/1024/512 B 各一写一读，256 B 前缀残差一写两读，128 B A→B 一写一读，256 B B→后缀一写一读；合计每组件 8,704 B，11 组件为 95,744 B。这里依据原 tensor 生产/消费集合及官方 `input_boundary/output_boundary` 条件，不把同核的 A→B 数据免除 COPY。作者总 COPY 1,712,000 B 还包含外围共同输入/私有输入及输出；本初审独立确认了共同输入与六项内部 cut，**未**独立复算总 COPY 服务 28,745 cycles 或全部 Task 边界。

**容量证书的限度。** 对固定切片逐一取原图中被 Task op 接触的 managed tensor 并集，10 片 L1 总足迹分别为前缀三组三组件各 254,688 B、二组件 206,560 B，A 全 11 组件 505,984 B，B 260,096 B，后缀三组三组件各 262,272 B、二组件 209,280 B；UB 均 0。最大 A 距 524,288 B 容量余 18,304 B。按官方 P1 的边界插 COPY 而原 tensor 在 Task 内仅保留一份、且原图无内部 COPY 的限定，总 managed 足迹小于容量是免于 Step2 spill/Step3 MEM 回收的充分上限；它不证明固定 FIFO 的调度、Task 编译过程或 E0 成绩。若后续实现产生额外片上 incarnation、改变切片或未保持唯一生产者，须重新核证容量。505,984→582,528 的下一列贪心切口数值本次未独立复算。

**待核与最小下一步。** R7 是未执行规范，尚无可提交两键 plan；目前不能认领合法性、无 spill、64,624 以下 Makespan 或全量收益。下一步应先由实现者生成唯一候选，并独立核对覆盖、10 Task、联合 DAG、全部边界 COPY 与容量；通过后才在另行授权的预算内做一次官方 E0。若任一静态量不符，停下定位，勿用静态时间包络当成绩。
