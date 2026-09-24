# 固定分带前瞻候选的全识别族检验

1. **目标与输入**：输入来自固定结构扫描的全部10图×1–5核50位置；不用旧axis构造的成功条件筛选新构造，包含单核。forest500收据以固定bff88a66提交原件/计划/结果SHA及输入身份验证。全是已见图，不声称留出集。
2. **方法**：每个原forest在线调用数小于3的位置，只构造一次band DP + pair-cache树序 + one-leaf。组合入口不读结果表/case名单，不枚举前瞻深度；重复方案和可证明下界不优于incumbent时不评分。不能将代理D优化当成官方M最优。
3. **预算**：50位置检查，最多49新P3 E0，0新P2/0solver/0retry；1worker、90秒/调用、600秒/批，首个失败停止。058/079五核若计划字节和冻结输入身份精确相同，复用已测两份P3，不再运行。所有计划在首次E0前保存。预检只构造、derive与静态下界，成本单列。
4. **产物**：src/q3/band_lookahead_family_probe.py，独立results/a/q3-nikolastarx/band-lookahead-family-20260925目录；每位置保留状态、候选字节/哈希、固定旧控制与新官方结果、调用/墙钟及负例。
5. **验收**：完整覆盖50位置的适用/预算/去重/下界/实测状态；M主指标，extra COPY/spill/字节命中率和构造/外部E0耗时分别报告。历史结果复用与新增E0明确区分。这是固定候选机制检验，不是新500格求解器成绩或在线耗时；最终上榜仍需同一入口全量运行。
6. **后续决策**：根据结构族整体增益与反例判断是否值得在线全量；不只挑两张正例，不用全量试跑取代机制判断。新在线入口仍维持总3次E0上限；本次离线候选批不扩大它。

运行：`uv run --locked python -m src.q3.band_lookahead_family_probe results/a/q3-nikolastarx/band-lookahead-family-20260925 --source FULL_SHA --forest-root FOREST_PRODUCER`，先用`--preflight`。版本先冻结；预检成功不等于正式评分结束。
