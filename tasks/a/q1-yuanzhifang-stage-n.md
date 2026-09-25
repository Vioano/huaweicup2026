# Stage N: adjacent union with unchanged-Task spill invariant

- **目标**：保留固定 a053 shared-input 构造的一次调用，在结构安全时合并同核相邻 Task。放宽 Stage M 的“所有原 Task resident union 均须合格”守卫，只要求每个实际合并对的 union 按官方 L1/UB（DDR→UB）容量合格。此处只准备源码，不宣称 Makespan 改善。
- **输入与来源**：原始图 JSON、核数 1–5、官方固定 config；固定基源 `a0537aeb72dc702af86d67d3194587d581ac207c` 及七项依赖哈希见 `src/q1_yuanzhifang_stage_n/sources.json`。Stage M 来源 `6003ef7684c5649b5ccafb653c4b11aa67945439`；父静态证明/反例归档 `49578ebeaad4d6283218b5787052d861f780ca52`。不读取历史 plan、成绩或 case ID 进行分派。
- **方法与边界**：先校验原图、每 tensor 至多一个 producer、无 excluded COPY 桥、Task 依赖全在同核向前。逐核左到右选不重叠、完整 incident-tensor union 合容量的相邻对，保留左 Task ID，最后官方 `derive_multicore_plan` / `validate_task_order`。不适用时返回原 base 与原因。未合并 Task 的 Step1/Step2 spill 逻辑在严格保序 COPY ID 重命名下保持；不推断 Step3、FIFO/MEM 物理时序或 Makespan。没有在线评分。
- **产物**：`src/q1_yuanzhifang_stage_n/` 新 CLI 与来源清单、`tests/test_q1_adjacent_spill_invariant.py`。CLI 为 `python -B -m src.q1_yuanzhifang_stage_n.adjacent_spill_invariant GRAPH --cores K --output PLAN --diagnostics DIAG`；plan 仅两字段，diag 记原图字节 SHA、守卫/合并及构造体内计时，完整 cold wall 由未来外层 runner 测量。
- **验收**：本阶段只运行小合成控制器测试、静态来源/差异检查；0 真实图构造、0 Task 编译、0 E0/E1/E2。未来正式试验需单独冻结 cells、预算与监督方式，不能继承 Stage M 的 044 调用次数。
- **交接与限制**：提交后报告完整源码 SHA、实际测试命令/结果、未验证项并停止写入。只验证计划结构及充分容量条件；质量、求解冷墙钟、正式 E0 需后续独立核查。
